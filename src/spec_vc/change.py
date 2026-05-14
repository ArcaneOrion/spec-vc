from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import fnmatch
import re

from ._sections import replace_section as _replace_section
from .adr import list_adrs, parse_adr
from .config import AdrRequiredConfig
from .errors import UsageError, ValidationError

ACTIVE_FILE_NAME = "_active.md"
PLAN_DIR_NAME = "plans"
ACTIVE_STAGE_VALUES = {"discover", "clarify", "plan", "implement-ready", "validate", "close"}
_PLAN_ID_RE = re.compile(r"ADR-\d{3,}-plan-\d{3}$")
FIELD_LABELS = {
    "motivation": "动机与上下文",
    "boundary": "目标与边界",
    "design": "设计与架构",
    "implementation": "实现路径",
    "verification": "验证与测试",
    "rollback": "风险与回滚",
}
SECTION_BY_FIELD = {
    "motivation": "Motivation and Context",
    "boundary": "Goals and Boundaries",
    "design": "Design and Architecture",
    "implementation": "Implementation Path",
    "verification": "Verification and Testing",
    "rollback": "Risks and Rollback",
}
REQUIRED_CLARIFY_FIELDS = tuple(FIELD_LABELS.keys())


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
    motivation: str = ""
    boundary: str = ""
    design: str = ""
    implementation: str = ""
    verification: str = ""
    rollback: str = ""


@dataclass(slots=True)
class NextQuestion:
    stage: str
    missing_fields: list[str]


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
    repo_root = adr_dir.parent.parent
    resolved = (repo_root / active.plan_path).resolve()
    if not str(resolved).startswith(str(repo_root.resolve()) + "/"):
        raise ValidationError(f"plan_path 指向仓库外: {active.plan_path}")
    return resolved


