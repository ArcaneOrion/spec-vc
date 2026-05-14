from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import tomllib

from .errors import ValidationError


@dataclass(slots=True)
class ExemptionConfig:
    enabled: bool = True
    allowed_paths: list[str] = field(default_factory=lambda: ["README.md", "docs/**", "doc/**", ".github/**"])
    blocked_paths: list[str] = field(default_factory=lambda: ["src/**", "lib/**", "core/**"])
    allowed_extensions: list[str] = field(default_factory=lambda: [".md", ".txt", ".rst", ".gitignore"])
    max_changed_lines: int = 40
    doc_max_changed_lines: int = 500


@dataclass(slots=True)
class AdrRequiredConfig:
    code_paths: list[str] = field(default_factory=lambda: ["src/**", "lib/**", "core/**", "api/**", "server/**", "backend/**", "frontend/**"])
    doc_only_paths: list[str] = field(default_factory=lambda: ["doc/**", "docs/**", ".github/**", "README.md"])
    doc_only_extensions: list[str] = field(default_factory=lambda: [".md", ".txt", ".rst"])
    keywords: list[str] = field(default_factory=lambda: ["架构", "接口", "行为", "状态机", "breaking", "api", "contract", "跨模块", "跨服务", "invariant", "refactor", "redesign", "protocol", "schema"])
    default_conservative: bool = True


@dataclass(slots=True)
class SpecConfig:
    dir: str = "doc/arch/specs"


@dataclass(slots=True)
class ProjectConfig:
    adr_dir: str = "doc/arch"
    strict: bool = True


@dataclass(slots=True)
class Config:
    project: ProjectConfig = field(default_factory=ProjectConfig)
    exemption: ExemptionConfig = field(default_factory=ExemptionConfig)
    adr_required: AdrRequiredConfig = field(default_factory=AdrRequiredConfig)
    spec: SpecConfig = field(default_factory=SpecConfig)


def _get_val(section: str, key: str, data: dict, default: object, expected_type: type) -> object:
    value = data.get(key, default)
    if not isinstance(value, expected_type):
        raise ValidationError(
            f".spec-vc.toml [{section}] {key} 类型错误: "
            f"期望 {expected_type.__name__}，实际 {type(value).__name__} (值: {value!r})"
        )
    return value


def load_config(repo_root: Path) -> Config:
    config = Config()
    path = repo_root / ".spec-vc.toml"
    if path.exists():
        data = tomllib.loads(path.read_text())
        project = data.get("project", {})
        exemption = data.get("exemption", {})
        adr_required = data.get("adr_required", {})
        spec = data.get("spec", {})
        config.project.adr_dir = str(_get_val("project", "adr_dir", project, config.project.adr_dir, str))
        config.project.strict = _get_val("project", "strict", project, config.project.strict, bool)
        config.exemption.enabled = _get_val("exemption", "enabled", exemption, config.exemption.enabled, bool)
        config.exemption.allowed_paths = _get_val("exemption", "allowed_paths", exemption, config.exemption.allowed_paths, list)
        config.exemption.blocked_paths = _get_val("exemption", "blocked_paths", exemption, config.exemption.blocked_paths, list)
        config.exemption.allowed_extensions = _get_val("exemption", "allowed_extensions", exemption, config.exemption.allowed_extensions, list)
        config.exemption.max_changed_lines = _get_val("exemption", "max_changed_lines", exemption, config.exemption.max_changed_lines, int)
        config.exemption.doc_max_changed_lines = _get_val("exemption", "doc_max_changed_lines", exemption, config.exemption.doc_max_changed_lines, int)
        config.adr_required.code_paths = _get_val("adr_required", "code_paths", adr_required, config.adr_required.code_paths, list)
        config.adr_required.doc_only_paths = _get_val("adr_required", "doc_only_paths", adr_required, config.adr_required.doc_only_paths, list)
        config.adr_required.doc_only_extensions = _get_val("adr_required", "doc_only_extensions", adr_required, config.adr_required.doc_only_extensions, list)
        config.adr_required.keywords = _get_val("adr_required", "keywords", adr_required, config.adr_required.keywords, list)
        config.adr_required.default_conservative = _get_val("adr_required", "default_conservative", adr_required, config.adr_required.default_conservative, bool)
        config.spec.dir = str(_get_val("spec", "dir", spec, config.spec.dir, str))
    env_adr_dir = os.getenv("ADR_DIR")
    if env_adr_dir:
        config.project.adr_dir = env_adr_dir
    return config
