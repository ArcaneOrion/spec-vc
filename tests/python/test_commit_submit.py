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


def _write_reports(repo: Path) -> None:
    audit = repo / ".git" / "spec-vc-audit-report.json"
    audit.write_text(json.dumps({
        "findings": [{"symbol": "✅", "spec_id": "000", "formal_file": "contract.openapi.yaml",
                       "description": "ok", "location": "src/main.py:1"}],
        "summary": {"total_passed": 1, "total_warnings": 0, "total_failed": 0, "judgment": "通过"}
    }))
    test = repo / ".git" / "spec-vc-test-report.json"
    test.write_text(json.dumps({
        "unit_results": [{"unit_id": "test-000-openapi", "formal_type": "openapi",
                          "total_cases": 1, "total_passed": 1, "total_failed": 0,
                          "judgment": "通过"}],
        "total_cases": 1, "total_passed": 1, "total_failed": 0, "judgment": "通过"
    }))


def _write_minimal_manifest_for_verify(repo: Path) -> None:
    """写入与 audit_report 匹配的最小 manifest，供 verify 通过。"""
    manifest = repo / ".git" / "spec-vc-manifest.json"
    manifest.write_text(json.dumps({
        "staged_files": ["src/main.py"],
        "spec_dirs": [],
        "audit_units": [{"unit_id": "audit-000", "spec_id": "000",
                          "adr_ref": "ADR-000", "dev_doc_summary": {},
                          "formal_files": {"contract.openapi.yaml": "dummy"},
                          "complexity_score": 1}],
        "test_units": [{"unit_id": "test-000-openapi", "spec_id": "000",
                         "formal_type": "openapi", "formal_content": "dummy",
                         "test_dir": "specs/000/tests/", "estimated_complexity": 1}],
        "timestamp": "2026-05-03T00:00:00"
    }))


class TestCommitSubmit:
    def test_submit_rejects_missing_manifest(self, tmp_path: Path):
        repo = init_repo(tmp_path)
        _stage_src(repo)
        proc = run(repo, "commit", "submit",
                   extra_env={"SPEC_VC_TEST_TTY_BYPASS": "1"})
        assert proc.returncode == 1
        assert "未找到 manifest" in proc.stderr

    def test_submit_rejects_missing_audit_report(self, tmp_path: Path):
        repo = init_repo(tmp_path)
        _stage_src(repo)
        _write_minimal_manifest_for_verify(repo)
        (repo / ".git" / "spec-vc-test-report.json").write_text("{}")
        proc = run(repo, "commit", "submit",
                   extra_env={"SPEC_VC_TEST_TTY_BYPASS": "1"})
        assert proc.returncode == 1
        assert "审计报告" in proc.stderr

    def test_submit_rejects_missing_test_report(self, tmp_path: Path):
        repo = init_repo(tmp_path)
        _stage_src(repo)
        _write_minimal_manifest_for_verify(repo)
        (repo / ".git" / "spec-vc-audit-report.json").write_text("{}")
        proc = run(repo, "commit", "submit",
                   extra_env={"SPEC_VC_TEST_TTY_BYPASS": "1"})
        assert proc.returncode == 1
        assert "测试报告" in proc.stderr

    def test_submit_rejects_manifest_mismatch(self, tmp_path: Path):
        repo = init_repo(tmp_path)
        _stage_src(repo)
        manifest = repo / ".git" / "spec-vc-manifest.json"
        manifest.write_text(json.dumps({
            "staged_files": ["nonexistent.py"],
            "spec_dirs": [],
            "audit_units": [],
            "test_units": [],
            "timestamp": "2026-05-03T00:00:00"
        }))
        proc = run(repo, "commit", "submit",
                   extra_env={"SPEC_VC_TEST_TTY_BYPASS": "1"})
        assert proc.returncode == 1
        assert "manifest 不匹配" in proc.stderr
