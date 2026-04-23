from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import tomllib


@dataclass(slots=True)
class ExemptionConfig:
    enabled: bool = True
    allowed_paths: list[str] = field(default_factory=lambda: ["README.md", "docs/**", ".github/**"])
    blocked_paths: list[str] = field(default_factory=lambda: ["src/**", "lib/**", "core/**"])
    allowed_extensions: list[str] = field(default_factory=lambda: [".md", ".txt", ".rst", ".gitignore"])
    max_changed_lines: int = 40


@dataclass(slots=True)
class ProjectConfig:
    adr_dir: str = "doc/arch"
    strict: bool = True


@dataclass(slots=True)
class Config:
    project: ProjectConfig = field(default_factory=ProjectConfig)
    exemption: ExemptionConfig = field(default_factory=ExemptionConfig)


def load_config(repo_root: Path) -> Config:
    config = Config()
    path = repo_root / ".spec-vc.toml"
    if path.exists():
        data = tomllib.loads(path.read_text())
        project = data.get("project", {})
        exemption = data.get("exemption", {})
        config.project.adr_dir = str(project.get("adr_dir", config.project.adr_dir))
        config.project.strict = bool(project.get("strict", config.project.strict))
        config.exemption.enabled = bool(exemption.get("enabled", config.exemption.enabled))
        config.exemption.allowed_paths = list(exemption.get("allowed_paths", config.exemption.allowed_paths))
        config.exemption.blocked_paths = list(exemption.get("blocked_paths", config.exemption.blocked_paths))
        config.exemption.allowed_extensions = list(exemption.get("allowed_extensions", config.exemption.allowed_extensions))
        config.exemption.max_changed_lines = int(exemption.get("max_changed_lines", config.exemption.max_changed_lines))
    env_adr_dir = os.getenv("ADR_DIR")
    if env_adr_dir:
        config.project.adr_dir = env_adr_dir
    return config
