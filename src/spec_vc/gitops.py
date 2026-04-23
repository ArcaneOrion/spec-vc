from __future__ import annotations

from pathlib import Path
import subprocess

from .errors import ValidationError


def run_git(repo_root: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    if check and proc.returncode != 0:
        raise ValidationError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout


def repo_root_from(path: Path) -> Path:
    proc = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=path,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise ValidationError("当前目录不在 git 仓库内")
    return Path(proc.stdout.strip())


def staged_files(repo_root: Path) -> list[str]:
    out = run_git(repo_root, "diff", "--cached", "--name-only")
    return [line for line in out.splitlines() if line.strip()]


def staged_diff_numstat(repo_root: Path) -> list[tuple[int, int, str]]:
    out = run_git(repo_root, "diff", "--cached", "--numstat")
    rows: list[tuple[int, int, str]] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        added, deleted, path = line.split("\t", 2)
        add_n = 0 if added == "-" else int(added)
        del_n = 0 if deleted == "-" else int(deleted)
        rows.append((add_n, del_n, path))
    return rows