def _replace_meta(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^- \*\*{re.escape(key)}\*\*:\s*.*$", re.M)
    if not pattern.search(text):
        raise ValidationError(f"计划文件缺少元数据: {key}")
    return pattern.sub(f"- **{key}**: {value}", text, count=1)


def _read_section(text: str, section: str) -> str:
    pattern = re.compile(rf"## {re.escape(section)}\n\n(.*?)(?=\n## |\Z)", re.S)
    match = pattern.search(text)
    if not match:
        raise ValidationError(f"计划文件缺少区块: {section}")
    return match.group(1).strip()


def _load_plan(path: Path) -> str:
    if not path.exists():
        raise UsageError(f"计划文件不存在: {path}")
    return path.read_text()


def _save_plan(path: Path, text: str) -> None:
    path.write_text(text)


def next_question(adr_dir: Path) -> NextQuestion:
    active = load_active(adr_dir)
    if active is None:
        raise UsageError("当前没有 active change")
    path = plan_path(adr_dir, active)
    text = _load_plan(path)
    missing: list[str] = []
    for field in REQUIRED_CLARIFY_FIELDS:
        value = _read_section(text, SECTION_BY_FIELD[field])
        if value in {"待补充", "待澄清", "", "待补充字段"} or value.startswith("待补充字段"):
            missing.append(field)
    return NextQuestion(stage=active.stage, missing_fields=missing)


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
            "## Clarification History",
            "",
            "待补充",
            "",
            "## Motivation and Context",
            "",
            "待补充",
            "",
            "## Goals and Boundaries",
            "",
            "待补充",
            "",
            "## Design and Architecture",
            "",
            "待补充",
            "",
            "## Implementation Path",
            "",
            "待补充",
            "",
            "## Verification and Testing",
            "",
            "待补充",
            "",
            "## Risks and Rollback",
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
            "## Closure Summary",
            "",
            "待补充",
            "",
            "## References",
            "",
            "- **Commits**: 待补充",
            "- **Plan**: 待补充",
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


def clarify_plan(adr_dir: Path, clar: ClarifyInput) -> tuple[Path, list[str]]:
    active = load_active(adr_dir)
    if active is None:
        raise UsageError("当前没有 active change")
    path = plan_path(adr_dir, active)
    text = _load_plan(path)
    history = "\n".join(
        [
            f"- 动机与上下文: {clar.motivation or '[missing]'}",
            f"- 目标与边界: {clar.boundary or '[missing]'}",
            f"- 设计与架构: {clar.design or '[missing]'}",
            f"- 实现路径: {clar.implementation or '[missing]'}",
            f"- 验证与测试: {clar.verification or '[missing]'}",
            f"- 风险与回滚: {clar.rollback or '[missing]'}",
        ]
    )
    text = _replace_section(text, "Clarification History", history)
    for field in REQUIRED_CLARIFY_FIELDS:
        value = getattr(clar, field)
        if value.strip():
            text = _replace_section(text, SECTION_BY_FIELD[field], value)
    _save_plan(path, text)
    question = next_question(adr_dir)
    if question.missing_fields:
        text = _load_plan(path)
        text = _replace_section(text, "Clarification", "待补充字段: " + ", ".join(question.missing_fields))
        text = _replace_meta(text, "Stage", "clarify")
        _save_plan(path, text)
        update_active_stage(adr_dir, "clarify")
        return path, question.missing_fields
    text = _load_plan(path)
    summary = "\n".join([f"- {FIELD_LABELS[field]}: {_read_section(text, SECTION_BY_FIELD[field])}" for field in REQUIRED_CLARIFY_FIELDS])
    text = _replace_section(text, "Clarification", summary)
    text = _replace_meta(text, "Stage", "plan")
    _save_plan(path, text)
    update_active_stage(adr_dir, "plan")
    return path, []


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
    next_stage_value = "implement-ready" if phase == "pre" else "validate"
    text = _replace_meta(text, "Stage", next_stage_value)
    _save_plan(path, text)
    update_active_stage(adr_dir, next_stage_value)
    return path


def _commit_refs_from_git(repo_root: Path, adr_id: str) -> list[str]:
    import subprocess
    proc = subprocess.run(["git", "log", "--format=%h %s"], cwd=repo_root, text=True, capture_output=True)
    if proc.returncode != 0:
        return []
    needle = f"[ADR-{adr_id}]"
    refs = []
    for line in proc.stdout.splitlines():
        if needle in line:
            refs.append(line.strip())
    return refs[:10]


def append_adr_summary(repo_root: Path, adr_dir: Path, active: ActiveChange) -> Path:
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
    commits = _commit_refs_from_git(repo_root, active.adr_id)
    commits_line = "; ".join(commits) if commits else "待补充"
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
        adr_text = re.sub(
            r"## Implementation Plans\n\n.*?(?=\n## |\Z)",
            lambda _m: block.strip() + "\n",
            adr_text,
            flags=re.S,
        )
    else:
        if "## References" in adr_text:
            adr_text = adr_text.replace("## References", block + "## References", 1)
        else:
            adr_text = adr_text.rstrip() + "\n\n" + block
    adr_text = re.sub(
        r"(- \*\*Commits\*\*: ).*$",
        lambda m: m.group(1) + commits_line,
        adr_text,
        flags=re.M,
    )
    adr_path.write_text(adr_text)
    return adr_path


def close_change(repo_root: Path, adr_dir: Path, summary: str) -> tuple[Path, Path]:
    active = load_active(adr_dir)
    if active is None:
        raise UsageError("当前没有 active change")
    plan = plan_path(adr_dir, active)
    text = _load_plan(plan)
    if not summary.strip():
        raise ValidationError("close summary 不能为空")
    text = _replace_section(text, "Closure Summary", summary)
    text = _replace_section(text, "References", f"- **Commits**: 待从 git 自动采集\n- **Plan**: {plan.relative_to(adr_dir.parent.parent)}")
    text = _replace_meta(text, "Stage", "close")
    _save_plan(plan, text)
    active.stage = "close"
    active.updated_at = datetime.now().isoformat(timespec="seconds")
    adr_path = append_adr_summary(repo_root, adr_dir, active)
    clear_active(adr_dir)
    return plan, adr_path


def infer_adr_required(paths: list[str], prompt: str, config: AdrRequiredConfig) -> tuple[bool, str]:
    prompt_l = prompt.lower()
    if any(any(fnmatch.fnmatch(p, pat) for pat in config.code_paths) for p in paths):
        return True, "命中代码/接口路径"
    if any(keyword.lower() in prompt_l for keyword in config.keywords):
        return True, "命中需要 ADR 的语义关键词"
    if paths and all(any(fnmatch.fnmatch(p, pat) for pat in config.doc_only_paths) or any(p.endswith(ext) for ext in config.doc_only_extensions) for p in paths):
        return False, "仅命中文档路径"
    if config.default_conservative and (paths or prompt.strip()):
        return True, "按保守策略需要 ADR"
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


def read_plan_content(adr_dir: Path, plan_id: str | None = None) -> str:
    """读取 Plan 文件内容，用于 show 命令。

    如果 plan_id 为 None，读取当前活跃变更的 plan。
    """
    if plan_id is None:
        active = load_active(adr_dir)
        if active is None:
            raise UsageError("当前没有 active change")
        path = plan_path(adr_dir, active)
    else:
        if not _PLAN_ID_RE.match(plan_id):
            raise ValidationError(f"无效的 plan ID: {plan_id!r}")
        path = plans_dir(adr_dir) / f"{plan_id}.md"
    if not path.exists():
        raise UsageError(f"计划文件不存在: {path}")
    return path.read_text()


def read_active_change_context(adr_dir: Path) -> str:
    """读取当前活跃变更的完整上下文（active + plan），用于 show change 命令。"""
    active = load_active(adr_dir)
    if active is None:
        raise UsageError("当前没有 active change")

    parts: list[str] = []
    parts.append(render_active(active))
    parts.append("")

    plan = plan_path(adr_dir, active)
    if plan.exists():
        parts.append("---\n")
        parts.append(plan.read_text())

    return "\n".join(parts)
