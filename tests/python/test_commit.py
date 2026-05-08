from __future__ import annotations

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
    proc = run(repo, "commit", "prepare")
    assert proc.returncode == 0
    assert "无 staged changes" in proc.stdout


def test_commit_reports_staged_files(tmp_path: Path):
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("hello")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    proc = run(repo, "commit", "prepare")
    assert proc.returncode == 0
    assert "Staged Files" in proc.stderr
    assert "README.md" in proc.stderr


def _stage_src_file(repo: Path) -> None:
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "main.py").write_text("print('test')")
    subprocess.run(["git", "add", "src/main.py"], cwd=repo, check=True)


def test_commit_prepare_writes_commit_msg(tmp_path: Path):
    repo = init_repo(tmp_path)
    _stage_src_file(repo)
    proc = run(repo, "commit", "prepare", "--message", "feat(core): test [ADR-000]")
    assert proc.returncode == 0
    msg_path = repo / ".git" / "spec-vc-commit-msg"
    assert msg_path.exists()
    assert "feat(core): test [ADR-000]" in msg_path.read_text()




def test_commit_prepare_no_manifest_generated(tmp_path: Path):
    """ADR-010: prepare no longer generates manifest/audit-report/test-report."""
    repo = init_repo(tmp_path)
    _stage_src_file(repo)
    proc = run(repo, "commit", "prepare")
    assert proc.returncode == 0
    assert not (repo / ".git" / "spec-vc-manifest.json").exists()


def test_commit_prepare_lists_hook_checks(tmp_path: Path):
    """ADR-012: commit prepare 输出列举 4 项 hook 校验项 + SKILL.md 引用。"""
    repo = init_repo(tmp_path)
    _stage_src_file(repo)
    proc = run(repo, "commit", "prepare")
    assert proc.returncode == 0
    assert "subagent session log" in proc.stderr
    assert "ADR 引用" in proc.stderr
    assert "plan stage" in proc.stderr
    assert "Spec" in proc.stderr
    assert "SKILL.md" in proc.stderr


def test_commit_with_spec_files(tmp_path: Path):
    repo = init_repo(tmp_path)
    _stage_src_file(repo)

    spec_dir = repo / "doc" / "arch" / "specs" / "001"
    spec_dir.mkdir(parents=True)
    (spec_dir / "dev-doc.md").write_text("""# Spec-001: test spec

- **ADR**: ADR-000
- **Status**: Draft
- **Author**: test
- **Date**: 2026-04-26
- **Version**: 0.1.0

---

## 概述

test overview

---

## 接口契约

```yaml
GET /test:
  response:
    200:
      status: ok
```

## 数据形状

test data

## 行为规则

test behavior

## 非目标

none

---

## 测试策略

验收标准: GET /test returns 200.

## 日志实现

INFO level logs request events.

---

""")
    (spec_dir / "contract.openapi.yaml").write_text("openapi: \"3.0.3\"\ninfo:\n  title: test\npaths:\n  /test:\n    get:\n      responses:\n        200:\n          description: ok\n")
    (spec_dir / "schema.json").write_text('{"$schema":"https://json-schema.org/draft/2020-12/schema","title":"test","type":"object","properties":{"status":{"type":"string"}}}')
    (spec_dir / "behavior.feature").write_text("Feature: test\n  Scenario: get status\n    When GET /test\n    Then status is 200\n")

    proc = run(repo, "commit", "prepare")
    assert proc.returncode == 0
    assert "Spec-001" in proc.stderr
    assert "manifest" not in proc.stdout.lower()
