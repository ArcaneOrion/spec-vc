"""ADR-018: spec-vc review —— 独立审查命令。

承担三件事:
1. 计算 anchor = ADR-XXX@<staged-diff-sha12>
2. 按 mode 校验证据（subagent 模式不强制 --note；simple 模式要求 --note 含 anchor）
3. 写 .git/spec-vc-review.json + .git/spec-vc-commit-msg

commit-msg hook 读 review.json 校验审计证据，不再读 PostToolUse session log（保留辅助）。
"""

from __future__ import annotations

import datetime
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .commit import (
    compute_audit_anchor,
    write_commit_message,
)


REVIEW_FILENAME = "spec-vc-review.json"
ADR_TOKEN_RE = re.compile(r"\[(ADR-none|ADR-\?+|ADR-\d{3,})\]")


@dataclass(slots=True)
class ReviewRecord:
    """.git/spec-vc-review.json 内容契约（Spec-018 ReviewRecord + ADR-019 context_summary）。"""

    anchor: str
    adr_token: str
    staged_sha12: str
    mode: str
    verified: bool
    note: str = ""
    subagent_log_tail: str | None = None
    created_at: str = field(default_factory=lambda: datetime.datetime.now().astimezone().isoformat(timespec="seconds"))
    context_summary: str = ""
    document_baseline: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def review_path(repo_root: Path) -> Path:
    return repo_root / ".git" / REVIEW_FILENAME


def write_review(repo_root: Path, record: ReviewRecord) -> Path:
    path = review_path(repo_root)
    path.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2))
    return path


def read_review(repo_root: Path) -> ReviewRecord | None:
    path = review_path(repo_root)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        return ReviewRecord(
            anchor=str(data["anchor"]),
            adr_token=str(data["adr_token"]),
            staged_sha12=str(data["staged_sha12"]),
            mode=str(data["mode"]),
            verified=bool(data["verified"]),
            note=str(data.get("note", "")),
            subagent_log_tail=data.get("subagent_log_tail"),
            created_at=str(data["created_at"]),
            context_summary=str(data.get("context_summary", "")),
            document_baseline=data.get("document_baseline") if isinstance(data.get("document_baseline"), dict) else None,
        )
    except (KeyError, TypeError, ValueError):
        return None


def extract_adr_token(message: str) -> str | None:
    """从 commit message 第一行提取 ADR token。返回 'ADR-018'/'ADR-none'/'ADR-???' 或 None。"""
    first_line = message.splitlines()[0] if message else ""
    m = ADR_TOKEN_RE.search(first_line)
    if not m:
        return None
    return m.group(1)


def build_review_record(
    repo_root: Path,
    adr_token: str,
    mode: str,
    verified: bool,
    note: str,
    subagent_log_tail: str | None = None,
) -> ReviewRecord:
    anchor = compute_audit_anchor(repo_root, adr_token)
    staged_sha12 = anchor.split("@", 1)[1]
    return ReviewRecord(
        anchor=anchor,
        adr_token=adr_token,
        staged_sha12=staged_sha12,
        mode=mode,
        verified=verified,
        note=note,
        subagent_log_tail=subagent_log_tail,
    )


def write_review_and_msg(
    repo_root: Path, record: ReviewRecord, message: str
) -> tuple[Path, Path]:
    """先写 commit-msg，再写 review.json。
    保证 review.json.mtime > commit-msg.mtime，便于 hook 校验新鲜度。
    """
    msg_path = write_commit_message(repo_root, message)
    # 确保 review.json 的 mtime 严格大于 commit-msg.mtime（同秒写入时手工抬升）
    review = review_path(repo_root)
    review.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2))
    msg_stat = msg_path.stat()
    review_stat = review.stat()
    if review_stat.st_mtime <= msg_stat.st_mtime:
        import os
        new_ts = msg_stat.st_mtime + 1.0
        os.utime(review, (new_ts, new_ts))
    return review, msg_path
