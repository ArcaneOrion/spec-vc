from __future__ import annotations

import subprocess
from pathlib import Path
import json
import os


def run(repo: Path, *args: str, check: bool = False):
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


def test_skill_doc_uses_correct_venv_path_in_bootstrap_protocol():
    root = Path(__file__).resolve().parents[2]
    skill = (root / "SKILL.md").read_text()
    assert "~/.claude/skills/spec-vc/.venv/bin/spec-vc skill load --user-prompt" in skill
    assert "spec-vc 的 Python 环境和可执行文件位于" in skill


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


def init_empty_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)
    return repo


def test_init_bootstraps_repo(tmp_path: Path):
    repo = init_empty_repo(tmp_path)
    proc = run(repo, "init", check=True)
    assert "spec-vc 初始化成功" in proc.stdout
    assert "uv sync" in proc.stdout
    assert (repo / ".spec-vc.toml").exists()
    assert (repo / "doc" / "arch" / "README.md").exists()
    assert (repo / "doc" / "arch" / "adr-000.md").exists()
    assert (repo / ".git" / "hooks" / "commit-msg").exists()
    assert (repo / ".git" / "hooks" / "prepare-commit-msg").exists()
    assert (repo / ".git" / "hooks" / "commit-msg").stat().st_mode & 0o111
    commit_template = subprocess.run(["git", "config", "commit.template"], cwd=repo, text=True, capture_output=True, check=True)
    assert commit_template.stdout.strip().endswith("templates/commit-msg")
    assert (repo / ".claude" / "settings.json").exists()
    settings = json.loads((repo / ".claude" / "settings.json").read_text())
    assert "PostToolUse" in settings.get("hooks", {})


def test_init_runs_uv_sync(tmp_path: Path):
    repo = init_empty_repo(tmp_path)
    proc = run(repo, "init", check=True)
    assert "uv sync" in proc.stdout
    root = Path(__file__).resolve().parents[2]
    assert (root / ".venv").exists()



def test_init_supports_no_seed(tmp_path: Path):
    repo = init_empty_repo(tmp_path)
    proc = run(repo, "init", "--no-seed", check=True)
    assert "spec-vc 初始化成功" in proc.stdout
    assert (repo / ".spec-vc.toml").exists()
    assert (repo / "doc" / "arch" / "README.md").exists()
    assert not (repo / "doc" / "arch" / "adr-000.md").exists()
    next_proc = run(repo, "adr", "new", "新的决策", check=True)
    assert "adr-000.md" in next_proc.stdout
    assert (repo / "doc" / "arch" / "adr-000.md").exists()



def test_init_fails_outside_git_repo(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    proc = run(repo, "init")
    assert proc.returncode != 0
    assert "当前目录不在 git 仓库内" in proc.stderr
    assert not (repo / ".spec-vc.toml").exists()



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


def _write_token(repo: Path):
    """写入一个有效的提交通行 token。"""
    import time
    import uuid
    token_path = repo / ".git" / "spec-vc-commit-token"
    token_content = f"{uuid.uuid4().hex}\n{int(time.time())}"
    token_path.write_text(token_content)


def test_commit_msg_blocks_without_token(tmp_path: Path):
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("change\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    msg = repo / "msg.txt"
    msg.write_text("docs: update [ADR-none]\n")
    proc = run(repo, "hook", "commit-msg", str(msg))
    assert proc.returncode != 0
    assert "未找到提交 token" in proc.stderr


def test_commit_msg_rejects_adr_none_for_code_change(tmp_path: Path):
    repo = init_repo(tmp_path)
    src = repo / "src"
    src.mkdir()
    (src / "main.py").write_text("print('x')\n")
    subprocess.run(["git", "add", "src/main.py"], cwd=repo, check=True)
    _write_token(repo)
    msg = repo / "msg.txt"
    msg.write_text("feat: x [ADR-none]\n")
    proc = run(repo, "hook", "commit-msg", str(msg))
    assert proc.returncode != 0
    assert "不符合豁免规则" in proc.stderr


def test_commit_msg_allows_adr_none_for_docs_change(tmp_path: Path):
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("doc change\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    _write_token(repo)
    msg = repo / "msg.txt"
    msg.write_text("docs: update [ADR-none]\n")
    proc = run(repo, "hook", "commit-msg", str(msg))
    assert proc.returncode == 0


def test_status_fails_on_invalid_rev_range(tmp_path: Path):
    repo = init_repo(tmp_path)
    proc = run(repo, "adr", "status", "--rev-range", "missing..HEAD")
    assert proc.returncode != 0
    assert "failed" in proc.stderr or "unknown revision" in proc.stderr or "bad revision" in proc.stderr


def test_init_merges_existing_claude_settings(tmp_path: Path):
    repo = init_empty_repo(tmp_path)
    claude_dir = repo / ".claude"
    claude_dir.mkdir()
    existing = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo existing"}]}]}}
    (claude_dir / "settings.json").write_text(json.dumps(existing))
    run(repo, "init", check=True)
    merged = json.loads((claude_dir / "settings.json").read_text())
    assert "PreToolUse" in merged["hooks"]
    assert "PostToolUse" in merged["hooks"]
    assert any("spec-vc hook post-tool-use" in h.get("command", "") for entry in merged["hooks"]["PostToolUse"] for h in entry.get("hooks", []))


def test_post_tool_use_hook_detects_clarify(tmp_path: Path):
    repo = init_repo(tmp_path)
    run(repo, "change", "start", "--adr", "000", "--summary", "重构 CLI")
    run(repo, "change", "clarify",
        "--motivation", "简化命名",
        "--boundary", "只改名不改功能",
        "--design", "无架构变更",
        "--implementation", "rename cmd_adr_init to cmd_init",
        "--verification", "单元测试覆盖",
        "--rollback", "git revert")
    hook_input = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": "spec-vc change clarify --motivation 简化命名 ..."},
        "tool_output": "doc/arch/plans/ADR-000-plan-001.md\n"
    })
    proc = subprocess.run(
        ["uv", "run", "spec-vc", "hook", "post-tool-use"],
        input=hook_input, text=True, capture_output=True, cwd=repo, env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src")}
    )
    assert proc.returncode == 0
    assert "ADR-000 执行方案" in proc.stdout


def test_post_tool_use_hook_ignores_irrelevant(tmp_path: Path):
    repo = init_repo(tmp_path)
    hook_input = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": "pytest tests/ -v"},
        "tool_output": "82 passed"
    })
    proc = subprocess.run(
        ["uv", "run", "spec-vc", "hook", "post-tool-use"],
        input=hook_input, text=True, capture_output=True, cwd=repo, env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src")}
    )
    assert proc.returncode == 0
    assert "ADR-000" not in proc.stdout
