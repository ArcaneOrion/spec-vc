from __future__ import annotations

import datetime
import os
import sys
from pathlib import Path
import re

from .adr import ensure_referenceable, exemption_allows, parse_adr
from .commit import SUBAGENT_SESSIONS_FILENAME, check_subagent_session
from .config import Config, load_config
from .errors import ValidationError
from .gitops import repo_root_from, staged_diff_numstat, staged_files


ADR_TOKEN_RE = re.compile(r"\[(ADR-none|ADR-\?+|ADR-\d{3,})\]")
EXACT_NONE_RE = re.compile(r"\[ADR-none\]")
EXACT_NUM_RE = re.compile(r"\[ADR-(\d{3,})\]")

BYPASS_LOG_FILENAME = "spec-vc-bypass.log"
ACTIVE_FILE_NAME = "_active.md"
PLAN_DIR_NAME = "plans"

IMPLEMENT_READY_OR_LATER = {"implement-ready", "validate", "close"}


def _load_active_stage(adr_dir: Path, adr_id: str) -> str | None:
    """读取 active change 的 stage，无 active change 时返回 None。"""
    active_path = adr_dir / PLAN_DIR_NAME / ACTIVE_FILE_NAME
    if not active_path.exists():
        return None
    text = active_path.read_text()
    for line in text.splitlines():
        if line.startswith("- **Stage**:"):
            return line.split(":", 1)[1].strip()
    return None


def _check_plan_stage(repo_root: Path, config: Config, adr_id: str) -> None:
    """检查 ADR 对应的变更计划 stage ≥ implement-ready。

    仅在有 active change 时检查。如果变更已关闭（无 active change），
    说明流程已走完，不阻塞提交。
    """
    adr_dir = repo_root / config.project.adr_dir
    stage = _load_active_stage(adr_dir, adr_id)
    if stage is not None and stage not in IMPLEMENT_READY_OR_LATER:
        raise ValidationError(
            f"[spec-vc] Commit 被阻塞: ADR-{adr_id} 的变更计划 stage 为 '{stage}'，"
            f"需推进到 implement-ready 才能提交。\n"
            f"下一步：运行 spec-vc change validate --phase pre --content \"<前置验证内容>\" "
            f"完成前置验证后推进到 implement-ready。\n"
            f"详细流程请查看 SKILL.md"
        )


def _check_spec_readiness_for_adr(repo_root: Path, config: Config, adr_id: str) -> None:
    """检查 ADR 关联的 Spec 是否完整（非骨架）。

    仅在 Spec 目录存在时检查。如果 ADR 没有关联 Spec，不阻塞。
    """
    from .spec import relevant_spec_issues, specs_root as get_specs_root

    specs_root = get_specs_root(repo_root, config.spec.dir)
    if not specs_root.exists():
        return

    issues = relevant_spec_issues(specs_root, adr_id)
    if not issues:
        return

    lines = [
        f"[spec-vc] Commit 被阻塞: ADR-{adr_id} 关联的 Spec 未完成:",
    ]
    for issue in issues:
        lines.append(f"  Spec-{issue.spec_id} / {issue.location}")
        lines.append(f"    → {issue.problem}")
    lines.append("")
    lines.append("修复步骤:")
    lines.append("  1. 填写 dev-doc.md 中各区块内容（概述/接口契约/数据形状/行为规则/测试策略/日志实现）")
    lines.append("  2. 运行 spec-vc spec formalize <id> --type all 生成形式化文件")
    lines.append("  3. 运行 spec-vc spec check 确认就绪")
    lines.append("")
    lines.append("详细流程请查看 SKILL.md")
    raise ValidationError("\n".join(lines))


