from __future__ import annotations

import datetime
import os
import sys
from pathlib import Path
import re

from .adr import ensure_referenceable, exemption_allows, parse_adr
from .commit import validate_and_consume_token
from .config import load_config
from .errors import ValidationError
from .gitops import repo_root_from, staged_diff_numstat, staged_files


ADR_TOKEN_RE = re.compile(r"\[(ADR-none|ADR-\?+|ADR-\d{3,})\]")
EXACT_NONE_RE = re.compile(r"\[ADR-none\]")
EXACT_NUM_RE = re.compile(r"\[ADR-(\d{3,})\]")

BYPASS_LOG_FILENAME = "spec-vc-bypass.log"
SUBAGENT_SESSIONS_FILENAME = "spec-vc-subagent-sessions.log"


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


HELP_MISSING = """[spec-vc] Commit 被阻塞:subject 必须包含且只能包含一个 [ADR-NNN] 或 [ADR-none]"""
HELP_SLOT = """[spec-vc] Commit 被阻塞:检测到未填充的槽位 [ADR-???]"""


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
            validate_and_consume_token(repo_root)
        except (FileNotFoundError, ValueError, TimeoutError) as e:
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
