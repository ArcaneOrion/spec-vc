from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re

from .adr import ADR, list_adrs, parse_adr
from .errors import ValidationError
from .gitops import run_git


ADR_REF_RE = re.compile(r"\[ADR-(\d{3,})\]")
SUPERSEDED_RE = re.compile(r"^Superseded by ADR-(\d{3,})$")


@dataclass(slots=True)
class StatusReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CommitRef:
    commit_hash: str
    short_hash: str
    subject: str
    adr_ids: list[str]


def collect_commit_refs(repo_root: Path, rev_range: str | None = None) -> list[CommitRef]:
    args = ["log", "--format=%H%x09%h%x09%s"]
    if rev_range:
        args.append(rev_range)
    out = run_git(repo_root, *args)
    refs: list[CommitRef] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        commit_hash, short_hash, subject = line.split("\t", 2)
        refs.append(CommitRef(commit_hash, short_hash, subject, ADR_REF_RE.findall(subject)))
    return refs


def build_status(repo_root: Path, adr_dir: Path, rev_range: str | None = None) -> StatusReport:
    report = StatusReport()
    adrs = list_adrs(adr_dir)
    adr_map = {adr.adr_id: adr for adr in adrs}
    commit_refs = collect_commit_refs(repo_root, rev_range=rev_range)

    referenced_ids: dict[str, list[CommitRef]] = {}
    for ref in commit_refs:
        for adr_id in ref.adr_ids:
            referenced_ids.setdefault(adr_id, []).append(ref)

    for adr_id, refs in sorted(referenced_ids.items(), key=lambda item: int(item[0])):
        if adr_id not in adr_map:
            for ref in refs:
                report.errors.append(f"幽灵引用: ADR-{adr_id} <- {ref.short_hash} {ref.subject}")

    for adr in adrs:
        superseded = SUPERSEDED_RE.match(adr.status)
        if superseded and superseded.group(1) not in adr_map:
            report.errors.append(f"状态漂移: ADR-{adr.adr_id} 指向不存在的 ADR-{superseded.group(1)}")

        refs = referenced_ids.get(adr.adr_id, [])
        if not refs:
            if adr.status == "Proposed":
                report.warnings.append(f"孤儿 ADR(提议中): ADR-{adr.adr_id} {adr.title}")
            elif adr.status == "Accepted":
                report.warnings.append(f"孤儿 ADR(已接受): ADR-{adr.adr_id} {adr.title}")

        missing_commits = [commit for commit in adr.references_commits if commit not in {r.commit_hash for r in refs} and commit not in {r.short_hash for r in refs}]
        if missing_commits:
            report.warnings.append(f"引用不一致: ADR-{adr.adr_id} 在 References.Commits 中记录了未在 git log 中匹配到的 commit: {', '.join(missing_commits)}")
    return report
