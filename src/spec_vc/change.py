from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import fnmatch
import re

from .adr import list_adrs, parse_adr
from .errors import UsageError, ValidationError

ACTIVE_FILE_NAME = "_active.md"
PLAN_DIR_NAME = "plans"
ACTIVE_STAGE_VALUES = {"discover", "clarify", "plan", "implement-ready", "validate", "close"}
PLAN_STAGE_VALUES = {"clarify", "plan", "implement-ready", "validate", "closed"}


@dataclass(slots=True)
class ActiveChange:
    adr_id: str
    plan_path: str
    stage: str
    status: str
    updated_at: str
    summary: str


@dataclass(slots=True)
class ClarifyInput:
    goal: str
    scope: str
    non_goals: str
    strategy: str
    risks: str
    acceptance: str


def plans_dir(adr_dir: Path) -> Path:
    return adr_dir / PLAN_DIR_NAME


def active_file(adr_dir: Path) -> Path:
    return plans_dir(adr_dir) / ACTIVE_FILE_NAME


def ensure_plan_dir(adr_dir: Path) -> Path:
    path = plans_dir(adr_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def parse_active(text: str) -> ActiveChange:
    data: dict[str, str] = {}
    for line in text.splitlines():
        if not line.startswith("- **"):
            continue
        try:
            key, value = line[4:].split("**:", 1)
        except ValueError:
            continue
        data[key.strip().lower().replace(" ", "_")] = value.strip()
    stage = data.get("stage", "")
    if stage not in ACTIVE_STAGE_VALUES:
        raise ValidationError(f"active context 阶段非法: {stage}")
    return ActiveChange(
        adr_id=data["adr"].replace("ADR-", ""),
        plan_path=data["plan"],
        stage=stage,
        status=data.get("status", "active"),
        updated_at=data.get("updated_at", ""),
        summary=data.get("summary", ""),
    )


def render_active(active: ActiveChange) -> str:
    return "\n".join(
        [
            "# spec-vc Active Change",
            "",
            f"- **ADR**: ADR-{active.adr_id}",
            f"- **Plan**: {active.plan_path}",
            f"- **Stage**: {active.stage}",
            f"- **Status**: {active.status}",
            f"- **Updated At**: {active.updated_at}",
            f"- **Summary**: {active.summary}",
            "",
            "该文件用于 spec-vc 子系统恢复当前活跃变更上下文。",
            "",
        ]
    )


def load_active(adr_dir: Path) -> ActiveChange | None:
    path = active_file(adr_dir)
    if not path.exists():
        return None
    return parse_active(path.read_text())


def save_active(adr_dir: Path, active: ActiveChange) -> Path:
    ensure_plan_dir(adr_dir)
    path = active_file(adr_dir)
    path.write_text(render_active(active))
    return path


def clear_active(adr_dir: Path) -> None:
    path = active_file(adr_dir)
    if path.exists():
        path.unlink()


def next_plan_id(adr_dir: Path, adr_id: str) -> str:
    ensure_plan_dir(adr_dir)
    max_id = 0
    for path in plans_dir(adr_dir).glob(f"ADR-{adr_id}-plan-*.md"):
        m = re.match(rf"ADR-{adr_id}-plan-(\d+).md$", path.name)
        if m:
            max_id = max(max_id, int(m.group(1)))
    return f"{max_id + 1:03d}"


def plan_path(adr_dir: Path, active: ActiveChange) -> Path:
    return adr_dir.parent.parent / active.plan_path


def _replace_section(text: str, section: str, body: str) -> str:
    pattern = re.compile(rf"(## {re.escape(section)}\n\n)(.*?)(?=\n## |\Z)", re.S)
    replacement = rf"\1{body.strip()}\n\n"
    if not pattern.search(text):
        raise ValidationError(f"计划文件缺少区块: {section}")
    return pattern.sub(replacement, text, count=1)


def _replace_meta(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^- \*\*{re.escape(key)}\*\*:\s*.*$", re.M)
    if not pattern.search(text):
        raise ValidationError(f"计划文件缺少元数据: {key}")
    return pattern.sub(f"- **{key}**: {value}", text, count=1)


def _load_plan(path: Path) -> str:
    if not path.exists():
        raise UsageError(f"计划文件不存在: {path}")
    return path.read_text()


def _save_plan(path: Path, text: str) -> None:
    path.write_text(text)


def create_plan(adr_dir: Path, adr_id: str, summary: str) -> Path:
    adr_path = adr_dir / f"adr-{adr_id}.md"
    if not adr_path.exists():
        raise UsageError(f"ADR-{adr_id} 不存在")
    adr = parse_adr(adr_path)
    plan_id = next_plan_id(adr_dir, adr_id)
    path = plans_dir(adr_dir) / f"ADR-{adr_id}-plan-{plan_id}.md"
    now = datetime.now().isoformat(timespec="seconds")
    content = "\n".join(
        [
            f"# ADR-{adr_id} 执行方案 {plan_id}",
            "",
            f"- **ADR**: ADR-{adr_id}",
            f"- **ADR Title**: {adr.title}",
            "- **Stage**: clarify",
            f"- **Created At**: {now}",
            f"- **Summary**: {summary}",
            "",
            "## Clarification",
            "",
            "待澄清",
            "",
            "## Goal",
            "",
            "待补充",
            "",
            "## Scope",
            "",
            "待补充",
            "",
            "## Non-Goals",
            "",
            "待补充",
            "",
            "## Implementation Strategy",
            "",
            "待补充",
            "",
            "## Affected Areas",
            "",
            "待补充",
            "",
            "## Acceptance Criteria",
            "",
            "待补充",
            "",
            "## Pre-Change Validation",
            "",
            "待补充",
            "",
            "## Post-Change Validation",
            "",
            "待补充",
            "",
            "## Closure Summary",
            "",
            "待补充",
            "",
            "## Risks and Rollback",
            "",
            "待补充",
            "",
            "## Checkpoints",
            "",
            "- [ ] 澄清完成",
            "- [ ] 前置验证完成",
            "- [ ] 实施完成",
            "- [ ] 后置验证完成",
            "- [ ] ADR 回填完成",
            "",
        ]
    )
    path.write_text(content)
    save_active(
        adr_dir,
        ActiveChange(
            adr_id=adr_id,
            plan_path=str(path.relative_to(adr_dir.parent.parent)),
            stage="clarify",
            status="active",
            updated_at=now,
            summary=summary,
        ),
    )
    return path


def update_active_stage(adr_dir: Path, stage: str) -> ActiveChange:
    active = load_active(adr_dir)
    if active is None:
        raise UsageError("当前没有 active change")
    if stage not in ACTIVE_STAGE_VALUES:
        raise ValidationError(f"未知 stage: {stage}")
    active.stage = stage
    active.updated_at = datetime.now().isoformat(timespec="seconds")
    save_active(adr_dir, active)
    return active


def clarify_plan(adr_dir: Path, clar: ClarifyInput) -> Path:
    active = load_active(adr_dir)
    if active is None:
        raise UsageError("当前没有 active change")
    path = plan_path(adr_dir, active)
    text = _load_plan(path)
    if not all([clar.goal.strip(), clar.scope.strip(), clar.non_goals.strip(), clar.strategy.strip(), clar.risks.strip(), clar.acceptance.strip()]):
        raise ValidationError("澄清信息不完整，goal/scope/non-goals/strategy/risks/acceptance 必填")
    summary = "\n".join(
        [
            f"- Goal: {clar.goal}",
            f"- Scope: {clar.scope}",
            f"- Non-Goals: {clar.non_goals}",
            f"- Strategy: {clar.strategy}",
            f"- Risks: {clar.risks}",
            f"- Acceptance: {clar.acceptance}",
        ]
    )
    text = _replace_section(text, "Clarification", summary)
    text = _replace_section(text, "Goal", clar.goal)
    text = _replace_section(text, "Scope", clar.scope)
    text = _replace_section(text, "Non-Goals", clar.non_goals)
    text = _replace_section(text, "Implementation Strategy", clar.strategy)
    text = _replace_section(text, "Acceptance Criteria", clar.acceptance)
    text = _replace_section(text, "Risks and Rollback", clar.risks)
    text = _replace_meta(text, "Stage", "plan")
    _save_plan(path, text)
    update_active_stage(adr_dir, "plan")
    return path


def record_validation(adr_dir: Path, phase: str, content: str) -> Path:
    active = load_active(adr_dir)
    if active is None:
        raise UsageError("当前没有 active change")
    if phase not in {"pre", "post"}:
        raise UsageError("validate phase 必须是 pre 或 post")
    if not content.strip():
        raise ValidationError("验证内容不能为空")
    path = plan_path(adr_dir, active)
    text = _load_plan(path)
    section = "Pre-Change Validation" if phase == "pre" else "Post-Change Validation"
    text = _replace_section(text, section, content)
    next_stage = "implement-ready" if phase == "pre" else "validate"
    text = _replace_meta(text, "Stage", next_stage)
    _save_plan(path, text)
    update_active_stage(adr_dir, next_stage)
    return path


def append_adr_summary(adr_dir: Path, active: ActiveChange) -> Path:
    adr_path = adr_dir / f"adr-{active.adr_id}.md"
    adr_text = adr_path.read_text()
    plan = plan_path(adr_dir, active)
    plan_text = plan.read_text()
    close_match = re.search(r"## Closure Summary\n\n(.*?)(?=\n## |\Z)", plan_text, re.S)
    pre_match = re.search(r"## Pre-Change Validation\n\n(.*?)(?=\n## |\Z)", plan_text, re.S)
    post_match = re.search(r"## Post-Change Validation\n\n(.*?)(?=\n## |\Z)", plan_text, re.S)
    summary = (close_match.group(1).strip() if close_match else "待补充").strip()
    pre = (pre_match.group(1).strip() if pre_match else "待补充").strip()
    post = (post_match.group(1).strip() if post_match else "待补充").strip()
    block = "\n".join(
        [
            "## Implementation Plans",
            "",
            f"- **Plan**: {plan.relative_to(adr_dir.parent.parent)}",
            f"- **Summary**: {summary}",
            f"- **Pre-Validation**: {pre}",
            f"- **Post-Validation**: {post}",
            "",
        ]
    )
    if "## Implementation Plans" in adr_text:
        adr_text = re.sub(r"## Implementation Plans\n\n.*?(?=\n## |\Z)", block.strip() + "\n", adr_text, flags=re.S)
    else:
        if "## References" in adr_text:
            adr_text = adr_text.replace("## References", block + "## References", 1)
        else:
            adr_text = adr_text.rstrip() + "\n\n" + block
    adr_path.write_text(adr_text)
    return adr_path


def close_change(adr_dir: Path, summary: str) -> tuple[Path, Path]:
    active = load_active(adr_dir)
    if active is None:
        raise UsageError("当前没有 active change")
    plan = plan_path(adr_dir, active)
    text = _load_plan(plan)
    if not summary.strip():
        raise ValidationError("close summary 不能为空")
    text = _replace_section(text, "Closure Summary", summary)
    text = _replace_meta(text, "Stage", "closed")
    _save_plan(plan, text)
    active.stage = "close"
    active.updated_at = datetime.now().isoformat(timespec="seconds")
    adr_path = append_adr_summary(adr_dir, active)
    clear_active(adr_dir)
    return plan, adr_path


def infer_adr_required(paths: list[str], prompt: str = "") -> tuple[bool, str]:
    prompt_l = prompt.lower()
    path_patterns_force = ["src/**", "lib/**", "core/**", "api/**", "server/**", "backend/**", "frontend/**"]
    keywords = ["架构", "接口", "行为", "状态机", "breaking", "api", "contract", "跨模块", "跨服务", "invariant"]
    doc_only_exts = (".md", ".txt", ".rst")
    if any(any(fnmatch.fnmatch(p, pat) for pat in path_patterns_force) for p in paths):
        return True, "命中代码/接口路径"
    if any(key in prompt_l for key in keywords):
        return True, "命中需要 ADR 的语义关键词"
    if paths and all(p.endswith(doc_only_exts) or p.startswith("doc/") or p.startswith("docs/") for p in paths):
        return False, "仅命中文档路径"
    if not paths and any(key in prompt_l for key in ["refactor", "redesign", "protocol", "schema"]):
        return True, "根据需求语义保守判断需要 ADR"
    return False, "未命中 ADR-required 规则"


def change_context(adr_dir: Path) -> dict[str, object]:
    ensure_plan_dir(adr_dir)
    active = load_active(adr_dir)
    adrs = list_adrs(adr_dir)
    recent = adrs[-3:]
    return {
        "active": active,
        "recent_adrs": recent,
        "plans_dir": plans_dir(adr_dir),
    }
