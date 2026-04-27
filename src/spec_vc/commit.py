from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import time
import uuid

from .config import Config
from .gitops import run_git, staged_files

TOKEN_TTL_SECONDS = 300
TOKEN_FILENAME = "spec-vc-commit-token"


def write_commit_token(repo_root: Path) -> Path:
    """在 .git 目录写入一次性提交 token，返回 token 文件路径。"""
    git_dir = repo_root / ".git"
    token_path = git_dir / TOKEN_FILENAME
    token_content = f"{uuid.uuid4().hex}\n{int(time.time())}"
    token_path.write_text(token_content)
    return token_path


def validate_and_consume_token(repo_root: Path) -> None:
    """校验 token 存在且未过期，校验通过后消费（删除）token。"""
    git_dir = repo_root / ".git"
    token_path = git_dir / TOKEN_FILENAME

    if not token_path.exists():
        raise FileNotFoundError(
            "未找到提交 token。请通过 spec-vc commit 流程提交代码，"
            "不要直接使用 git commit。"
        )

    content = token_path.read_text().strip()
    lines = content.split("\n")
    if len(lines) < 2:
        token_path.unlink()
        raise ValueError("token 格式无效，请重新执行 spec-vc commit")

    try:
        token_ts = int(lines[1])
    except ValueError:
        token_path.unlink()
        raise ValueError("token 格式无效，请重新执行 spec-vc commit")

    if time.time() - token_ts > TOKEN_TTL_SECONDS:
        token_path.unlink()
        raise TimeoutError(
            f"提交 token 已过期（有效期 {TOKEN_TTL_SECONDS // 60} 分钟），"
            "请重新执行 spec-vc commit"
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


def gather_commit_context(repo_root: Path, config: Config) -> CommitContext:
    from .spec import list_formal_files, list_specs, specs_root as get_specs_root

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

    return CommitContext(
        repo_root=repo_root,
        specs_root=specs_root,
        staged_files=files,
        staged_diff=diff,
        spec_dirs=spec_dirs,
        formal_files=formal_files,
        dev_docs=dev_docs,
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
