from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
import re

from .change import load_active, plan_path, plans_dir
from .config import Config
from .spec import list_specs, spec_basedir, specs_root as get_specs_root


BASELINE_VERSION = 1
FORMAL_SPEC_FILES = ("contract.openapi.yaml", "schema.json", "behavior.feature")


@dataclass(slots=True)
class BaselineFile:
    path: str
    kind: str
    exists: bool
    sha256: str | None


@dataclass(slots=True)
class DocumentBaseline:
    version: int
    adr_token: str
    files: list[BaselineFile]

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "adr_token": self.adr_token,
            "files": [asdict(item) for item in self.files],
        }


@dataclass(slots=True)
class BaselineMismatch:
    path: str
    kind: str
    expected_exists: bool
    actual_exists: bool
    expected_sha256: str | None
    actual_sha256: str | None


def _repo_relative(repo_root: Path, path: Path) -> str:
    resolved = path.resolve()
    root = repo_root.resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError(f"baseline path escapes repo: {path}") from exc


def _hash_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _baseline_file(repo_root: Path, path: Path, kind: str) -> BaselineFile:
    return BaselineFile(
        path=_repo_relative(repo_root, path),
        kind=kind,
        exists=path.exists(),
        sha256=_hash_file(path),
    )


def _latest_plan_for_adr(adr_dir: Path, adr_id: str) -> Path | None:
    pattern = re.compile(rf"^ADR-{re.escape(adr_id)}-plan-(\d+)\.md$")
    candidates: list[tuple[int, Path]] = []
    for path in plans_dir(adr_dir).glob(f"ADR-{adr_id}-plan-*.md"):
        match = pattern.match(path.name)
        if match:
            candidates.append((int(match.group(1)), path))
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item[0])[-1][1]


def _selected_plan(repo_root: Path, adr_dir: Path, adr_id: str) -> Path | None:
    active = load_active(adr_dir)
    if active is not None and active.adr_id == adr_id:
        return plan_path(adr_dir, active)
    latest = _latest_plan_for_adr(adr_dir, adr_id)
    if latest is None:
        return None
    return (repo_root / _repo_relative(repo_root, latest)).resolve()


def build_document_baseline(repo_root: Path, config: Config, adr_token: str) -> dict | None:
    if not re.fullmatch(r"ADR-\d{3,}", adr_token):
        return None

    adr_id = adr_token.removeprefix("ADR-")
    adr_dir = repo_root / config.project.adr_dir
    files: list[BaselineFile] = []

    files.append(_baseline_file(repo_root, adr_dir / f"adr-{adr_id}.md", "adr"))

    selected_plan = _selected_plan(repo_root, adr_dir, adr_id)
    if selected_plan is not None:
        files.append(_baseline_file(repo_root, selected_plan, "plan"))

    root = get_specs_root(repo_root, config.spec.dir)
    for spec in list_specs(root):
        if spec.adr_ref != adr_token:
            continue
        basedir = spec_basedir(root, spec.spec_id)
        files.append(_baseline_file(repo_root, basedir / "dev-doc.md", "spec-dev-doc"))
        for fname in FORMAL_SPEC_FILES:
            files.append(_baseline_file(repo_root, basedir / fname, "spec-formal"))

    files.sort(key=lambda item: (item.path, item.kind))
    baseline = DocumentBaseline(
        version=BASELINE_VERSION,
        adr_token=adr_token,
        files=files,
    )
    return baseline.to_dict()


def compare_document_baseline(
    repo_root: Path,
    config: Config,
    expected: dict | None,
    adr_token: str,
) -> list[BaselineMismatch]:
    if not expected:
        return []
    if expected.get("version") != BASELINE_VERSION:
        return []
    if expected.get("adr_token") != adr_token:
        return []

    actual = build_document_baseline(repo_root, config, adr_token)
    if actual is None:
        return []

    expected_files = {
        str(item.get("path")): item
        for item in expected.get("files", [])
        if isinstance(item, dict) and item.get("path")
    }
    actual_files = {
        str(item.get("path")): item
        for item in actual.get("files", [])
        if isinstance(item, dict) and item.get("path")
    }

    mismatches: list[BaselineMismatch] = []
    for path in sorted(set(expected_files) | set(actual_files)):
        exp = expected_files.get(path)
        act = actual_files.get(path)
        if exp == act:
            continue
        mismatches.append(
            BaselineMismatch(
                path=path,
                kind=str((exp or act or {}).get("kind", "")),
                expected_exists=bool(exp.get("exists")) if exp else False,
                actual_exists=bool(act.get("exists")) if act else False,
                expected_sha256=str(exp.get("sha256")) if exp and exp.get("sha256") is not None else None,
                actual_sha256=str(act.get("sha256")) if act and act.get("sha256") is not None else None,
            )
        )
    return mismatches
