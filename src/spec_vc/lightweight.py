"""ADR-018: [ADR-none] 量化判定。

判定规则（全部命中才认为是轻量改动）:
- staged files 数 ≤ config.files_max
- 全部文件路径命中 config.type_whitelist（glob 模式 / dir/** 前缀）
- 净变更行数（增 + 删）≤ config.lines_max

任一不满足 → is_lightweight=False，reasons 列出未命中规则供 BlockingError 引用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

from .config import LightweightConfig
from .gitops import staged_diff_numstat, staged_files


@dataclass(slots=True)
class LightweightMetrics:
    files_count: int
    lines_delta: int
    unmatched_files: list[str] = field(default_factory=list)


@dataclass(slots=True)
class LightweightDetectionResult:
    is_lightweight: bool
    reasons: list[str]
    metrics: LightweightMetrics


def _matches_any(filepath: str, patterns: list[str]) -> bool:
    """fnmatch + dir/** 前缀支持。"""
    for p in patterns:
        if fnmatch(filepath, p):
            return True
        if p.endswith("/**"):
            prefix = p[:-3].rstrip("/")
            if prefix and (filepath == prefix or filepath.startswith(prefix + "/")):
                return True
    return False


def detect_lightweight_change(
    repo_root: Path, config: LightweightConfig
) -> LightweightDetectionResult:
    files = staged_files(repo_root)
    files_count = len(files)
    numstat = staged_diff_numstat(repo_root)
    lines_delta = sum(add + delete for add, delete, _ in numstat)

    unmatched: list[str] = [f for f in files if not _matches_any(f, config.type_whitelist)]

    reasons: list[str] = []
    if files_count > config.files_max:
        reasons.append(f"files_count: {files_count} > {config.files_max}")
    if lines_delta > config.lines_max:
        reasons.append(f"lines_delta: {lines_delta} > {config.lines_max}")
    if unmatched:
        reasons.append(f"unmatched_files: {unmatched}")

    metrics = LightweightMetrics(
        files_count=files_count,
        lines_delta=lines_delta,
        unmatched_files=unmatched,
    )
    return LightweightDetectionResult(
        is_lightweight=not reasons,
        reasons=reasons,
        metrics=metrics,
    )
