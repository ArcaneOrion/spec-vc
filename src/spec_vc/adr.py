from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import fnmatch
import re
from datetime import date

from .config import Config
from .errors import ValidationError


ADR_HEADER_RE = re.compile(r"^#\s*ADR-(?P<id>\d+)[:：]\s*(?P<title>.+?)\s*$", re.MULTILINE)
STATUS_RE = re.compile(r"^-\s*\*\*Status\*\*:\s*(?P<status>.+?)\s*$", re.MULTILINE)
DATE_RE = re.compile(r"^-\s*\*\*Date\*\*:\s*(?P<date>.+?)\s*$", re.MULTILINE)
REF_COMMITS_BLOCK_RE = re.compile(r"##\s*References.*?###\s*Commits\s*(?P<body>.*?)(?:\n##\s|\Z)", re.S)
REF_COMMIT_RE = re.compile(r"^-\s*(?P<hash>[0-9a-f]{7,40})\b.*$", re.MULTILINE)


@dataclass(slots=True)
class ADR:
    adr_id: str
    title: str
    status: str
    adr_date: str | None
    references_commits: list[str]
    path: Path


ALLOWED_REFERENCE_STATUSES = {"Proposed", "Accepted"}


def parse_adr(path: Path) -> ADR:
    text = path.read_text()
    header = ADR_HEADER_RE.search(text)
    if not header:
        raise ValidationError(f"ADR 文件头格式非法: {path}")
    status_match = STATUS_RE.search(text)
    if not status_match:
        raise ValidationError(f"ADR Status 缺失或格式非法: {path}")
    date_match = DATE_RE.search(text)
    refs_match = REF_COMMITS_BLOCK_RE.search(text)
    refs = REF_COMMIT_RE.findall(refs_match.group("body")) if refs_match else []
    return ADR(
        adr_id=header.group("id"),
        title=header.group("title").strip(),
        status=status_match.group("status").strip(),
        adr_date=date_match.group("date").strip() if date_match else None,
        references_commits=refs,
        path=path,
    )


def ensure_referenceable(adr: ADR, expected_id: str) -> None:
    if adr.adr_id != expected_id:
        raise ValidationError(f"ADR 文件编号与文件名不一致: 期望 {expected_id}, 实际 {adr.adr_id}")
    if adr.status not in ALLOWED_REFERENCE_STATUSES:
        raise ValidationError(f'ADR-{expected_id} 状态为 "{adr.status}"，不允许被引用')


def list_adrs(adr_dir: Path) -> list[ADR]:
    items = [parse_adr(path) for path in sorted(adr_dir.glob("adr-*.md"))]
    return sorted(items, key=lambda item: int(item.adr_id))


def next_adr_id(adr_dir: Path) -> str:
    max_id = -1
    for path in adr_dir.glob("adr-*.md"):
        match = re.match(r"adr-(\d+)\.md$", path.name)
        if not match:
            continue
        max_id = max(max_id, int(match.group(1)))
    return f"{max_id + 1:03d}"


def validate_title(title: str) -> str:
    if not title.strip():
        raise ValidationError("ADR 标题不能为空")
    if "\n" in title or "\r" in title:
        raise ValidationError("ADR 标题不能包含换行")
    return title.strip()


def render_adr(template: str, adr_id: str, title: str, author: str) -> str:
    rendered = template.replace("{{NUMBER}}", adr_id)
    rendered = rendered.replace("{{TITLE}}", title)
    rendered = rendered.replace("{{DATE}}", date.today().isoformat())
    rendered = rendered.replace("{{AUTHOR}}", author)
    rendered = rendered.replace("{{TAGS}}", "")
    return rendered


def match_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def exemption_allows(config: Config, staged_files: list[str], changed_lines: int) -> tuple[bool, str | None]:
    if not config.exemption.enabled:
        return False, "[ADR-none] 已被禁用"
    if changed_lines > config.exemption.max_changed_lines:
        return False, f"改动行数 {changed_lines} 超过豁免阈值 {config.exemption.max_changed_lines}"
    for path in staged_files:
        if match_any(path, config.exemption.blocked_paths):
            return False, f"命中禁止豁免路径: {path}"
        suffix_ok = any(path.endswith(ext) for ext in config.exemption.allowed_extensions)
        path_ok = match_any(path, config.exemption.allowed_paths)
        if not suffix_ok and not path_ok:
            return False, f"文件不在允许豁免范围内: {path}"
    return True, None
