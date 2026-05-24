from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path
import re

from .adr import ensure_referenceable, parse_adr
from .commit import SUBAGENT_SESSIONS_FILENAME, compute_audit_anchor, COMMIT_MSG_FILENAME
from .config import Config, load_config
from .errors import BlockingError, ValidationError
from .gitops import repo_root_from
from .review import read_review, review_path


ADR_TOKEN_RE = re.compile(r"\[(ADR-none|ADR-\?+|ADR-\d{3,})\]")
EXACT_NONE_RE = re.compile(r"\[ADR-none\]")
EXACT_NUM_RE = re.compile(r"\[ADR-(\d{3,})\]")

BYPASS_LOG_FILENAME = "spec-vc-bypass.log"


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


def _check_review_record(repo_root: Path, config: Config, adr_id: str) -> None:
    """[ADR-NNN] 时校验 .git/spec-vc-review.json（ADR-018）。

    取代 ADR-013/017 的 session log + anchor 间接证据，把审计证据搭在直接文件上。
    所有阻塞输出走 BlockingError 结构（含 reason / current_state / fix_commands / docs_ref）。
    """
    adr_token = f"ADR-{adr_id}"
    expected_anchor = compute_audit_anchor(repo_root, adr_token)
    expected_sha12 = expected_anchor.split("@", 1)[1]

    rv_path = review_path(repo_root)
    record = read_review(repo_root)
    if record is None:
        err = BlockingError(
            reason=f"review.json 不存在或解析失败 ({adr_token})",
            current_state=(
                f"expected: .git/spec-vc-review.json\n"
                f"actual: {'不存在' if not rv_path.exists() else '非法 JSON'}\n"
                f"current staged sha12: {expected_sha12}\n"
                f"expected anchor: {expected_anchor}"
            ),
            fix_commands=[
                f'spec-vc review --mode subagent --message "<完整 commit message 含 [{adr_token}]>"',
                "git commit",
            ],
            docs_ref=["SKILL.md#commit-审查-提交", "ADR-018", "Spec-018"],
        )
        raise ValidationError(err.format())

    if record.anchor != expected_anchor:
        simple_note_hint = (
            f' --note "<审查结论，必须含 {expected_anchor}>"' if record.mode == "simple" else ""
        )
        err = BlockingError(
            reason=f"review.json.anchor 不匹配当前 staged ({adr_token})",
            current_state=(
                f"expected: {expected_anchor}\n"
                f"actual: {record.anchor}\n"
                f"原因: staged 内容自上次 review 后已变化，需重新审查"
            ),
            fix_commands=[
                f'spec-vc review --mode {record.mode} --message "<完整 commit message>"{simple_note_hint}',
            ],
            docs_ref=["ADR-018", "Spec-018"],
        )
        raise ValidationError(err.format())

    msg_path = repo_root / ".git" / COMMIT_MSG_FILENAME
    if msg_path.exists():
        if rv_path.stat().st_mtime <= msg_path.stat().st_mtime:
            rv_ts = datetime.datetime.fromtimestamp(rv_path.stat().st_mtime).astimezone()
            msg_ts = datetime.datetime.fromtimestamp(msg_path.stat().st_mtime).astimezone()
            err = BlockingError(
                reason="review.json mtime ≤ commit-msg mtime（审计证据不新鲜）",
                current_state=(
                    f"review.json mtime: {rv_ts.isoformat(timespec='seconds')}\n"
                    f"commit-msg mtime: {msg_ts.isoformat(timespec='seconds')}\n"
                    f"原因: 审计可能是历史遗留，未对应本次 commit message"
                ),
                fix_commands=[
                    f'spec-vc review --mode {record.mode} --message "<完整 commit message>"',
                ],
                docs_ref=["ADR-018", "Spec-018"],
            )
            raise ValidationError(err.format())


def run_post_tool_use(repo_root: Path, tool_name: str = "", description: str = "") -> int:
    """记录 Agent 工具调用到 subagent session log。

    输入优先级（ADR-016）：
    1. CLI 显式参数（--tool-name / --description）有值则使用
    2. CLI 参数为空且 stdin 非 tty 时，从 stdin JSON payload 提取
       tool_name 与 tool_input.description（Claude Code harness 的实际传值方式）
    3. JSON 解析失败 / 任何 IO 异常 → fail-open（return 0，不阻塞 commit）

    跳过条件：
    - hook_event_name == "PostToolUseFailure"（ADR-017）：harness 显式失败事件
    - 解析后 tool_name 为空
    - 解析后 description 为空或纯空白（ADR-013 保留）
    """
    if (not tool_name or not description) and not sys.stdin.isatty():
        try:
            raw = sys.stdin.read()
        except OSError:
            return 0
        if raw.strip():
            try:
                payload = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                return 0
            if isinstance(payload, dict):
                if payload.get("hook_event_name") == "PostToolUseFailure":
                    return 0
                if not tool_name:
                    candidate = payload.get("tool_name", "")
                    tool_name = candidate if isinstance(candidate, str) else ""
                if not description:
                    tool_input = payload.get("tool_input") or {}
                    if isinstance(tool_input, dict):
                        candidate = tool_input.get("description", "")
                        description = candidate if isinstance(candidate, str) else ""

    if not tool_name:
        return 0
    if not description.strip():
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

    if any(token.startswith("ADR-?") for token in tokens):
        raise ValidationError(HELP_SLOT)
    if len(tokens) != 1:
        raise ValidationError(HELP_MISSING)

    token = tokens[0]
    if token == "ADR-none":
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

    # [ADR-NNN] ADR-020 减法后：Spec 完整性 + review.json (anchor + mtime)
    _check_spec_readiness_for_adr(repo_root, config, adr_id)
    if not bypass_reason:
        _check_review_record(repo_root, config, adr_id)

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