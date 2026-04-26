from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from datetime import date

from ._sections import extract_section, validate_title
from .errors import ValidationError


SPEC_HEADER_RE = re.compile(
    r"^#\s*Spec-(?P<id>\d+)[:：]\s*(?P<title>.+?)\s*$",
    re.MULTILINE,
)
STATUS_RE = re.compile(
    r"^-\s*\*\*Status\*\*:\s*(?P<status>.+?)\s*$",
    re.MULTILINE,
)
DATE_RE = re.compile(
    r"^-\s*\*\*Date\*\*:\s*(?P<date>.+?)\s*$",
    re.MULTILINE,
)
ADR_REF_RE = re.compile(
    r"^-\s*\*\*ADR\*\*:\s*(?P<adr_ref>.+?)\s*$",
    re.MULTILINE,
)

@dataclass(slots=True)
class Spec:
    spec_id: str
    title: str
    status: str
    adr_ref: str
    author: str
    spec_date: str | None
    path: Path
    overview: str = ""
    interface_contract: str = ""
    data_shape: str = ""
    behavior_rules: str = ""
    non_goals: str = ""
    references: str = ""


ALLOWED_REFERENCE_STATUSES = {"Draft", "Reviewed", "Implemented"}


def specs_root(repo_root: Path, spec_cfg_dir: str) -> Path:
    return repo_root / spec_cfg_dir


def spec_basedir(specs_root: Path, spec_id: str) -> Path:
    return specs_root / spec_id


def dev_doc_path(specs_root: Path, spec_id: str) -> Path:
    return spec_basedir(specs_root, spec_id) / "dev-doc.md"



def parse_spec(path: Path) -> Spec:
    text = path.read_text()
    header = SPEC_HEADER_RE.search(text)
    if not header:
        raise ValidationError(f"Spec 文件头格式非法: {path}")
    status_match = STATUS_RE.search(text)
    if not status_match:
        raise ValidationError(f"Spec Status 缺失或格式非法: {path}")
    date_match = DATE_RE.search(text)
    adr_match = ADR_REF_RE.search(text)

    return Spec(
        spec_id=header.group("id"),
        title=header.group("title").strip(),
        status=status_match.group("status").strip(),
        adr_ref=adr_match.group("adr_ref").strip() if adr_match else "未关联",
        author="",
        spec_date=date_match.group("date").strip() if date_match else None,
        path=path,
        overview=extract_section(text, "概述"),
        interface_contract=extract_section(text, "接口契约"),
        data_shape=extract_section(text, "数据形状"),
        behavior_rules=extract_section(text, "行为规则"),
        non_goals=extract_section(text, "非目标"),
        references=extract_section(text, "References"),
    )


def list_specs(specs_root: Path) -> list[Spec]:
    if not specs_root.exists():
        return []
    items: list[Spec] = []
    for subdir in sorted(specs_root.iterdir()):
        if not subdir.is_dir():
            continue
        if not re.match(r"^\d{3,}$", subdir.name):
            continue
        doc_path = subdir / "dev-doc.md"
        if doc_path.exists():
            items.append(parse_spec(doc_path))
    return sorted(items, key=lambda item: int(item.spec_id))


def next_spec_id(specs_root: Path) -> str:
    if not specs_root.exists():
        return "001"
    max_id = 0
    for subdir in specs_root.iterdir():
        if not subdir.is_dir():
            continue
        match = re.match(r"^(\d{3,})$", subdir.name)
        if not match:
            continue
        max_id = max(max_id, int(match.group(1)))
    return f"{max_id + 1:03d}"


def validate_title(title: str) -> str:
    if not title.strip():
        raise ValidationError("Spec 标题不能为空")
    if "\n" in title or "\r" in title:
        raise ValidationError("Spec 标题不能包含换行")
    return title.strip()


def render_dev_doc(template: str, spec_id: str, title: str, author: str, adr_ref: str) -> str:
    rendered = template.replace("{{NUMBER}}", spec_id)
    rendered = rendered.replace("{{TITLE}}", title)
    rendered = rendered.replace("{{DATE}}", date.today().isoformat())
    rendered = rendered.replace("{{AUTHOR}}", author)
    rendered = rendered.replace("{{ADR_REF}}", adr_ref)
    return rendered


def ensure_referenceable(spec: Spec, expected_id: str) -> None:
    if spec.spec_id != expected_id:
        raise ValidationError(
            f"Spec 文件编号与文件名不一致: 期望 {expected_id}, 实际 {spec.spec_id}"
        )
    if spec.status not in ALLOWED_REFERENCE_STATUSES:
        raise ValidationError(
            f'Spec-{expected_id} 状态为 "{spec.status}"，不允许被引用'
        )


def create_spec(
    specs_root: Path,
    spec_id: str,
    title: str,
    author: str,
    adr_ref: str,
    template_dir: Path,
) -> Path:
    basedir = spec_basedir(specs_root, spec_id)
    basedir.mkdir(parents=True, exist_ok=True)

    dev_doc_tpl = template_dir / "dev-doc.md"
    doc_content = render_dev_doc(
        dev_doc_tpl.read_text(), spec_id, title, author, adr_ref
    )
    (basedir / "dev-doc.md").write_text(doc_content)

    for fname in ["contract.openapi.yaml", "schema.json", "behavior.feature"]:
        tpl = template_dir / fname
        if tpl.exists():
            content = (
                tpl.read_text()
                .replace("{{TITLE}}", title)
                .replace("{{DESCRIPTION}}", f"Spec-{spec_id}: {title}")
            )
        else:
            content = ""
        (basedir / fname).write_text(content)

    return basedir / "dev-doc.md"


def list_formal_files(specs_root: Path, spec_id: str) -> list[str]:
    basedir = spec_basedir(specs_root, spec_id)
    if not basedir.exists():
        return []
    files: list[str] = []
    for fname in ["contract.openapi.yaml", "schema.json", "behavior.feature"]:
        path = basedir / fname
        if path.exists() and path.stat().st_size > 0:
            files.append(fname)
    return files


def formalize_spec(
    specs_root: Path,
    spec_id: str,
    formal_type: str,
) -> Path:
    basedir = spec_basedir(specs_root, spec_id)
    doc_path = basedir / "dev-doc.md"
    if not doc_path.exists():
        raise ValidationError(f"Spec 不存在: Spec-{spec_id}")

    spec = parse_spec(doc_path)

    formal_map: dict[str, tuple[str, str]] = {
        "openapi": ("contract.openapi.yaml", spec.interface_contract),
        "jsonschema": ("schema.json", spec.data_shape),
        "gherkin": ("behavior.feature", spec.behavior_rules),
    }

    if formal_type not in formal_map:
        raise ValidationError(
            f"不支持的形式化类型: {formal_type}，可选: openapi, jsonschema, gherkin"
        )

    fname, content = formal_map[formal_type]
    out_path = basedir / fname
    if not content.strip() or content.strip() == "待补充":
        raise ValidationError(
            f"Spec-{spec_id} 的对应区块为空（待补充），无法生成形式化文件"
        )
    out_path.write_text(content.strip() + "\n")
    return out_path
