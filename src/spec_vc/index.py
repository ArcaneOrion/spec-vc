from __future__ import annotations

from pathlib import Path

from .adr import list_adrs


def update_index(adr_dir: Path) -> None:
    readme = adr_dir / "README.md"
    text = readme.read_text()
    start = "| 编号 | 标题 | 状态 | 日期 |"
    marker = "## 状态图例"
    if marker not in text:
        return
    prefix, _, suffix = text.partition(marker)
    if start in prefix:
        prefix = prefix.split(start, 1)[0]
    rows = [
        "| 编号 | 标题 | 状态 | 日期 |",
        "|------|------|------|------|",
    ]
    for adr in list_adrs(adr_dir):
        rows.append(f"| ADR-{adr.adr_id} | {adr.title} | {adr.status} | {adr.adr_date or ''} |")
    new_text = prefix.rstrip() + "\n\n" + "\n".join(rows) + "\n\n" + marker + suffix
    readme.write_text(new_text)
