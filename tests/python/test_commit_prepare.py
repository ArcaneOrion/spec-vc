from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys
import os


def run(repo: Path, *args: str, extra_env: dict | None = None):
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, "PYTHONPATH": str(root / "src")}
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-m", "spec_vc.cli", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        env=env,
    )


def init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)
    root = Path(__file__).resolve().parents[2]
    (repo / ".spec-vc.toml").write_text((root / ".spec-vc.toml").read_text())
    (repo / "doc" / "arch").mkdir(parents=True)
    (repo / "doc" / "arch" / "README.md").write_text((root / "templates" / "index.md").read_text())
    seed = (
        (root / "templates" / "seed-adr-000.md")
        .read_text()
        .replace("{{DATE}}", "2026-04-23")
        .replace("{{AUTHOR}}", "test")
    )
    (repo / "doc" / "arch" / "adr-000.md").write_text(seed)
    return repo


def _stage_src(repo: Path) -> None:
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "main.py").write_text("print('test')")
    subprocess.run(["git", "add", "src/main.py"], cwd=repo, check=True)


class TestCommitPrepare:
    def test_prepare_writes_manifest_not_token(self, tmp_path: Path):
        repo = init_repo(tmp_path)
        _stage_src(repo)
        proc = run(repo, "commit", "prepare")
        assert proc.returncode == 0
        manifest = repo / ".git" / "spec-vc-manifest.json"
        assert manifest.exists()
        token = repo / ".git" / "spec-vc-commit-token"
        assert not token.exists()
        data = json.loads(manifest.read_text())
        assert "staged_files" in data
        assert "src/main.py" in data["staged_files"]

    def test_prepare_writes_commit_message(self, tmp_path: Path):
        repo = init_repo(tmp_path)
        _stage_src(repo)
        msg = "feat(core): add main module [ADR-000]"
        proc = run(repo, "commit", "prepare", "--message", msg)
        assert proc.returncode == 0
        msg_path = repo / ".git" / "spec-vc-commit-msg"
        assert msg_path.exists()
        assert msg_path.read_text() == msg

    def test_prepare_no_staged_output(self, tmp_path: Path):
        repo = init_repo(tmp_path)
        proc = run(repo, "commit", "prepare")
        assert proc.returncode == 0
        assert "无 staged changes" in proc.stdout

    def test_prepare_outputs_manifest_json(self, tmp_path: Path):
        repo = init_repo(tmp_path)
        _stage_src(repo)
        proc = run(repo, "commit", "prepare")
        assert proc.returncode == 0
        manifest = json.loads(proc.stdout)
        assert "audit_units" in manifest
        assert "test_units" in manifest
        assert "complexity_report" in manifest

    def test_prepare_manifest_saved_matches_stdout(self, tmp_path: Path):
        repo = init_repo(tmp_path)
        _stage_src(repo)
        proc = run(repo, "commit", "prepare")
        assert proc.returncode == 0
        stdout_data = json.loads(proc.stdout)
        saved_data = json.loads((repo / ".git" / "spec-vc-manifest.json").read_text())
        assert stdout_data == saved_data

    def test_prepare_prints_guidance_to_stderr(self, tmp_path: Path):
        repo = init_repo(tmp_path)
        _stage_src(repo)
        proc = run(repo, "commit", "prepare")
        assert proc.returncode == 0
        assert "manifest 已写入" in proc.stderr
        assert "spec-vc commit submit" in proc.stderr
