from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import math
import shutil
import sys
import time
import uuid

from .config import Config
from .gitops import run_git, staged_files
from .manifest import (
    AuditManifest,
    AuditUnit,
    ComplexityReport,
    DevDocSummary,
    TestUnit,
)
from .spec import specs_root as get_specs_root

TOKEN_TTL_SECONDS = 300
TOKEN_FILENAME = "spec-vc-commit-token"
MANIFEST_FILENAME = "spec-vc-manifest.json"
AUDIT_REPORT_FILENAME = "spec-vc-audit-report.json"
TEST_REPORT_FILENAME = "spec-vc-test-report.json"
COMMIT_MSG_FILENAME = "spec-vc-commit-msg"


def _sha256_hex(file_path: Path) -> str:
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def write_commit_message(repo_root: Path, message: str) -> Path:
    msg_path = repo_root / ".git" / COMMIT_MSG_FILENAME
    msg_path.write_text(message)
    return msg_path


def write_commit_token(repo_root: Path,
                       manifest_hash: str = "",
                       audit_hash: str = "",
                       test_hash: str = "") -> Path:
    """写入 hash chain token 到 .git/spec-vc-commit-token。"""
    git_dir = repo_root / ".git"
    token_path = git_dir / TOKEN_FILENAME
    parts = [uuid.uuid4().hex, str(int(time.time()))]
    if manifest_hash or audit_hash or test_hash:
        parts.extend([manifest_hash, audit_hash, test_hash])
    token_path.write_text("\n".join(parts))
    return token_path


def validate_and_consume_token(repo_root: Path) -> None:
    """校验 token（含 hash chain），通过后消费（删除）token。"""
    git_dir = repo_root / ".git"
    token_path = git_dir / TOKEN_FILENAME

    if not token_path.exists():
        raise FileNotFoundError(
            "未找到提交 token。请通过 spec-vc commit prepare + submit 流程提交代码，"
            "不要直接使用 git commit。\n"
            "紧急情况下可临时绕过（会写审计日志至 .git/spec-vc-bypass.log）：\n"
            "  SPEC_VC_BYPASS=<原因> git commit ..."
        )

    content = token_path.read_text().strip()
    lines = content.split("\n")
    if len(lines) < 2:
        token_path.unlink()
        raise ValueError("token 格式无效，请重新执行 spec-vc commit prepare + submit")

    try:
        token_ts = int(lines[1])
    except ValueError:
        token_path.unlink()
        raise ValueError("token 格式无效，请重新执行 spec-vc commit prepare + submit")

    if time.time() - token_ts > TOKEN_TTL_SECONDS:
        token_path.unlink()
        raise TimeoutError(
            f"提交 token 已过期（有效期 {TOKEN_TTL_SECONDS // 60} 分钟），"
            "请重新执行 spec-vc commit prepare + submit"
        )

    if len(lines) == 2:
        token_path.unlink()
        raise ValueError(
            "token 格式已升级，旧格式不再支持。"
            "请使用 spec-vc commit prepare + submit 流程重新提交"
        )

    if len(lines) != 5:
        token_path.unlink()
        raise ValueError("token 格式无效，请重新执行 spec-vc commit prepare + submit")

    manifest_hash, audit_hash, test_hash = lines[2], lines[3], lines[4]

    manifest_path = git_dir / MANIFEST_FILENAME
    audit_path = git_dir / AUDIT_REPORT_FILENAME
    test_path = git_dir / TEST_REPORT_FILENAME

    for fpath, fname, expected in [
        (manifest_path, "manifest", manifest_hash),
        (audit_path, "审计报告", audit_hash),
        (test_path, "测试报告", test_hash),
    ]:
        if not fpath.exists():
            token_path.unlink()
            raise FileNotFoundError(f"{fname} 文件不存在，请重新执行 spec-vc commit prepare")
        actual = _sha256_hex(fpath)
        if actual != expected:
            token_path.unlink()
            raise ValueError(
                f"{fname} 与 token 内哈希不匹配，可能已被篡改。"
                "请重新执行 spec-vc commit prepare + submit"
            )

    token_path.unlink()


@dataclass
class CommitContext:
    repo_root: Path
    specs_root: Path
    staged_files: list[str]
    staged_diff: str
    spec_dirs: list[str]
    formal_files: dict[str, list[str]]
    dev_docs: dict[str, str]
    spec_readiness_issues: list


