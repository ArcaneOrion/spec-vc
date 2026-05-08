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


def test_adr_new_warns_on_id_gap(tmp_path: Path):
    """ADR-012: 编号存在空洞时 adr new 输出警告。"""
    repo = init_repo(tmp_path)
    # seed ADR-000 已存在，先创建 ADR-001 使得 next_adr_id=002
    run(repo, "adr", "new", "第一个决策")
    # 然后创建 ADR-002
    run(repo, "adr", "new", "第二个决策")
    # 删除 ADR-001 制造空洞：000, 002 存在，001 缺失
    (repo / "doc" / "arch" / "adr-001.md").unlink()
    proc = run(repo, "adr", "new", "第三个决策", check=True)
    assert "编号存在空洞" in proc.stderr
    # 新 ADR 应该是 003（最大编号+1）
    assert (repo / "doc" / "arch" / "adr-003.md").exists()


def test_spec_new_uses_adr_id(tmp_path: Path):
    """ADR-012: spec new --adr ADR-012 时 Spec 编号与 ADR 编号对齐。"""
    repo = init_repo(tmp_path)
    run(repo, "adr", "new", "测试决策")
    proc = run(repo, "spec", "new", "测试 Spec", "--adr", "ADR-001", check=True)
    assert "Spec-001" in proc.stdout
    assert (repo / "doc" / "arch" / "specs" / "001").is_dir()


def test_spec_new_falls_back_on_duplicate(tmp_path: Path):
    """ADR-012: Spec-001 已存在时用 next_spec_id 顺延。"""
    repo = init_repo(tmp_path)
    run(repo, "adr", "new", "测试决策")
    run(repo, "spec", "new", "第一个 Spec", "--adr", "ADR-001")
    # 再用同一 ADR 创建，Spec-001 已存在，顺延到 002
    proc = run(repo, "spec", "new", "第二个 Spec", "--adr", "ADR-001", check=True)
    assert "Spec-002" in proc.stdout
    assert (repo / "doc" / "arch" / "specs" / "002").is_dir()


def test_commit_msg_rejects_multiple_tokens(tmp_path: Path):
    repo = init_repo(tmp_path)
    msg = repo / "msg.txt"
    msg.write_text("feat: x [ADR-000] [ADR-999]\n")
    proc = run(repo, "hook", "commit-msg", str(msg))
    assert proc.returncode != 0


