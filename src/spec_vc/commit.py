from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .gitops import run_git, staged_files

COMMIT_MSG_FILENAME = "spec-vc-commit-msg"
SUBAGENT_SESSIONS_FILENAME = "spec-vc-subagent-sessions.log"


def write_commit_message(repo_root: Path, message: str) -> Path:
    msg_path = repo_root / ".git" / COMMIT_MSG_FILENAME
    msg_path.write_text(message)
    return msg_path


def check_subagent_session(repo_root: Path) -> None:
    """检查 subagent session log 存在且非空，否则阻塞提交。"""
    git_dir = repo_root / ".git"
    session_log = git_dir / SUBAGENT_SESSIONS_FILENAME
    if not session_log.exists() or session_log.read_text().strip() == "":
        raise FileNotFoundError(
            "未找到 subagent 审计记录。\n"
            "下一步：使用 Agent 工具执行代码/规格审计，PostToolUse hook 会自动记录到 "
            ".git/spec-vc-subagent-sessions.log。\n"
            "如未配置 hook，运行 spec-vc init 自动注入 .claude/settings.json。\n"
            "紧急情况下可临时绕过（会写审计日志至 .git/spec-vc-bypass.log）：\n"
            "  SPEC_VC_BYPASS=<原因> git commit ...\n"
            "详细流程请查看 SKILL.md"
        )


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
    from .spec import list_formal_files, list_specs, check_spec_readiness, specs_root as get_specs_root

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