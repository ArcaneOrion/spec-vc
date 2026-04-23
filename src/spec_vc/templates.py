from __future__ import annotations

from pathlib import Path


def skill_root() -> Path:
    return Path(__file__).resolve().parents[2]


def template_path(name: str) -> Path:
    return skill_root() / "templates" / name
