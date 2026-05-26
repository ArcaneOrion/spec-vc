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


def _stage_src_file(repo: Path) -> None:
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "main.py").write_text("print('test')")
    subprocess.run(["git", "add", "src/main.py"], cwd=repo, check=True)


def test_review_blocks_when_no_staged(tmp_path: Path):
    """ADR-018: spec-vc review 无 staged → BlockingError 阻塞。"""
    repo = init_repo(tmp_path)
    proc = run(repo, "review", "--message", "feat: x [ADR-000]")
    assert proc.returncode != 0
    assert "staged 区为空" in proc.stderr
    assert "BLOCKED" in proc.stderr
    assert "git add" in proc.stderr


def test_review_reports_staged_files(tmp_path: Path):
    """ADR-018: spec-vc review 输出 staged files + audit-anchor。"""
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("hello")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    proc = run(repo, "review", "--message", "docs: hello [ADR-000]")
    assert proc.returncode == 0, proc.stderr
    assert "Staged Files" in proc.stderr
    assert "README.md" in proc.stderr
    assert "audit-anchor: ADR-000@" in proc.stdout


def test_review_writes_commit_msg(tmp_path: Path):
    """ADR-018: spec-vc review --message 写 commit-msg + review.json。"""
    repo = init_repo(tmp_path)
    _stage_src_file(repo)
    proc = run(repo, "review", "--message", "feat(core): test [ADR-000]")
    assert proc.returncode == 0, proc.stderr
    msg_path = repo / ".git" / "spec-vc-commit-msg"
    assert msg_path.exists()
    assert "feat(core): test [ADR-000]" in msg_path.read_text()
    review_path = repo / ".git" / "spec-vc-review.json"
    assert review_path.exists()
    record = json.loads(review_path.read_text())
    assert record["adr_token"] == "ADR-000"
    assert record["mode"] == "subagent"
    assert record["verified"] is False
    assert record["document_baseline"]["version"] == 1
    assert record["document_baseline"]["adr_token"] == "ADR-000"
    assert any(
        item["path"] == "doc/arch/adr-000.md" and item["kind"] == "adr"
        for item in record["document_baseline"]["files"]
    )


def test_review_no_manifest_generated(tmp_path: Path):
    """ADR-010 保留: review 不生成 manifest。"""
    repo = init_repo(tmp_path)
    _stage_src_file(repo)
    proc = run(repo, "review", "--message", "feat: x [ADR-000]")
    assert proc.returncode == 0
    assert not (repo / ".git" / "spec-vc-manifest.json").exists()


def test_review_outputs_next_step_hints(tmp_path: Path):
    """ADR-018: spec-vc review 输出含 audit-anchor + 下一步 + SKILL.md 引用。"""
    repo = init_repo(tmp_path)
    _stage_src_file(repo)
    proc = run(repo, "review", "--message", "feat: x [ADR-000]")
    assert proc.returncode == 0
    assert "audit-anchor:" in proc.stdout
    assert "review.json" in proc.stderr
    assert "commit-msg" in proc.stderr
    assert "SKILL.md" in proc.stderr


def test_review_with_spec_files(tmp_path: Path):
    """ADR-018 + Spec-001 端到端：staged code + 完整 spec → review 通过。"""
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

    proc = run(repo, "review", "--message", "feat: x [ADR-000]")
    assert proc.returncode == 0
    assert "Spec-001" in proc.stderr


def test_commit_prepare_alias_emits_deprecation(tmp_path: Path):
    """ADR-018: spec-vc commit prepare 作为 alias 调用 review 并打 deprecation warning。"""
    repo = init_repo(tmp_path)
    _stage_src_file(repo)
    proc = run(repo, "commit", "prepare", "--message", "feat: x [ADR-000]")
    assert proc.returncode == 0
    assert "DEPRECATION" in proc.stderr
    assert "spec-vc review" in proc.stderr
    review_path = repo / ".git" / "spec-vc-review.json"
    assert review_path.exists()
