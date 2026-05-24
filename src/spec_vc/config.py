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
class LightweightConfig:
    """ADR-018: [ADR-none] 量化判定阈值 + require_user_verified 升级开关。"""
    files_max: int = 5
    lines_max: int = 50
    type_whitelist: list[str] = field(
        default_factory=lambda: ["*.md", "*.txt", "doc/**", "docs/**", ".gitignore", ".editorconfig", "*.json"]
    )
    require_user_verified: bool = False


@dataclass(slots=True)
class ReviewAssistanceConfig:
    """ADR-019: spec-vc review 审查助手输出控制。"""
    show_diff_summary: bool = True
    show_plan_context: bool = True
    show_spec_context: bool = True
    run_static_checks: bool = True
    static_check_timeout_seconds: float = 5.0
    context_summary_max_bytes: int = 4096


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
    lightweight: LightweightConfig = field(default_factory=LightweightConfig)
    review_assistance: ReviewAssistanceConfig = field(default_factory=ReviewAssistanceConfig)


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
        lightweight = data.get("lightweight", {})
        config.lightweight.files_max = _get_val("lightweight", "files_max", lightweight, config.lightweight.files_max, int)
        config.lightweight.lines_max = _get_val("lightweight", "lines_max", lightweight, config.lightweight.lines_max, int)
        config.lightweight.type_whitelist = _get_val("lightweight", "type_whitelist", lightweight, config.lightweight.type_whitelist, list)
        config.lightweight.require_user_verified = _get_val("lightweight", "require_user_verified", lightweight, config.lightweight.require_user_verified, bool)
        review_assistance = data.get("review_assistance", {})
        config.review_assistance.show_diff_summary = _get_val("review_assistance", "show_diff_summary", review_assistance, config.review_assistance.show_diff_summary, bool)
        config.review_assistance.show_plan_context = _get_val("review_assistance", "show_plan_context", review_assistance, config.review_assistance.show_plan_context, bool)
        config.review_assistance.show_spec_context = _get_val("review_assistance", "show_spec_context", review_assistance, config.review_assistance.show_spec_context, bool)
        config.review_assistance.run_static_checks = _get_val("review_assistance", "run_static_checks", review_assistance, config.review_assistance.run_static_checks, bool)
        raw_timeout = review_assistance.get("static_check_timeout_seconds", config.review_assistance.static_check_timeout_seconds)
        if not isinstance(raw_timeout, (int, float)):
            raise ValidationError(
                f".spec-vc.toml [review_assistance] static_check_timeout_seconds 类型错误: "
                f"期望 number，实际 {type(raw_timeout).__name__} (值: {raw_timeout!r})"
            )
        config.review_assistance.static_check_timeout_seconds = float(raw_timeout)
        config.review_assistance.context_summary_max_bytes = _get_val("review_assistance", "context_summary_max_bytes", review_assistance, config.review_assistance.context_summary_max_bytes, int)
    env_adr_dir = os.getenv("ADR_DIR")
    if env_adr_dir:
        config.project.adr_dir = env_adr_dir
    return config
