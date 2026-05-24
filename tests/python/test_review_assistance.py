"""ADR-019: review_assistance 单元测试 + cmd_review 集成测试。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def run(repo: Path, *args: str):
    env = {**os.environ, "PYTHONPATH": str(_root() / "src")}
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
    root = _root()
    (repo / ".spec-vc.toml").write_text((root / ".spec-vc.toml").read_text())
    (repo / "doc" / "arch").mkdir(parents=True)
    (repo / "doc" / "arch" / "README.md").write_text((root / "templates" / "index.md").read_text())
    seed = (root / "templates" / "seed-adr-000.md").read_text().replace("{{DATE}}", "2026-04-23").replace("{{AUTHOR}}", "test")
    (repo / "doc" / "arch" / "adr-000.md").write_text(seed)
    return repo


# ─── ADR-019: summarize_staged_diff ────────────────────────────────────────


def test_summarize_staged_diff_includes_stat_and_hunk(tmp_path: Path):
    """ADR-019: staged 区有变更时输出含 stat + hunk header。"""
    from spec_vc.review_assistance import summarize_staged_diff
    repo = init_repo(tmp_path)
    # 先初始 commit 一个文件，再修改它制造 hunk
    (repo / "README.md").write_text("line1\nline2\nline3\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init", "--no-verify"], cwd=repo, check=True)
    (repo / "README.md").write_text("line1\nNEW\nline2\nline3\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    out = summarize_staged_diff(repo)
    assert "=== Staged Diff Summary ===" in out
    assert "README.md" in out
    assert "@@" in out


def test_summarize_staged_diff_empty_staging(tmp_path: Path):
    """ADR-019: staged 区为空时返回 fallback。"""
    from spec_vc.review_assistance import summarize_staged_diff
    repo = init_repo(tmp_path)
    out = summarize_staged_diff(repo)
    assert "(无 staged changes)" in out


def test_summarize_staged_diff_fail_open(tmp_path: Path):
    """ADR-019: git 子进程异常 → fail-open，不抛异常。"""
    from spec_vc.review_assistance import summarize_staged_diff
    # 传入不存在的目录触发异常
    bad = tmp_path / "nonexistent"
    out = summarize_staged_diff(bad)
    assert "Staged Diff Summary" in out
    assert "(本段获取失败:" in out or "(无 staged changes)" in out


# ─── ADR-019: summarize_plan_context ────────────────────────────────────────


def test_summarize_plan_context_extracts_design_and_verification(tmp_path: Path):
    """ADR-019: 存在 plan 文件时提取 design + verification 两段。"""
    from spec_vc.review_assistance import summarize_plan_context
    repo = init_repo(tmp_path)
    plans_dir = repo / "doc" / "arch" / "plans"
    plans_dir.mkdir(parents=True)
    plan = plans_dir / "ADR-000-plan-001.md"
    plan.write_text(
        "# Plan\n\n## Design and Architecture\n\n这是设计段内容。\n\n"
        "## Verification and Testing\n\n这是验证段内容。\n"
    )
    out = summarize_plan_context(repo, "ADR-000")
    assert "=== Plan Context (Design + Verification) ===" in out
    assert "Design and Architecture" in out
    assert "这是设计段内容" in out
    assert "Verification and Testing" in out
    assert "这是验证段内容" in out


def test_summarize_plan_context_no_plan_file(tmp_path: Path):
    """ADR-019: ADR 无 plan 文件时返回 fallback。"""
    from spec_vc.review_assistance import summarize_plan_context
    repo = init_repo(tmp_path)
    out = summarize_plan_context(repo, "ADR-999")
    assert "无活跃 plan" in out


def test_summarize_plan_context_truncates_long_section(tmp_path: Path):
    """ADR-019: 段超过 max_chars_per_section 时截断标记。"""
    from spec_vc.review_assistance import summarize_plan_context
    repo = init_repo(tmp_path)
    plans_dir = repo / "doc" / "arch" / "plans"
    plans_dir.mkdir(parents=True)
    long_text = "x" * 2000
    (plans_dir / "ADR-000-plan-001.md").write_text(
        f"# Plan\n\n## Design and Architecture\n\n{long_text}\n\n"
        f"## Verification and Testing\n\nshort\n"
    )
    out = summarize_plan_context(repo, "ADR-000", max_chars_per_section=100)
    assert "(truncated)" in out


# ─── ADR-019: summarize_spec_context ────────────────────────────────────────


def test_summarize_spec_context_outputs_formal_files(tmp_path: Path):
    """ADR-019: 有关联 Spec 时输出三个形式化文件前 N 行。"""
    from spec_vc.review_assistance import summarize_spec_context
    repo = init_repo(tmp_path)
    spec_dir = repo / "doc" / "arch" / "specs" / "000"
    spec_dir.mkdir(parents=True)
    (spec_dir / "dev-doc.md").write_text(
        "# Spec-000: test spec\n\n- **ADR**: ADR-000\n- **Status**: Draft\n- **Author**: test\n- **Date**: 2026-04-23\n- **Version**: 0.1.0\n"
    )
    (spec_dir / "contract.openapi.yaml").write_text("openapi: 3.0.3\ninfo:\n  title: t\n")
    (spec_dir / "schema.json").write_text('{"$schema": "x", "title": "t"}')
    (spec_dir / "behavior.feature").write_text("Feature: t\n")
    out = summarize_spec_context(repo, "ADR-000")
    assert "=== Spec Context ===" in out
    assert "Spec-000/contract.openapi.yaml" in out
    assert "Spec-000/schema.json" in out
    assert "Spec-000/behavior.feature" in out


def test_summarize_spec_context_no_associated_spec(tmp_path: Path):
    """ADR-019: ADR 无关联 Spec 时返回 fallback。"""
    from spec_vc.review_assistance import summarize_spec_context
    repo = init_repo(tmp_path)
    out = summarize_spec_context(repo, "ADR-000")
    assert "无关联 Spec" in out or "specs 目录不存在" in out


# ─── ADR-019: run_static_checks ────────────────────────────────────────────


def test_run_static_checks_ruff_missing_silently_skipped(tmp_path: Path, monkeypatch):
    """ADR-019: ruff 不在 PATH 时静默跳过 + fallback 文字。"""
    from spec_vc import review_assistance
    monkeypatch.setattr(review_assistance.shutil, "which", lambda _: None)
    repo = init_repo(tmp_path)
    out = review_assistance.run_static_checks(repo)
    assert "=== Static Checks ===" in out
    assert "未检测到 ruff" in out


def test_run_static_checks_timeout(tmp_path: Path, monkeypatch):
    """ADR-019: 子进程超时 → fallback 文字，不抛异常。"""
    from spec_vc import review_assistance

    repo = init_repo(tmp_path)

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="ruff", timeout=0.01)

    monkeypatch.setattr(review_assistance.shutil, "which", lambda _: "/usr/bin/ruff")
    monkeypatch.setattr(review_assistance.subprocess, "run", fake_run)
    out = review_assistance.run_static_checks(repo, timeout=0.01)
    assert "超时" in out


# ─── ADR-019: assemble_review_report ───────────────────────────────────────


def test_assemble_review_report_full_sections(tmp_path: Path):
    """ADR-019: 默认全开时输出 5 段，含 anchor。"""
    from spec_vc.config import ReviewAssistanceConfig
    from spec_vc.review_assistance import assemble_review_report
    repo = init_repo(tmp_path)
    cfg = ReviewAssistanceConfig()
    out = assemble_review_report(repo, "ADR-000", "ADR-000@aaaaaaaaaaaa", cfg)
    assert "=== Staged Diff Summary ===" in out
    assert "=== Plan Context (Design + Verification) ===" in out
    assert "=== Spec Context ===" in out
    assert "=== Static Checks ===" in out
    assert "=== Your Response ===" in out
    assert "audit-anchor: ADR-000@aaaaaaaaaaaa" in out
    assert "spec-vc commit" in out


def test_assemble_review_report_respects_switches(tmp_path: Path):
    """ADR-019: 单个 show_* 开关关闭时该段不输出。"""
    from spec_vc.config import ReviewAssistanceConfig
    from spec_vc.review_assistance import assemble_review_report
    repo = init_repo(tmp_path)
    cfg = ReviewAssistanceConfig(run_static_checks=False, show_plan_context=False)
    out = assemble_review_report(repo, "ADR-000", "ADR-000@aaaaaaaaaaaa", cfg)
    assert "=== Static Checks ===" not in out
    assert "=== Plan Context (Design + Verification) ===" not in out
    assert "=== Your Response ===" in out


def test_assemble_review_report_fail_open_one_section(tmp_path: Path, monkeypatch):
    """ADR-019: 单段函数抛异常时该段 fail-open，其他段继续。"""
    from spec_vc import review_assistance
    from spec_vc.config import ReviewAssistanceConfig

    def boom(*args, **kwargs):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(review_assistance, "summarize_plan_context", boom)
    repo = init_repo(tmp_path)
    cfg = ReviewAssistanceConfig()
    out = review_assistance.assemble_review_report(repo, "ADR-000", "ADR-000@a" * 12 if len("ADR-000@a" * 12) else "ADR-000@aaaaaaaaaaaa", cfg)
    assert "Plan Context" in out
    assert "(本段获取失败:" in out
    assert "=== Your Response ===" in out


# ─── ADR-019: cmd_review 集成测试 ──────────────────────────────────────────


def test_cmd_review_outputs_report_to_stderr_and_writes_context_summary(tmp_path: Path):
    """ADR-019: spec-vc review 输出 5 段到 stderr + review.json.context_summary 非空。"""
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("hello\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    proc = run(repo, "review", "--message", "docs: hello [ADR-000]")
    assert proc.returncode == 0, proc.stderr
    assert "=== Staged Diff Summary ===" in proc.stderr
    assert "=== Your Response ===" in proc.stderr
    record = json.loads((repo / ".git" / "spec-vc-review.json").read_text())
    assert "context_summary" in record
    assert record["context_summary"]  # 非空
    assert "Your Response" in record["context_summary"]


def test_cmd_review_context_summary_truncated_to_max_bytes(tmp_path: Path):
    """ADR-019: context_summary 超过 max_bytes 时截断。"""
    repo = init_repo(tmp_path)
    cfg_path = repo / ".spec-vc.toml"
    cfg_path.write_text(cfg_path.read_text() + "\n[review_assistance]\ncontext_summary_max_bytes = 200\n")
    (repo / "README.md").write_text("hello\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    proc = run(repo, "review", "--message", "docs: hello [ADR-000]")
    assert proc.returncode == 0
    record = json.loads((repo / ".git" / "spec-vc-review.json").read_text())
    assert len(record["context_summary"]) == 200


# ─── ADR-019: 回归 —— hook 对含/不含 context_summary 的 review.json 都放行 ─


def test_hook_accepts_review_json_with_context_summary(tmp_path: Path):
    """ADR-019: review.json 含 context_summary 时 hook 正常放行（hook 不读该字段）。"""
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("doc\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    # 先 review 写入完整 review.json
    proc = run(repo, "review", "--message", "docs: x [ADR-000]")
    assert proc.returncode == 0
    record = json.loads((repo / ".git" / "spec-vc-review.json").read_text())
    assert "context_summary" in record
    # 触发 hook
    msg = repo / "msg.txt"
    msg.write_text("docs: x [ADR-000]\n")
    hook_proc = run(repo, "hook", "commit-msg", str(msg))
    assert hook_proc.returncode == 0, hook_proc.stderr


def test_hook_accepts_legacy_review_json_without_context_summary(tmp_path: Path):
    """ADR-019: 向后兼容 —— review.json 缺 context_summary 字段时 hook 仍放行。"""
    import datetime
    from spec_vc.commit import compute_audit_anchor
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("doc\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    anchor = compute_audit_anchor(repo, "ADR-000")
    ts = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    # 模拟 ADR-018 时代的 review.json（无 context_summary 字段）
    legacy = {
        "anchor": anchor,
        "adr_token": "ADR-000",
        "staged_sha12": anchor.split("@", 1)[1],
        "mode": "subagent",
        "verified": False,
        "note": "",
        "subagent_log_tail": None,
        "created_at": ts,
    }
    (repo / ".git" / "spec-vc-review.json").write_text(json.dumps(legacy))
    msg = repo / "msg.txt"
    msg.write_text("docs: x [ADR-000]\n")
    hook_proc = run(repo, "hook", "commit-msg", str(msg))
    assert hook_proc.returncode == 0, hook_proc.stderr
