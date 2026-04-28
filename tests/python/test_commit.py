from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys
import os


def run(repo: Path, *args: str):
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, "PYTHONPATH": str(root / "src")}
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


def test_commit_no_staged_changes(tmp_path: Path):
    repo = init_repo(tmp_path)
    proc = run(repo, "commit")
    assert proc.returncode == 0
    assert "无 staged changes" in proc.stdout


def test_commit_reports_staged_files(tmp_path: Path):
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("hello")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    proc = run(repo, "commit")
    assert proc.returncode == 0
    assert "Staged Files" in proc.stderr
    assert "README.md" in proc.stderr


def _stage_src_file(repo: Path) -> None:
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "main.py").write_text("print('test')")
    subprocess.run(["git", "add", "src/main.py"], cwd=repo, check=True)


def test_commit_generates_audit_prompt(tmp_path: Path):
    repo = init_repo(tmp_path)
    _stage_src_file(repo)
    proc = run(repo, "commit", "--format", "text")
    assert proc.returncode == 0
    assert "AUDIT SUBAGENT PROMPT" in proc.stdout
    assert "审计规则" in proc.stdout
    assert "Git Diff" in proc.stdout


def test_commit_generates_test_prompt(tmp_path: Path):
    repo = init_repo(tmp_path)
    _stage_src_file(repo)
    proc = run(repo, "commit", "--format", "text")
    assert proc.returncode == 0
    assert "TEST SUBAGENT PROMPT" in proc.stdout
    assert "测试生成" in proc.stdout


def test_commit_with_spec_files(tmp_path: Path):
    repo = init_repo(tmp_path)
    _stage_src_file(repo)

    spec_dir = repo / "doc" / "arch" / "specs" / "001"
    spec_dir.mkdir(parents=True)
    (spec_dir / "dev-doc.md").write_text("""# Spec-001: 测试规格

- **ADR**: ADR-000
- **Status**: Draft
- **Author**: test
- **Date**: 2026-04-26

## 概述

测试概述

## 接口契约

```yaml
GET /test:
  response:
    200:
      status: ok
```

## 数据形状

测试数据

## 行为规则

测试行为

## 非目标

无

## References

- **ADR**: ADR-000
""")
    (spec_dir / "contract.openapi.yaml").write_text("openapi: \"3.0.3\"\ninfo:\n  title: test\npaths:\n  /test:\n    get:\n      responses:\n        200:\n          description: ok\n")
    (spec_dir / "schema.json").write_text('{"$schema":"https://json-schema.org/draft/2020-12/schema","title":"test","type":"object","properties":{"status":{"type":"string"}}}')
    (spec_dir / "behavior.feature").write_text("Feature: test\n  Scenario: get status\n    When GET /test\n    Then status is 200\n")

    proc = run(repo, "commit")
    assert proc.returncode == 0
    # human-readable info on stderr
    assert "Spec-001" in proc.stderr
    assert "formal: contract.openapi.yaml" in proc.stderr
    # JSON manifest on stdout
    manifest = json.loads(proc.stdout)
    assert "audit_units" in manifest
    assert "test_units" in manifest
    assert "complexity_report" in manifest
    assert len(manifest["audit_units"]) == 1
    assert manifest["audit_units"][0]["spec_id"] == "001"


def test_commit_clean_removes_tests(tmp_path: Path):
    repo = init_repo(tmp_path)
    test_dir = repo / "doc" / "arch" / "specs" / "001" / "tests"
    test_dir.mkdir(parents=True)
    (test_dir / "test_example.py").write_text("def test(): pass\n")
    assert test_dir.exists()

    proc = run(repo, "commit", "clean")
    assert proc.returncode == 0
    assert "已清理" in proc.stdout
    assert not test_dir.exists()


def test_commit_clean_no_tests(tmp_path: Path):
    repo = init_repo(tmp_path)
    proc = run(repo, "commit", "clean")
    assert proc.returncode == 0
    assert "无测试目录" in proc.stdout
