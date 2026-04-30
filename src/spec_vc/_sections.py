from __future__ import annotations

import re
from .errors import ValidationError


SECTION_RE = re.compile(
    r"({section_pattern})\n\n(.*?)(?=\n## |\Z)",
    re.S,
)


def _section_pattern(name: str) -> str:
    return rf"## {re.escape(name)}"


def extract_section(text: str, section_name: str) -> str:
    pattern = _section_pattern(section_name)
    compiled = re.compile(
        rf"({pattern}\n(?:<!--.*?-->\n)*\n)(.*?)(?=\n## |\Z)",
        re.S,
    )
    match = compiled.search(text)
    if not match:
        return ""
    return match.group(2).strip()


def replace_section(text: str, section_name: str, body: str) -> str:
    pattern = _section_pattern(section_name)
    compiled = re.compile(
        rf"({pattern}\n(?:<!--.*?-->\n)*\n)(.*?)(?=\n## |\Z)",
        re.S,
    )
    replacement = rf"\g<1>{body.strip()}\n\n"
    if not compiled.search(text):
        raise ValidationError(f"计划文件缺少区块: {section_name}")
    return compiled.sub(replacement, text, count=1)


def validate_title(title: str, label: str = "标题") -> str:
    if not title.strip():
        raise ValidationError(f"{label}不能为空")
    if "\n" in title or "\r" in title:
        raise ValidationError(f"{label}不能包含换行")
    return title.strip()
