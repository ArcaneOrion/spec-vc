from __future__ import annotations

import datetime
import hashlib
from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .gitops import run_git, staged_files

COMMIT_MSG_FILENAME = "spec-vc-commit-msg"
SUBAGENT_SESSIONS_FILENAME = "spec-vc-subagent-sessions.log"
AUDIT_ANCHOR_FILENAME = "spec-vc-audit-anchor"


def write_commit_message(repo_root: Path, message: str) -> Path:
    msg_path = repo_root / ".git" / COMMIT_MSG_FILENAME
    msg_path.write_text(message)
    return msg_path


def compute_audit_anchor(repo_root: Path, adr_token: str) -> str:
    """生成 audit anchor = '<adr_token>@<sha12>'。

    sha12 = sha256(git diff --cached --no-renames --no-color)[:12]。
    adr_token 形如 'ADR-017' 或 'ADR-none'（无方括号）。

    设计意图（ADR-017）：把 staged 内容指纹和 ADR 引用绑定到 audit description，
    迫使通过门禁的最小成本至少等于读一次 staged diff。
    """
    diff = run_git(
        repo_root, "diff", "--cached", "--no-renames", "--no-color", check=False
    )
    sha12 = hashlib.sha256(diff.encode("utf-8")).hexdigest()[:12]
    return f"{adr_token}@{sha12}"


def write_audit_anchor(repo_root: Path, anchor: str) -> Path:
    """写 anchor 到 .git/spec-vc-audit-anchor（单行，无 trailing newline）。"""
    anchor_path = repo_root / ".git" / AUDIT_ANCHOR_FILENAME
    anchor_path.write_text(anchor)
    return anchor_path


def read_audit_anchor(repo_root: Path) -> str | None:
    """读 .git/spec-vc-audit-anchor 内容；文件不存在返回 None。"""
    anchor_path = repo_root / ".git" / AUDIT_ANCHOR_FILENAME
    if not anchor_path.exists():
        return None
    return anchor_path.read_text().strip()


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


def check_session_log_freshness(repo_root: Path) -> None:
    """检查 session log 末行时间戳晚于 commit-msg 写入时间。

    旁路条件：commit-msg 文件不存在（用户未走 prepare）→ 跳过。
    Fail-open：log 末行无法解析时间戳时跳过（避免误伤）。
    阻塞条件：末行时间戳 ≤ commit-msg mtime → 抛 FileNotFoundError（陈旧审计）。
    """
    git_dir = repo_root / ".git"
    msg_path = git_dir / COMMIT_MSG_FILENAME
    if not msg_path.exists():
        return

    log_path = git_dir / SUBAGENT_SESSIONS_FILENAME
    if not log_path.exists():
        return  # check_subagent_session 已处理

    lines = [line for line in log_path.read_text().splitlines() if line.strip()]
    if not lines:
        return

    last_line = lines[-1]
    ts_str = last_line.split(" | ", 1)[0].strip()
    try:
        log_ts = datetime.datetime.fromisoformat(ts_str)
    except ValueError:
        return  # fail-open

    msg_mtime = datetime.datetime.fromtimestamp(msg_path.stat().st_mtime).astimezone()
    if log_ts.tzinfo is None:
        log_ts = log_ts.astimezone()

    if log_ts <= msg_mtime:
        raise FileNotFoundError(
            f"subagent 审计陈旧：session log 末行时间戳 "
            f"({log_ts.isoformat(timespec='seconds')}) "
            f"早于 commit-msg 写入时间 ({msg_mtime.isoformat(timespec='seconds')})。\n"
            "本次提交未触发新的 Agent 工具调用，审计可能是历史遗留。\n"
            "下一步：使用 Agent 工具执行新的代码/规格审计，PostToolUse hook 会自动记录。\n"
            "紧急情况下可临时绕过：SPEC_VC_BYPASS=<原因> git commit ...\n"
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