def run_post_tool_use(repo_root: Path, tool_name: str = "", description: str = "") -> int:
    """全量记录 Agent 工具调用到 subagent session log。"""
    if not tool_name:
        return 0
    log_path = repo_root / ".git" / SUBAGENT_SESSIONS_FILENAME
    timestamp = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    line = f"{timestamp} | {tool_name} | {description}\n"
    try:
        with log_path.open("a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass
    return 0


HELP_MISSING = (
    "[spec-vc] Commit 被阻塞:subject 必须包含且只能包含一个 [ADR-NNN] 或 [ADR-none]\n"
    "下一步：在 commit subject 末尾追加 [ADR-NNN]（具体决策）或 [ADR-none]（豁免，仅限不影响架构的改动）\n"
    "详细流程请查看 SKILL.md"
)
HELP_SLOT = (
    "[spec-vc] Commit 被阻塞:检测到未填充的槽位 [ADR-???]\n"
    "下一步：将 [ADR-???] 替换为具体 [ADR-NNN] 或 [ADR-none]\n"
    "详细流程请查看 SKILL.md"
)


def _subject(message_file: Path) -> str:
    lines = message_file.read_text().splitlines()
    return lines[0].rstrip("\n") if lines else ""


def _extract_exact_tokens(subject: str) -> list[str]:
    return ADR_TOKEN_RE.findall(subject)


def _try_write_bypass_log(repo_root: Path, reason: str, subject: str) -> None:
    """ADR-007: 向 .git/spec-vc-bypass.log 追加 bypass 审计行；fail-open。"""
    log_path = repo_root / ".git" / BYPASS_LOG_FILENAME
    timestamp = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    line = f"{timestamp} | {reason} | {subject}\n"
    try:
        with log_path.open("a", encoding="utf-8") as f:
            f.write(line)
    except OSError as e:
        print(
            f"[spec-vc] bypass 日志写入失败: {e}（commit 仍放行）",
            file=sys.stderr,
        )


def run_commit_msg(message_file: Path) -> int:
    repo_root = repo_root_from(Path.cwd())
    config = load_config(repo_root)
    subject = _subject(message_file)
    tokens = _extract_exact_tokens(subject)

    bypass_reason = os.environ.get("SPEC_VC_BYPASS", "")
    if bypass_reason:
        _try_write_bypass_log(repo_root, bypass_reason, subject)
    else:
        try:
            check_subagent_session(repo_root)
        except FileNotFoundError as e:
            raise ValidationError(str(e)) from e

    if any(token.startswith("ADR-?") for token in tokens):
        raise ValidationError(HELP_SLOT)
    if len(tokens) != 1:
        raise ValidationError(HELP_MISSING)

    token = tokens[0]
    if token == "ADR-none":
        files = staged_files(repo_root)
        total = sum(add + delete for add, delete, _ in staged_diff_numstat(repo_root))
        allowed, reason = exemption_allows(config, files, total)
        if not allowed:
            raise ValidationError(f"[spec-vc] [ADR-none] 不符合豁免规则: {reason}")
        return 0

    match = EXACT_NUM_RE.search(f"[{token}]")
    if not match:
        raise ValidationError(HELP_MISSING)
    adr_id = match.group(1)
    adr_file = repo_root / config.project.adr_dir / f"adr-{adr_id}.md"
    if not adr_file.exists():
        raise ValidationError(f"[spec-vc] Commit 被阻塞:引用的 ADR 不存在: ADR-{adr_id}")
    adr = parse_adr(adr_file)
    ensure_referenceable(adr, adr_id)

    # [ADR-NNN] 额外检查: plan stage ≥ implement-ready + Spec 完整性
    _check_plan_stage(repo_root, config, adr_id)
    _check_spec_readiness_for_adr(repo_root, config, adr_id)

    return 0


def run_prepare_commit_msg(message_file: Path, source: str = "", _sha: str = "") -> int:
    if source in {"merge", "squash", "commit"}:
        return 0
    lines = message_file.read_text().splitlines()
    if not lines:
        return 0
    first = lines[0]
    subject_tokens = _extract_exact_tokens(first)
    if not subject_tokens and first and not first.startswith("#"):
        lines[0] = f"{first} [ADR-???]"
    hint = "# spec-vc 提示:\n#   [ADR-NNN]  引用具体决策\n#   [ADR-none] 显式豁免,仅限不影响架构的改动"
    text = "\n".join(lines)
    if "# spec-vc 提示:" not in text:
        text = text.rstrip("\n") + "\n\n" + hint + "\n"
    else:
        text = text.rstrip("\n") + "\n"
    message_file.write_text(text)
    return 0