def gather_commit_context(repo_root: Path, config: Config) -> CommitContext:
    from .spec import list_formal_files, list_specs, check_spec_readiness

    specs_root = get_specs_root(repo_root, config.spec.dir)
    files = staged_files(repo_root)
    diff = run_git(repo_root, "diff", "--cached", check=False)

    specs = list_specs(specs_root)
    spec_dirs: list[str] = []
    formal_files: dict[str, list[str]] = {}
    dev_docs: dict[str, str] = {}

    for s in specs:
        spec_dirs.append(s.spec_id)
        formal_files[s.spec_id] = list_formal_files(specs_root, s.spec_id)
        dev_doc_path = specs_root / s.spec_id / "dev-doc.md"
        if dev_doc_path.exists():
            dev_docs[s.spec_id] = dev_doc_path.read_text()

    readiness_issues = check_spec_readiness(specs_root)

    return CommitContext(
        repo_root=repo_root,
        specs_root=specs_root,
        staged_files=files,
        staged_diff=diff,
        spec_dirs=spec_dirs,
        formal_files=formal_files,
        dev_docs=dev_docs,
        spec_readiness_issues=readiness_issues,
    )


def prepare_audit_prompt(ctx: CommitContext) -> str:
    lines: list[str] = []
    lines.append("你是 spec-vc 审计 subagent。你的职责是对照 Spec 形式化文件和开发文档，审查 git diff 中的代码变更是否符合规格。")
    lines.append("")
    lines.append("## 审计规则")
    lines.append("")
    lines.append("1. 逐条阅读每个 Spec 的形式化文件（contract.openapi.yaml / schema.json / behavior.feature）")
    lines.append("2. 对照 dev-doc.md 理解设计意图（概述 + 非目标）")
    lines.append("3. 检查 git diff 中的每一处代码变更")
    lines.append("4. 输出格式：每条结论包含 [✅] / [⚠️] / [❌]，附文件路径+行号")
    lines.append("5. 不生成代码，不生成测试，只做对照审计")
    lines.append("")
    if ctx.dev_docs:
        lines.append("## 开发文档 (dev-doc.md)")
        lines.append("")
        for spec_id, doc in ctx.dev_docs.items():
            lines.append(f"### Spec-{spec_id}")
            lines.append("")
            lines.append(doc)
            lines.append("")

    lines.append("## 形式化规格文件")
    lines.append("")
    for spec_id in ctx.spec_dirs:
        base = ctx.specs_root / spec_id
        formal_list = ctx.formal_files.get(spec_id, [])
        if not formal_list:
            lines.append(f"### Spec-{spec_id}: (无形式化文件)")
            lines.append("")
            continue
        for fname in formal_list:
            fpath = base / fname
            if fpath.exists():
                lines.append(f"### Spec-{spec_id} / {fname}")
                lines.append("")
                lines.append(fpath.read_text())
                lines.append("")

    lines.append("## Git Diff（暂存区变更）")
    lines.append("")
    lines.append("```diff")
    lines.append(ctx.staged_diff)
    lines.append("```")
    lines.append("")
    lines.append("## 输出格式要求")
    lines.append("")
    lines.append("请输出结构化审计报告，格式如下：")
    lines.append("")
    lines.append("```markdown")
    lines.append("## 审计报告")
    lines.append("")
    lines.append("### Spec-NNN / formal-file-name")
    lines.append("- [✅] 描述: 代码实现了 X 行为 (path:line)")
    lines.append("- [⚠️] 描述: 部分实现但偏差 (path:line)")
    lines.append("- [❌] 描述: 未实现或违反 (path:line 或 未找到)")
    lines.append("")
    lines.append("## 汇总")
    lines.append("- 通过: N")
    lines.append("- 警告: N")
    lines.append("- 失败: N")
    lines.append("- 判定: 通过 | 阻塞")
    lines.append("```")

    return "\n".join(lines)


def prepare_test_prompt(ctx: CommitContext) -> str:
    lines: list[str] = []
    lines.append("你是 spec-vc 测试生成 subagent。你的职责是仅根据 Spec 形式化文件生成并执行测试——不阅读代码，不阅读 dev-doc.md。")
    lines.append("")
    lines.append("## 规则")
    lines.append("")
    lines.append("1. 仅基于形式化规格文件生成测试")
    lines.append("2. 不看代码（代码实现是否正确由审计 subagent 负责）")
    lines.append("3. 测试文件写入 doc/arch/specs/{spec_id}/tests/ 目录")
    lines.append("4. 生成后立即执行测试，报告通过/失败")
    lines.append("5. 测试应按形式化文件类型生成：")
    lines.append("   - contract.openapi.yaml → HTTP 契约测试（请求/响应格式、状态码）")
    lines.append("   - schema.json → 数据校验测试（输入/输出形状、边界值）")
    lines.append("   - behavior.feature → 行为场景测试（Gherkin 执行）")
    lines.append("")

    lines.append("## 形式化规格文件")
    lines.append("")
    for spec_id in ctx.spec_dirs:
        base = ctx.specs_root / spec_id
        formal_list = ctx.formal_files.get(spec_id, [])
        if not formal_list:
            continue
        for fname in formal_list:
            fpath = base / fname
            if fpath.exists():
                lines.append(f"### Spec-{spec_id} / {fname}")
                lines.append("")
                lines.append(fpath.read_text())
                lines.append("")

    lines.append("## 输出格式要求")
    lines.append("")
    lines.append("请输出测试报告，包含：")
    lines.append("")
    lines.append("```markdown")
    lines.append("## 测试报告")
    lines.append("")
    lines.append("### Spec-NNN / formal-file-name")
    lines.append("- 测试文件: tests/test_xxx.py（N 个用例）")
    lines.append("- 执行结果: 通过 | 失败")
    lines.append("- 覆盖项: 列出覆盖的 Spec 条目")
    lines.append("")
    lines.append("## 汇总")
    lines.append("- 用例总数: N")
    lines.append("- 通过: N")
    lines.append("- 失败: N")
    lines.append("- 判定: 通过 | 失败")
    lines.append("```")

    return "\n".join(lines)


