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
from .lightweight import detect_lightweight_change
from .review import read_review, review_path


ADR_TOKEN_RE = re.compile(r"\[(ADR-none|ADR-\?+|ADR-\d{3,})\]")
EXACT_NONE_RE = re.compile(r"\[ADR-none\]")
EXACT_NUM_RE = re.compile(r"\[ADR-(\d{3,})\]")

BYPASS_LOG_FILENAME = "spec-vc-bypass.log"
ACTIVE_FILE_NAME = "_active.md"
PLAN_DIR_NAME = "plans"

IMPLEMENT_READY_OR_LATER = {"implement-ready", "validate", "close"}


def _load_stage_for_adr(adr_dir: Path, adr_id: str) -> str | None:
    """按 adr_id 路由读取变更 stage。

    优先级：
    1. _active.md 的 ADR 字段匹配 adr_id → 用 active.stage
    2. 否则从 plans/ADR-{adr_id}-plan-*.md 取编号最大的，读 - **Stage**: 字段
    3. 该 ADR 无 plan 文件 → 返回 None（流程已结束，不阻塞）
    """
    plans_dir = adr_dir / PLAN_DIR_NAME
    active_path = plans_dir / ACTIVE_FILE_NAME

    if active_path.exists():
        active_adr: str | None = None
        active_stage: str | None = None
        for line in active_path.read_text().splitlines():
            if line.startswith("- **ADR**:"):
                raw = line.split(":", 1)[1].strip()
                active_adr = raw.replace("ADR-", "")
            elif line.startswith("- **Stage**:"):
                active_stage = line.split(":", 1)[1].strip()
        if active_adr == adr_id and active_stage:
            return active_stage

    if not plans_dir.exists():
        return None
    pattern = re.compile(rf"^ADR-{re.escape(adr_id)}-plan-(\d+)\.md$")
    candidates: list[tuple[int, Path]] = []
    for path in plans_dir.iterdir():
        m = pattern.match(path.name)
        if m:
            candidates.append((int(m.group(1)), path))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    _, latest_plan = candidates[-1]
    for line in latest_plan.read_text().splitlines():
        if line.startswith("- **Stage**:"):
            return line.split(":", 1)[1].strip()
    return None


def _check_plan_stage(repo_root: Path, config: Config, adr_id: str) -> None:
    """检查 ADR 对应的变更计划 stage ≥ implement-ready。

    使用 _load_stage_for_adr 按 adr_id 路由读取，正确处理 commit 引用 ADR-X
    而 active 是 ADR-Y 的场景（fallback 到 plan 文件）。
    无 plan 文件（流程已走完或 ADR 未启动 plan）→ 不阻塞。
    """
    adr_dir = repo_root / config.project.adr_dir
    stage = _load_stage_for_adr(adr_dir, adr_id)
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

    if record.mode == "simple" and record.anchor not in record.note:
        err = BlockingError(
            reason="simple 模式 review.json.note 不含 anchor 子串",
            current_state=(
                f"anchor: {record.anchor}\n"
                f"note: {record.note}\n"
                f"原因: simple 模式要求 AI 在 note 中复述 anchor，强制至少读一次 staged diff 指纹"
            ),
            fix_commands=[
                f'spec-vc review --mode simple --message "<commit msg>" --note "<结论，必须含 {record.anchor}>"',
            ],
            docs_ref=["ADR-018", "Spec-018"],
        )
        raise ValidationError(err.format())

    if config.lightweight.require_user_verified and not record.verified:
        err = BlockingError(
            reason="require_user_verified=true 但 review.json.verified=false",
            current_state=(
                f"review.json.verified: {record.verified}\n"
                f"config.lightweight.require_user_verified: True\n"
                f"原因: 配置要求用户实际验证后才能 commit"
            ),
            fix_commands=[
                f'spec-vc review --verified --mode {record.mode} --message "<commit msg>"',
            ],
            docs_ref=["ADR-018", "Spec-018"],
        )
        raise ValidationError(err.format())


def _check_lightweight(repo_root: Path, config: Config) -> None:
    """[ADR-none] 量化判定（ADR-018）。未命中即阻塞。"""
    result = detect_lightweight_change(repo_root, config.lightweight)
    if result.is_lightweight:
        return

    state_lines = [
        f"files_count: {result.metrics.files_count} (limit {config.lightweight.files_max})",
        f"lines_delta: {result.metrics.lines_delta} (limit {config.lightweight.lines_max})",
        f"unmatched_files: {result.metrics.unmatched_files}",
        f"unmet rules: {result.reasons}",
    ]
    err = BlockingError(
        reason="[ADR-none] 未命中量化轻量规则",
        current_state="\n".join(state_lines),
        fix_commands=[
            "升级 commit: 改 subject 含具体 [ADR-NNN]，并按 spec-vc 流程走 spec-vc review",
            "或拆分本次 commit 至轻量阈值内（默认 files≤5 + lines≤50 + 全部命中 type_whitelist）",
            "紧急情况绕过: SPEC_VC_BYPASS=<原因> git commit ...",
        ],
        docs_ref=["ADR-018", "Spec-018", "SKILL.md#轻量路径"],
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
        if not bypass_reason:
            _check_lightweight(repo_root, config)
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

    # [ADR-NNN] 额外检查（ADR-018：用 review.json 替代 session log + anchor 间接证据）
    _check_plan_stage(repo_root, config, adr_id)
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