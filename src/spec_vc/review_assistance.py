"""ADR-019: spec-vc review 审查助手。

设计哲学转向：从 sticks（提高作弊成本）转 carrots（降低遵守成本）。
让审查所需信息成为 spec-vc review 命令的免费副产品输出到 stderr，
AI 读取这份报告本身就是审查发生。

新心智模型：写代码 → review（读到一份审查报告）→ 发现问题 → 改 → 满意 → commit
review 是自检，不是审批。

所有函数 fail-open：单段抛异常 → 返回错误说明文字，不阻塞 review 流程。
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from ._sections import extract_section
from .config import ReviewAssistanceConfig
from .gitops import run_git, staged_files


_HUNK_HEADER_RE = re.compile(r"^@@\s+-?\d+(?:,\d+)?\s+\+?\d+(?:,\d+)?\s+@@")


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "... (truncated)"


def summarize_staged_diff(
    repo_root: Path, max_files: int = 20, max_hunks_per_file: int = 3
) -> str:
    """返回 staged diff 摘要（git diff --stat + 每文件前 N 个 hunk header）。fail-open。"""
    try:
        stat_output = run_git(
            repo_root, "diff", "--cached", "--stat", check=False
        ).strip()
        files = staged_files(repo_root)
        if not files:
            return "=== Staged Diff Summary ===\n(无 staged changes)"

        lines = ["=== Staged Diff Summary ===", stat_output, ""]
        lines.append("关键 hunk:")
        shown = 0
        for f in files[:max_files]:
            try:
                file_diff = run_git(
                    repo_root, "diff", "--cached", "--no-color", "--", f, check=False
                )
            except Exception as e:
                lines.append(f"  {f}: (获取失败: {e!r})")
                continue
            hunks = [
                ln.rstrip() for ln in file_diff.splitlines() if _HUNK_HEADER_RE.match(ln)
            ]
            for h in hunks[:max_hunks_per_file]:
                lines.append(f"  {f} {h}")
                shown += 1
        if shown == 0:
            lines.append("  (无 hunk header，可能是新文件或纯二进制变更)")
        if len(files) > max_files:
            lines.append(f"  ... 还有 {len(files) - max_files} 个文件未列出")
        return "\n".join(lines)
    except Exception as e:
        return f"=== Staged Diff Summary ===\n(本段获取失败: {e!r})"


def summarize_plan_context(
    repo_root: Path, adr_token: str, max_chars_per_section: int = 600
) -> str:
    """返回关联 ADR plan 的 Design + Verification 段摘要。fail-open。"""
    header = "=== Plan Context (Design + Verification) ==="
    try:
        m = re.match(r"^ADR-(\d{3,}|none)$", adr_token)
        if not m or m.group(1) == "none":
            return f"{header}\n(adr_token={adr_token!r}，无对应 plan)"
        adr_id = m.group(1)

        plans_dir = repo_root / "doc" / "arch" / "plans"
        pattern = re.compile(rf"^ADR-{re.escape(adr_id)}-plan-(\d+)\.md$")
        candidates: list[tuple[int, Path]] = []
        if plans_dir.exists():
            for p in plans_dir.iterdir():
                mm = pattern.match(p.name)
                if mm:
                    candidates.append((int(mm.group(1)), p))
        if not candidates:
            return f"{header}\n(ADR-{adr_id} 无活跃 plan，已 close 或未启动)"

        candidates.sort(key=lambda x: x[0])
        plan_path = candidates[-1][1]
        text = plan_path.read_text()

        design = extract_section(text, "Design and Architecture").strip()
        verify = extract_section(text, "Verification and Testing").strip()

        lines = [header, f"plan: {plan_path.name}", ""]
        lines.append("--- Design and Architecture ---")
        lines.append(_truncate(design, max_chars_per_section) if design else "(段为空)")
        lines.append("")
        lines.append("--- Verification and Testing ---")
        lines.append(_truncate(verify, max_chars_per_section) if verify else "(段为空)")
        return "\n".join(lines)
    except Exception as e:
        return f"{header}\n(本段获取失败: {e!r})"


def summarize_spec_context(
    repo_root: Path, adr_token: str, max_lines_per_file: int = 30
) -> str:
    """返回关联 Spec 的形式化契约前 N 行。fail-open。"""
    from .config import load_config
    from .spec import list_specs, specs_root as get_specs_root

    header = "=== Spec Context ==="
    try:
        m = re.match(r"^ADR-(\d{3,}|none)$", adr_token)
        if not m or m.group(1) == "none":
            return f"{header}\n(adr_token={adr_token!r}，无对应 Spec)"
        adr_id = m.group(1)
        adr_ref = f"ADR-{adr_id}"

        config = load_config(repo_root)
        specs_root = get_specs_root(repo_root, config.spec.dir)
        if not specs_root.exists():
            return f"{header}\n(specs 目录不存在)"

        associated = [s for s in list_specs(specs_root) if s.adr_ref == adr_ref]
        if not associated:
            return f"{header}\n({adr_ref} 无关联 Spec)"

        lines = [header]
        for spec in associated:
            spec_dir = specs_root / spec.spec_id
            for fname in ("contract.openapi.yaml", "schema.json", "behavior.feature"):
                fpath = spec_dir / fname
                lines.append("")
                lines.append(f"--- Spec-{spec.spec_id}/{fname} ---")
                if not fpath.exists():
                    lines.append("(文件不存在)")
                    continue
                try:
                    file_lines = fpath.read_text().splitlines()
                except Exception as e:
                    lines.append(f"(读取失败: {e!r})")
                    continue
                head = file_lines[:max_lines_per_file]
                lines.extend(head)
                if len(file_lines) > max_lines_per_file:
                    lines.append(f"... ({len(file_lines) - max_lines_per_file} more lines)")
        return "\n".join(lines)
    except Exception as e:
        return f"{header}\n(本段获取失败: {e!r})"


def run_static_checks(repo_root: Path, timeout: float = 5.0) -> str:
    """跑可选的 ruff 检查，缺失工具或超时静默跳过。fail-open。"""
    header = "=== Static Checks ==="
    try:
        ruff = shutil.which("ruff")
        if not ruff:
            return f"{header}\n(未检测到 ruff，跳过静态检查)"
        try:
            proc = subprocess.run(
                [ruff, "check", "src/"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return f"{header}\nruff: 超时（>{timeout}s）跳过"

        if proc.returncode == 0:
            return f"{header}\nruff: 0 errors"
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        body = out or err
        body_lines = body.splitlines()[:10]
        n_errors = sum(1 for ln in body.splitlines() if ":" in ln and "error" in ln.lower()) or len(body_lines)
        return f"{header}\nruff: {n_errors} errors（前 10 行）\n" + "\n".join(body_lines)
    except Exception as e:
        return f"{header}\n(本段获取失败: {e!r})"


def _your_response_section(anchor: str) -> str:
    return (
        "=== Your Response ===\n"
        "看完上述信息后:\n"
        "  ✓ 无问题 → spec-vc commit\n"
        "  ✗ 有问题 → 改代码后重跑 spec-vc review\n"
        f"audit-anchor: {anchor}"
    )


def assemble_review_report(
    repo_root: Path,
    adr_token: str,
    anchor: str,
    config: ReviewAssistanceConfig,
) -> str:
    """按 config 开关拼接 4 个 summarize 段 + Your Response 段。fail-open。"""
    parts: list[str] = []
    if config.show_diff_summary:
        try:
            parts.append(summarize_staged_diff(repo_root))
        except Exception as e:
            parts.append(f"=== Staged Diff Summary ===\n(本段获取失败: {e!r})")
    if config.show_plan_context:
        try:
            parts.append(summarize_plan_context(repo_root, adr_token))
        except Exception as e:
            parts.append(f"=== Plan Context (Design + Verification) ===\n(本段获取失败: {e!r})")
    if config.show_spec_context:
        try:
            parts.append(summarize_spec_context(repo_root, adr_token))
        except Exception as e:
            parts.append(f"=== Spec Context ===\n(本段获取失败: {e!r})")
    if config.run_static_checks:
        try:
            parts.append(run_static_checks(repo_root, timeout=config.static_check_timeout_seconds))
        except Exception as e:
            parts.append(f"=== Static Checks ===\n(本段获取失败: {e!r})")
    parts.append(_your_response_section(anchor))
    return "\n\n".join(parts)
