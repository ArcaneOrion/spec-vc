from __future__ import annotations

import subprocess
from pathlib import Path


def run(repo: Path, *args: str, check: bool = False):
    import os
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, "PYTHONPATH": str(root / "src")}
    proc = subprocess.run(
        [__import__("sys").executable, "-m", "spec_vc.cli", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        env=env,
    )
    if check and proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout)
    return proc


def init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)
    (repo / "doc" / "arch").mkdir(parents=True)
    root = Path(__file__).resolve().parents[2]
    (repo / ".spec-vc.toml").write_text((root / ".spec-vc.toml").read_text())
    (repo / "doc" / "arch" / "README.md").write_text((root / "templates" / "index.md").read_text())
    seed = (root / "templates" / "seed-adr-000.md").read_text().replace("{{DATE}}", "2026-04-23").replace("{{AUTHOR}}", "test")
    (repo / "doc" / "arch" / "adr-000.md").write_text(seed)
    return repo


def test_adr_new_updates_index(tmp_path: Path):
    repo = init_repo(tmp_path)
    proc = run(repo, "adr", "new", "新的决策", check=True)
    assert "adr-001.md" in proc.stdout
    assert (repo / "doc" / "arch" / "adr-001.md").exists()
    readme = (repo / "doc" / "arch" / "README.md").read_text()
    assert "ADR-001" in readme


def test_commit_msg_rejects_multiple_tokens(tmp_path: Path):
    repo = init_repo(tmp_path)
    msg = repo / "msg.txt"
    msg.write_text("feat: x [ADR-000] [ADR-999]\n")
    proc = run(repo, "hook", "commit-msg", str(msg))
    assert proc.returncode != 0


def test_commit_msg_rejects_adr_none_for_code_change(tmp_path: Path):
    repo = init_repo(tmp_path)
    src = repo / "src"
    src.mkdir()
    (src / "main.py").write_text("print('x')\n")
    subprocess.run(["git", "add", "src/main.py"], cwd=repo, check=True)
    msg = repo / "msg.txt"
    msg.write_text("feat: x [ADR-none]\n")
    proc = run(repo, "hook", "commit-msg", str(msg))
    assert proc.returncode != 0
    assert "不符合豁免规则" in proc.stderr


def test_commit_msg_allows_adr_none_for_docs_change(tmp_path: Path):
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("doc change\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    msg = repo / "msg.txt"
    msg.write_text("docs: update [ADR-none]\n")
    proc = run(repo, "hook", "commit-msg", str(msg))
    assert proc.returncode == 0


def test_status_fails_on_invalid_rev_range(tmp_path: Path):
    repo = init_repo(tmp_path)
    proc = run(repo, "adr", "status", "--rev-range", "missing..HEAD")
    assert proc.returncode != 0
    assert "failed" in proc.stderr or "unknown revision" in proc.stderr or "bad revision" in proc.stderr
