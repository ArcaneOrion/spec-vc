from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import re

from .adr import list_adrs, parse_adr
from .errors import UsageError, ValidationError

ACTIVE_FILE_NAME = "_active.md"
PLAN_DIR_NAME = "plans"
ACTIVE_STAGE_VALUES = {"discover", "clarify", "plan", "implement-ready", "validate", "close"}


@dataclass(slots=True)
class ActiveChange:
    adr_id: str
    plan_path: str
    stage: str
    status: str
    updated_at: str
    summary: str


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
            "- **Stage**: plan",
            f"- **Created At**: {now}",
            f"- **Summary**: {summary}",
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
            "## Pre-Change Validation",
            "",
            "待补充",
            "",
            "## Post-Change Validation",
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
            stage="plan",
            status="active",
            updated_at=now,
            summary=summary,
        ),
    )
    return path


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