def test_commit_msg_block_messages_reference_skill_md(tmp_path: Path):
    """ADR-012: HELP_MISSING / HELP_SLOT 阻塞消息含可执行指引和 SKILL.md 引用。"""
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("change\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    _write_subagent_session(repo)
    msg = repo / "msg.txt"

    msg.write_text("docs: no token here\n")
    proc = run(repo, "hook", "commit-msg", str(msg))
    assert proc.returncode != 0
    assert "[ADR-NNN]" in proc.stderr
    assert "SKILL.md" in proc.stderr

    msg.write_text("docs: slot [ADR-???]\n")
    proc = run(repo, "hook", "commit-msg", str(msg))
    assert proc.returncode != 0
    assert "[ADR-???]" in proc.stderr
    assert "SKILL.md" in proc.stderr


def _write_subagent_session(repo: Path):
    """写入 subagent session log。"""
    log_path = repo / ".git" / "spec-vc-subagent-sessions.log"
    log_path.write_text("2026-05-03T17:00:00+08:00 | Agent | audit subagent\n")


def test_commit_msg_blocks_without_subagent_session(tmp_path: Path):
    """无 subagent session 记录时 hook 阻塞。"""
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("change\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    msg = repo / "msg.txt"
    msg.write_text("docs: update [ADR-none]\n")
    proc = run(repo, "hook", "commit-msg", str(msg))
    assert proc.returncode != 0
    assert "未找到 subagent 审计记录" in proc.stderr
    assert "SKILL.md" in proc.stderr


def test_commit_msg_rejects_adr_none_for_code_change(tmp_path: Path):
    repo = init_repo(tmp_path)
    src = repo / "src"
    src.mkdir()
    (src / "main.py").write_text("print('x')\n")
    subprocess.run(["git", "add", "src/main.py"], cwd=repo, check=True)
    _write_subagent_session(repo)
    msg = repo / "msg.txt"
    msg.write_text("feat: x [ADR-none]\n")
    proc = run(repo, "hook", "commit-msg", str(msg))
    assert proc.returncode != 0
    assert "不符合豁免规则" in proc.stderr


def test_commit_msg_allows_adr_none_for_docs_change(tmp_path: Path):
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("doc change\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    _write_subagent_session(repo)
    msg = repo / "msg.txt"
    msg.write_text("docs: update [ADR-none]\n")
    proc = run(repo, "hook", "commit-msg", str(msg))
    assert proc.returncode == 0


def _run_with_env(repo: Path, *args: str, extra_env: dict | None = None):
    """ADR-007 测试辅助：调用 hook 并附加自定义环境变量。"""
    import sys as _sys
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, "PYTHONPATH": str(root / "src")}
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [_sys.executable, "-m", "spec_vc.cli", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        env=env,
    )


def test_commit_msg_bypass_env_skips_token_check(tmp_path: Path):
    """ADR-007: SPEC_VC_BYPASS 非空时跳过 token 校验并写审计日志。"""
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("change\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    msg = repo / "msg.txt"
    msg.write_text("docs: update [ADR-none]\n")
    # 不写 token，靠 bypass 通过
    proc = _run_with_env(
        repo, "hook", "commit-msg", str(msg),
        extra_env={"SPEC_VC_BYPASS": "hotfix"},
    )
    assert proc.returncode == 0, f"bypass 应放行, stderr={proc.stderr}"
    log_path = repo / ".git" / "spec-vc-bypass.log"
    assert log_path.exists(), "bypass 日志应被创建"
    log_content = log_path.read_text()
    assert "hotfix" in log_content
    assert "docs: update [ADR-none]" in log_content
    # 验证格式：含管道分隔符
    assert log_content.count(" | ") >= 2


def test_commit_msg_bypass_empty_string_falls_back_to_session_check(tmp_path: Path):
    """ADR-011: SPEC_VC_BYPASS 空字符串视为未触发，走 subagent session 校验。"""
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("change\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    msg = repo / "msg.txt"
    msg.write_text("docs: update [ADR-none]\n")
    proc = _run_with_env(
        repo, "hook", "commit-msg", str(msg),
        extra_env={"SPEC_VC_BYPASS": ""},
    )
    assert proc.returncode != 0, "空字符串不应触发 bypass"
    assert "未找到 subagent 审计记录" in proc.stderr
    assert "SPEC_VC_BYPASS" in proc.stderr


def test_commit_msg_bypass_log_failure_is_fail_open(tmp_path: Path):
    """ADR-007: 日志写入失败时 hook 仍放行（fail-open）。"""
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("change\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    # 把日志路径预先做成目录——open("a") 会报 IsADirectoryError
    log_path = repo / ".git" / "spec-vc-bypass.log"
    log_path.mkdir()
    msg = repo / "msg.txt"
    msg.write_text("docs: update [ADR-none]\n")
    proc = _run_with_env(
        repo, "hook", "commit-msg", str(msg),
        extra_env={"SPEC_VC_BYPASS": "repair"},
    )
    assert proc.returncode == 0, f"日志写入失败时应仍放行, stderr={proc.stderr}"
    assert "bypass 日志写入失败" in proc.stderr


def test_hook_with_subagent_session_passes(tmp_path: Path):
    """有 subagent session 记录时 hook 放行。"""
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("doc change\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    _write_subagent_session(repo)
    msg = repo / "msg.txt"
    msg.write_text("docs: update [ADR-none]\n")
    proc = run(repo, "hook", "commit-msg", str(msg))
    assert proc.returncode == 0, f"有 session 记录应放行, stderr={proc.stderr}"


def test_hook_blocks_without_subagent_session(tmp_path: Path):
    """无 subagent session 记录时 hook 阻塞。"""
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("doc change\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    # 不写 subagent session log
    msg = repo / "msg.txt"
    msg.write_text("docs: update [ADR-none]\n")
    proc = run(repo, "hook", "commit-msg", str(msg))
    assert proc.returncode != 0, "无 session 记录应阻塞"
    assert "subagent" in proc.stderr
    assert "SKILL.md" in proc.stderr


def test_hook_bypass_skips_subagent_session_check(tmp_path: Path):
    """SPEC_VC_BYPASS 非空时跳过 token + subagent session 检查。"""
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("doc change\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    msg = repo / "msg.txt"
    msg.write_text("docs: hotfix [ADR-none]\n")
    proc = _run_with_env(
        repo, "hook", "commit-msg", str(msg),
        extra_env={"SPEC_VC_BYPASS": "hotfix"},
    )
    assert proc.returncode == 0, f"bypass 应放行, stderr={proc.stderr}"
    assert (repo / ".git" / "spec-vc-bypass.log").exists()


def _setup_active_change(repo: Path) -> None:
    """创建一个 active change (clarify stage) 用于 plan stage 测试。"""
    run(repo, "change", "start", "--adr", "000", "--summary", "测试变更")


def _complete_clarify(repo: Path) -> None:
    """完成 clarify 所有字段，推进到 plan stage。"""
    run(repo, "change", "clarify",
        "--motivation", "测试动机",
        "--boundary", "测试边界",
        "--design", "测试设计",
        "--implementation", "测试实现",
        "--verification", "测试验证",
        "--rollback", "测试回滚")


def test_hook_blocks_adr_with_plan_stage_below_implement_ready(tmp_path: Path):
    """ADR-011: plan stage 为 clarify 时，[ADR-NNN] 提交被 hook 阻塞。"""
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("doc change\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    _setup_active_change(repo)
    _write_subagent_session(repo)
    msg = repo / "msg.txt"
    msg.write_text("docs: update [ADR-000]\n")
    proc = run(repo, "hook", "commit-msg", str(msg))
    assert proc.returncode != 0, "clarify stage 应阻塞提交"
    assert "implement-ready" in proc.stderr
    assert "SKILL.md" in proc.stderr


def test_hook_allows_adr_at_implement_ready_stage(tmp_path: Path):
    """ADR-011: plan stage >= implement-ready 时，[ADR-NNN] 提交放行。"""
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("doc change\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    _setup_active_change(repo)
    _complete_clarify(repo)
    # validate --phase pre → implement-ready
    run(repo, "change", "validate", "--phase", "pre", "--content", "修改前验证通过")
    _write_subagent_session(repo)
    msg = repo / "msg.txt"
    msg.write_text("docs: update [ADR-000]\n")
    proc = run(repo, "hook", "commit-msg", str(msg))
    assert proc.returncode == 0, f"implement-ready stage 应放行, stderr={proc.stderr}"


def test_hook_allows_adr_without_active_change(tmp_path: Path):
    """ADR-011: ADR 引用正确但无 active change 时放行（变更流程已关闭或不同提交）。"""
    repo = init_repo(tmp_path)
    (repo / "doc" / "arch" / "README.md").write_text("change\n")
    subprocess.run(["git", "add", "doc/arch/README.md"], cwd=repo, check=True)
    # 不创建 active change — 模拟变更已关闭后的追加提交
    _write_subagent_session(repo)
    msg = repo / "msg.txt"
    msg.write_text("docs: update [ADR-000]\n")
    proc = run(repo, "hook", "commit-msg", str(msg))
    assert proc.returncode == 0, f"无 active change 时应放行, stderr={proc.stderr}"


def test_hook_blocks_adr_with_incomplete_spec_includes_skill_md(tmp_path: Path):
    """ADR-012: ADR 关联 Spec 不就绪时 hook 阻塞且消息含修复步骤 + SKILL.md 引用。"""
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("doc change\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    _setup_active_change(repo)
    _complete_clarify(repo)
    # 此时无关联 Spec，pre-validation 直接通过推进到 implement-ready
    run(repo, "change", "validate", "--phase", "pre", "--content", "通过")
    # 推进到 implement-ready 后再创建关联 Spec 但不填写
    run(repo, "spec", "new", "测试 Spec", "--adr", "ADR-000")
    _write_subagent_session(repo)
    msg = repo / "msg.txt"
    msg.write_text("docs: update [ADR-000]\n")
    proc = run(repo, "hook", "commit-msg", str(msg))
    assert proc.returncode != 0, "未就绪 Spec 应阻塞"
    assert "Spec 未完成" in proc.stderr
    assert "spec formalize" in proc.stderr
    assert "SKILL.md" in proc.stderr


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


def test_post_tool_use_hook_records_agent_call(tmp_path: Path):
    """ADR-009: PostToolUse hook 记录 Agent 调用到 subagent-sessions.log。"""
    repo = init_repo(tmp_path)
    proc = run(repo, "hook", "post-tool-use",
               "--tool-name", "Agent",
               "--description", "audit subagent checking commit")
    assert proc.returncode == 0
    log_path = repo / ".git" / "spec-vc-subagent-sessions.log"
    assert log_path.exists(), "subagent-sessions.log 应该被创建"
    content = log_path.read_text()
    assert "Agent" in content
    assert "audit subagent checking commit" in content
    # 验证管道分隔格式
    parts = content.strip().split(" | ")
    assert len(parts) >= 2, f"日志格式应为 pipe-separated, got: {content}"
    assert parts[1] == "Agent"


def test_post_tool_use_hook_skips_empty_tool_name(tmp_path: Path):
    """ADR-009: 无 tool_name 时不写入日志。"""
    repo = init_repo(tmp_path)
    proc = run(repo, "hook", "post-tool-use")
    assert proc.returncode == 0
    log_path = repo / ".git" / "spec-vc-subagent-sessions.log"
    assert not log_path.exists(), "无 tool_name 时不应创建日志"