def cleanup_tests(specs_root: Path) -> list[str]:
    removed: list[str] = []
    if not specs_root.exists():
        return removed
    for spec_dir in sorted(specs_root.iterdir()):
        if not spec_dir.is_dir():
            continue
        test_dir = spec_dir / "tests"
        if test_dir.exists():
            shutil.rmtree(test_dir)
            removed.append(str(test_dir))
    return removed


def _compute_audit_complexity(num_formal_files: int, diff_line_count: int) -> int:
    score = num_formal_files * 2
    if diff_line_count > 100:
        score += 3
    elif diff_line_count > 30:
        score += 2
    elif diff_line_count > 0:
        score += 1
    return min(score, 10)


def _compute_test_complexity(formal_type: str, content: str) -> int:
    lines = content.splitlines()
    if formal_type == "openapi":
        path_count = sum(1 for line in lines if line.strip().startswith("/") or "get:" in line or "post:" in line or "put:" in line or "delete:" in line or "patch:" in line)
        return min(max(1, path_count), 10)
    elif formal_type == "jsonschema":
        prop_count = content.count('"type"')
        return min(max(1, prop_count // 2), 10)
    elif formal_type == "gherkin":
        scenario_count = sum(1 for line in lines if line.strip().startswith("Scenario"))
        return min(max(1, scenario_count), 10)
    return 1


def build_audit_manifest(ctx: CommitContext) -> AuditManifest:
    from .spec import parse_spec as _parse_spec

    audit_units: list[AuditUnit] = []
    test_units: list[TestUnit] = []
    diff_lines = len(ctx.staged_diff.splitlines()) if ctx.staged_diff else 0

    for spec_id in ctx.spec_dirs:
        doc_summary = DevDocSummary()
        adr_ref = "未知"
        try:
            spec = _parse_spec(ctx.specs_root / spec_id / "dev-doc.md")
        except Exception as e:
            print(f"[spec-vc] 警告: Spec-{spec_id} dev-doc.md 解析失败 ({e})，审计上下文可能不完整", file=sys.stderr)
        else:
            adr_ref = spec.adr_ref
            doc_summary = DevDocSummary(
                overview=spec.overview,
                interface_contract=spec.interface_contract,
                data_shape=spec.data_shape,
                behavior_rules=spec.behavior_rules,
                non_goals=spec.non_goals,
            )

        formal_files: dict[str, str] = {}
        for fname in ctx.formal_files.get(spec_id, []):
            fpath = ctx.specs_root / spec_id / fname
            if fpath.exists():
                formal_files[fname] = fpath.read_text()

        complexity = _compute_audit_complexity(len(formal_files), diff_lines)

        audit_units.append(
            AuditUnit(
                unit_id=f"audit-{spec_id}",
                spec_id=spec_id,
                adr_ref=adr_ref,
                dev_doc_summary=doc_summary,
                formal_files=formal_files,
                complexity_score=complexity,
            )
        )

        for fname, content in formal_files.items():
            formal_type = {
                "contract.openapi.yaml": "openapi",
                "schema.json": "jsonschema",
                "behavior.feature": "gherkin",
            }.get(fname, "unknown")
            if formal_type == "unknown":
                continue
            test_complexity = _compute_test_complexity(formal_type, content)
            test_units.append(
                TestUnit(
                    unit_id=f"test-{spec_id}-{formal_type}",
                    spec_id=spec_id,
                    formal_type=formal_type,
                    formal_content=content,
                    test_dir=f"specs/{spec_id}/tests/",
                    estimated_complexity=test_complexity,
                )
            )

    total_audit = len(audit_units)
    total_test = len(test_units)
    complexity_report = ComplexityReport(
        total_audit_units=total_audit,
        total_test_units=total_test,
        recommended_audit_agents=max(1, math.ceil(total_audit / 3)),
        recommended_test_agents=max(1, math.ceil(total_test / 3)),
    )

    return AuditManifest(
        repo_root=str(ctx.repo_root),
        specs_root=str(ctx.specs_root),
        staged_files=ctx.staged_files,
        staged_diff=ctx.staged_diff,
        audit_units=audit_units,
        test_units=test_units,
        complexity_report=complexity_report,
    )


def manifest_to_json(manifest: AuditManifest) -> str:
    from dataclasses import asdict

    return json.dumps(asdict(manifest), ensure_ascii=False, indent=2)
