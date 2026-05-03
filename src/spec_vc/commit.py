from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
import uuid

from .config import Config
from .gitops import run_git, staged_files

TOKEN_TTL_SECONDS = 300
TOKEN_FILENAME = "spec-vc-commit-token"
COMMIT_MSG_FILENAME = "spec-vc-commit-msg"
SUBAGENT_SESSIONS_FILENAME = "spec-vc-subagent-sessions.log"
PREPARE_TS_FILENAME = "spec-vc-prepare-ts"


def write_commit_message(repo_root: Path, message: str) -> Path:
    msg_path = repo_root / ".git" / COMMIT_MSG_FILENAME
    msg_path.write_text(message)
    return msg_path


def write_commit_token(repo_root: Path) -> Path:
    """在 .git 目录写入一次性提交 token（basic 2 行格式），返回 token 文件路径。"""
    git_dir = repo_root / ".git"
    token_path = git_dir / TOKEN_FILENAME
    token_content = f"{uuid.uuid4().hex}\n{int(time.time())}"
    token_path.write_text(token_content)
    return token_path


def validate_and_consume_token(repo_root: Path) -> None:
    """校验 token 存在且未过期、subagent session 有记录，通过后消费 token。"""
    git_dir = repo_root / ".git"
    token_path = git_dir / TOKEN_FILENAME

    if not token_path.exists():
        raise FileNotFoundError(
            "未找到提交 token。请通过 spec-vc commit prepare + subagent 审计 + submit 流程提交代码，"
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

    session_log = git_dir / SUBAGENT_SESSIONS_FILENAME
    if not session_log.exists() or session_log.read_text().strip() == "":
        raise FileNotFoundError(
            "未找到 subagent 审计记录。请先通过 spec-vc commit prepare 写入 commit-msg，"
            "然后由 AI 执行 subagent 审计流程，最后在终端运行 spec-vc commit submit。\n"
            "如果 PostToolUse hook 未配置，请运行 spec-vc init 重新初始化。"
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
