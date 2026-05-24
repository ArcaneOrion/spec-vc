from __future__ import annotations

import subprocess
from pathlib import Path
import json
import os


def run(repo: Path, *args: str, check: bool = False, stdin: str | None = None):
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, "PYTHONPATH": str(root / "src")}
    proc = subprocess.run(
        [__import__("sys").executable, "-m", "spec_vc.cli", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        env=env,
        input=stdin,
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


def _write_subagent_session(repo: Path, anchor: str | None = None, adr_id: str = "000", mode: str = "subagent", verified: bool = False, note: str = ""):
    """ADR-018: 升级到写 review.json，同时兼容性写 session log + anchor file。

    旧测试默认 adr_id='000'，会基于当前 staged 内容动态计算真实 anchor。
    显式传 anchor 参数则覆盖（用于测试 anchor 不匹配 / 历史 anchor 等场景）。
    """
    import datetime
    import json
    from spec_vc.commit import compute_audit_anchor

    if anchor is None:
        adr_token = f"ADR-{adr_id}"
        anchor = compute_audit_anchor(repo, adr_token)
    else:
        adr_token = anchor.split("@", 1)[0]

    timestamp = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    log_path = repo / ".git" / "spec-vc-subagent-sessions.log"
    log_path.write_text(f"{timestamp} | Agent | audit subagent {anchor}\n")

    review_path = repo / ".git" / "spec-vc-review.json"
    sha12_part = anchor.split("@", 1)[1] if "@" in anchor else ""
    record = {
        "anchor": anchor,
        "adr_token": adr_token,
        "staged_sha12": sha12_part,
        "mode": mode,
        "verified": verified,
        "note": note,
        "subagent_log_tail": None,
        "created_at": timestamp,
    }
    review_path.write_text(json.dumps(record, ensure_ascii=False, indent=2))

    anchor_legacy_path = repo / ".git" / "spec-vc-audit-anchor"
    anchor_legacy_path.write_text(anchor)
    return anchor


def test_commit_msg_blocks_without_subagent_session(tmp_path: Path):
    """ADR-018: 无 review.json 时 [ADR-NNN] hook 阻塞。"""
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("change\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    msg = repo / "msg.txt"
    msg.write_text("docs: update [ADR-000]\n")
    proc = run(repo, "hook", "commit-msg", str(msg))
    assert proc.returncode != 0
    assert "review.json" in proc.stderr
    assert "BLOCKED" in proc.stderr
    assert "How to fix:" in proc.stderr
    assert "spec-vc review" in proc.stderr
    assert "ADR-018" in proc.stderr or "SKILL.md" in proc.stderr


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
    """ADR-018: SPEC_VC_BYPASS 空字符串视为未触发，[ADR-NNN] 仍走 review.json 校验。"""
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("change\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    msg = repo / "msg.txt"
    msg.write_text("docs: update [ADR-000]\n")
    proc = _run_with_env(
        repo, "hook", "commit-msg", str(msg),
        extra_env={"SPEC_VC_BYPASS": ""},
    )
    assert proc.returncode != 0, "空字符串不应触发 bypass"
    assert "review.json" in proc.stderr
    assert "BLOCKED" in proc.stderr


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
    """有 subagent session 记录时 [ADR-NNN] hook 放行。"""
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("doc change\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    _write_subagent_session(repo)
    msg = repo / "msg.txt"
    msg.write_text("docs: update [ADR-000]\n")
    proc = run(repo, "hook", "commit-msg", str(msg))
    assert proc.returncode == 0, f"有 session 记录应放行, stderr={proc.stderr}"


def test_hook_blocks_without_subagent_session(tmp_path: Path):
    """无 subagent session 记录时 [ADR-NNN] hook 阻塞。"""
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("doc change\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    # 不写 subagent session log
    msg = repo / "msg.txt"
    msg.write_text("docs: update [ADR-000]\n")
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


def test_post_tool_use_hook_skips_empty_description(tmp_path: Path):
    """ADR-013: description 为空时不写日志（避免空行污染 + 防仪式性）。"""
    repo = init_repo(tmp_path)
    proc = run(repo, "hook", "post-tool-use",
               "--tool-name", "Agent",
               "--description", "")
    assert proc.returncode == 0
    log_path = repo / ".git" / "spec-vc-subagent-sessions.log"
    assert not log_path.exists(), "空 description 时不应创建日志"


def test_post_tool_use_hook_skips_whitespace_description(tmp_path: Path):
    """ADR-013: description 仅空白时也不写日志。"""
    repo = init_repo(tmp_path)
    proc = run(repo, "hook", "post-tool-use",
               "--tool-name", "Agent",
               "--description", "   ")
    assert proc.returncode == 0
    log_path = repo / ".git" / "spec-vc-subagent-sessions.log"
    assert not log_path.exists(), "纯空白 description 时不应创建日志"


def test_post_tool_use_hook_reads_stdin_json(tmp_path: Path):
    """ADR-016: 无 CLI 参数时从 stdin JSON 提取 tool_name 与 tool_input.description。"""
    repo = init_repo(tmp_path)
    payload = json.dumps({
        "tool_name": "Agent",
        "tool_input": {"description": "stdin-driven audit", "prompt": "x", "subagent_type": "y"},
    })
    proc = run(repo, "hook", "post-tool-use", stdin=payload)
    assert proc.returncode == 0
    log_path = repo / ".git" / "spec-vc-subagent-sessions.log"
    assert log_path.exists()
    content = log_path.read_text()
    assert "Agent" in content
    assert "stdin-driven audit" in content


def test_post_tool_use_hook_cli_args_override_stdin(tmp_path: Path):
    """ADR-016: CLI 参数有值时优先于 stdin JSON。"""
    repo = init_repo(tmp_path)
    payload = json.dumps({
        "tool_name": "Agent",
        "tool_input": {"description": "from stdin"},
    })
    proc = run(repo, "hook", "post-tool-use",
               "--tool-name", "Agent",
               "--description", "from cli",
               stdin=payload)
    assert proc.returncode == 0
    log_path = repo / ".git" / "spec-vc-subagent-sessions.log"
    content = log_path.read_text()
    assert "from cli" in content
    assert "from stdin" not in content


def test_post_tool_use_hook_skips_empty_description_in_stdin(tmp_path: Path):
    """ADR-016 + ADR-013: stdin JSON 中 description 为空仍跳过写日志。"""
    repo = init_repo(tmp_path)
    payload = json.dumps({"tool_name": "Agent", "tool_input": {"description": ""}})
    proc = run(repo, "hook", "post-tool-use", stdin=payload)
    assert proc.returncode == 0
    log_path = repo / ".git" / "spec-vc-subagent-sessions.log"
    assert not log_path.exists()


def test_post_tool_use_hook_skips_when_tool_input_missing(tmp_path: Path):
    """ADR-016: stdin JSON 缺 tool_input 字段时跳过写日志。"""
    repo = init_repo(tmp_path)
    payload = json.dumps({"tool_name": "Agent"})
    proc = run(repo, "hook", "post-tool-use", stdin=payload)
    assert proc.returncode == 0
    log_path = repo / ".git" / "spec-vc-subagent-sessions.log"
    assert not log_path.exists()


def test_post_tool_use_hook_fail_open_on_invalid_json(tmp_path: Path):
    """ADR-016: stdin 非 JSON 文本时 fail-open（不抛错，不写日志）。"""
    repo = init_repo(tmp_path)
    proc = run(repo, "hook", "post-tool-use", stdin="not a json {{{")
    assert proc.returncode == 0
    assert proc.stderr == ""
    log_path = repo / ".git" / "spec-vc-subagent-sessions.log"
    assert not log_path.exists()


def test_post_tool_use_hook_skips_when_stdin_empty_and_no_args(tmp_path: Path):
    """ADR-016: 无 stdin 内容且无 CLI 参数时跳过（典型：终端手工调用）。"""
    repo = init_repo(tmp_path)
    proc = run(repo, "hook", "post-tool-use", stdin="")
    assert proc.returncode == 0
    log_path = repo / ".git" / "spec-vc-subagent-sessions.log"
    assert not log_path.exists()


def test_init_writes_post_tool_use_hook_without_args(tmp_path: Path):
    """ADR-016: spec-vc init 写入的 PostToolUse hook 命令不再带 --tool-name/--description。"""
    repo = init_empty_repo(tmp_path)
    run(repo, "init", check=True)
    settings = json.loads((repo / ".claude" / "settings.json").read_text())
    post_hooks = settings["hooks"]["PostToolUse"]
    cmds = [h["command"] for entry in post_hooks if entry.get("matcher") == "Agent" for h in entry.get("hooks", [])]
    assert cmds, "Agent matcher 下应有至少一条 spec-vc hook 命令"
    for cmd in cmds:
        assert "--tool-name" not in cmd
        assert "--description" not in cmd
        assert "CLAUDE_TOOL_DESCRIPTION" not in cmd
        assert cmd.endswith("hook post-tool-use")


def test_init_migrates_legacy_post_tool_use_hook(tmp_path: Path):
    """ADR-016: spec-vc init 自动把旧格式（含 --tool-name/--description）升级为新格式。"""
    repo = init_empty_repo(tmp_path)
    claude_dir = repo / ".claude"
    claude_dir.mkdir()
    legacy = {
        "hooks": {
            "PostToolUse": [{
                "matcher": "Agent",
                "hooks": [{
                    "type": "command",
                    "command": "/old/path/spec-vc hook post-tool-use --tool-name Agent --description \"${CLAUDE_TOOL_DESCRIPTION}\""
                }]
            }]
        }
    }
    (claude_dir / "settings.json").write_text(json.dumps(legacy))
    run(repo, "init", check=True)
    merged = json.loads((claude_dir / "settings.json").read_text())
    cmds = [h["command"] for entry in merged["hooks"]["PostToolUse"] for h in entry.get("hooks", [])]
    assert any(cmd.endswith("hook post-tool-use") and "--description" not in cmd for cmd in cmds)
    for cmd in cmds:
        assert "CLAUDE_TOOL_DESCRIPTION" not in cmd


def _write_session_log_with_ts(repo: Path, ts: str, description: str = "audit") -> Path:
    log_path = repo / ".git" / "spec-vc-subagent-sessions.log"
    log_path.write_text(f"{ts} | Agent | {description}\n")
    return log_path


def _touch_commit_msg(repo: Path, content: str = "feat: x [ADR-none]\n") -> Path:
    msg_path = repo / ".git" / "spec-vc-commit-msg"
    msg_path.write_text(content)
    return msg_path


def test_freshness_passes_when_review_newer_than_commit_msg(tmp_path: Path):
    """ADR-018: review.json mtime > commit-msg mtime → [ADR-NNN] 放行。"""
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("doc change\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    _touch_commit_msg(repo)
    _write_subagent_session(repo, adr_id="000")
    msg = repo / "msg.txt"
    msg.write_text("docs: update [ADR-000]\n")
    proc = run(repo, "hook", "commit-msg", str(msg))
    assert proc.returncode == 0, f"新鲜 review 应放行, stderr={proc.stderr}"


def test_freshness_blocks_when_review_older_than_commit_msg(tmp_path: Path):
    """ADR-018: review.json mtime <= commit-msg mtime → [ADR-NNN] 阻塞 BlockingError。"""
    import os
    import time
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("doc change\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    _write_subagent_session(repo, adr_id="000")
    time.sleep(0.01)
    _touch_commit_msg(repo)
    # 把 commit-msg mtime 强行设为 review.json mtime 之后
    rv = repo / ".git" / "spec-vc-review.json"
    msg_path = repo / ".git" / "spec-vc-commit-msg"
    new_ts = rv.stat().st_mtime + 5.0
    os.utime(msg_path, (new_ts, new_ts))
    msg = repo / "msg.txt"
    msg.write_text("docs: update [ADR-000]\n")
    proc = run(repo, "hook", "commit-msg", str(msg))
    assert proc.returncode != 0, "陈旧 review 应阻塞"
    assert "不新鲜" in proc.stderr
    assert "BLOCKED" in proc.stderr


def test_freshness_skips_when_no_commit_msg(tmp_path: Path):
    """ADR-018: 无 commit-msg 文件时跳过 mtime 新鲜度检查。"""
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("doc change\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    _write_subagent_session(repo, adr_id="000")
    assert not (repo / ".git" / "spec-vc-commit-msg").exists()
    msg = repo / "msg.txt"
    msg.write_text("docs: update [ADR-000]\n")
    proc = run(repo, "hook", "commit-msg", str(msg))
    assert proc.returncode == 0, f"无 commit-msg 时应跳过 mtime 检查, stderr={proc.stderr}"


def test_bypass_skips_freshness_check(tmp_path: Path):
    """ADR-013: SPEC_VC_BYPASS 同时旁路 session 检查与 freshness 检查。"""
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("doc change\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    _write_session_log_with_ts(repo, "2020-01-01T00:00:00+08:00", "stale audit")
    _touch_commit_msg(repo)
    msg = repo / "msg.txt"
    msg.write_text("docs: bypass [ADR-none]\n")
    proc = _run_with_env(
        repo, "hook", "commit-msg", str(msg),
        extra_env={"SPEC_VC_BYPASS": "emergency"},
    )
    assert proc.returncode == 0, f"bypass 应同时旁路 freshness, stderr={proc.stderr}"


def test_adr_none_skips_session_freshness_check(tmp_path: Path):
    """ADR-015: [ADR-none] 不检查 subagent session 和时间戳新鲜度，仅走豁免规则。"""
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("doc change\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    # 写陈旧 log → 如果是 [ADR-NNN] 会被阻塞，但 [ADR-none] 应跳过
    _write_session_log_with_ts(repo, "2020-01-01T00:00:00+08:00", "stale audit")
    _touch_commit_msg(repo)
    msg = repo / "msg.txt"
    msg.write_text("docs: update [ADR-none]\n")
    proc = run(repo, "hook", "commit-msg", str(msg))
    assert proc.returncode == 0, f"[ADR-none] 应跳过 session 检查, stderr={proc.stderr}"


# ─── ADR-018: review.json 与新 hook 校验链 ──────────────────────────────────


def test_compute_audit_anchor_stable_for_same_staged(tmp_path: Path):
    """ADR-017: 同一 staged 内容生成同一 anchor。"""
    from spec_vc.commit import compute_audit_anchor
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("hello\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    a1 = compute_audit_anchor(repo, "ADR-017")
    a2 = compute_audit_anchor(repo, "ADR-017")
    assert a1 == a2
    assert a1.startswith("ADR-017@")
    assert len(a1.split("@")[1]) == 12


def test_compute_audit_anchor_changes_with_staged(tmp_path: Path):
    """ADR-017: staged 内容变化 anchor 变化。"""
    from spec_vc.commit import compute_audit_anchor
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("v1\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    a1 = compute_audit_anchor(repo, "ADR-017")
    (repo / "README.md").write_text("v2\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    a2 = compute_audit_anchor(repo, "ADR-017")
    assert a1 != a2


def test_compute_audit_anchor_format_adr_none(tmp_path: Path):
    """ADR-017: [ADR-none] 也生成 anchor，格式 'ADR-none@<sha12>'。"""
    import re
    from spec_vc.commit import compute_audit_anchor
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("doc\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    a = compute_audit_anchor(repo, "ADR-none")
    assert re.match(r"^ADR-none@[0-9a-f]{12}$", a)


def test_commit_prepare_writes_audit_anchor_file(tmp_path: Path):
    """ADR-018: spec-vc commit prepare (deprecation alias) 写 review.json + anchor 格式正确。"""
    import json as _json
    import re
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("doc\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    proc = run(repo, "commit", "prepare", "--message", "docs: update [ADR-000]")
    assert proc.returncode == 0, proc.stderr
    review_path = repo / ".git" / "spec-vc-review.json"
    assert review_path.exists()
    record = _json.loads(review_path.read_text())
    assert re.match(r"^ADR-000@[0-9a-f]{12}$", record["anchor"])
    assert record["mode"] == "subagent"
    assert f"audit-anchor: {record['anchor']}" in proc.stdout
    assert "DEPRECATION" in proc.stderr


def test_post_tool_use_hook_skips_post_tool_use_failure(tmp_path: Path):
    """ADR-017: stdin JSON 中 hook_event_name == 'PostToolUseFailure' → 不写日志。"""
    repo = init_repo(tmp_path)
    payload = json.dumps({
        "hook_event_name": "PostToolUseFailure",
        "tool_name": "Agent",
        "tool_input": {"description": "would-write-if-not-failure"},
        "error": "API 429",
    })
    proc = run(repo, "hook", "post-tool-use", stdin=payload)
    assert proc.returncode == 0
    log_path = repo / ".git" / "spec-vc-subagent-sessions.log"
    assert not log_path.exists(), "PostToolUseFailure 时不应写日志"


def test_post_tool_use_hook_writes_for_normal_post_tool_use_event(tmp_path: Path):
    """ADR-017: hook_event_name 显式为 'PostToolUse' 时正常写日志。"""
    repo = init_repo(tmp_path)
    payload = json.dumps({
        "hook_event_name": "PostToolUse",
        "tool_name": "Agent",
        "tool_input": {"description": "ADR-017@a3f7c891b2d4 audit"},
    })
    proc = run(repo, "hook", "post-tool-use", stdin=payload)
    assert proc.returncode == 0
    log_path = repo / ".git" / "spec-vc-subagent-sessions.log"
    assert log_path.exists()
    assert "ADR-017@a3f7c891b2d4" in log_path.read_text()


def test_anchor_binding_passes_when_review_anchor_matches(tmp_path: Path):
    """ADR-018: review.json.anchor 匹配当前 staged sha12 → 放行。"""
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("doc\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    _write_subagent_session(repo, adr_id="000")
    msg = repo / "msg.txt"
    msg.write_text("docs: update [ADR-000]\n")
    proc = run(repo, "hook", "commit-msg", str(msg))
    assert proc.returncode == 0, f"匹配 anchor 应放行, stderr={proc.stderr}"


def test_anchor_binding_blocks_when_anchor_mismatch(tmp_path: Path):
    """ADR-018: review.json.anchor 与当前 staged sha12 不匹配 → 阻塞 + expected/actual。"""
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("doc\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    fake_anchor = "ADR-000@deadbeefcafe"
    _write_subagent_session(repo, anchor=fake_anchor)
    msg = repo / "msg.txt"
    msg.write_text("docs: update [ADR-000]\n")
    proc = run(repo, "hook", "commit-msg", str(msg))
    assert proc.returncode != 0, "anchor 不匹配应阻塞"
    assert "不匹配" in proc.stderr
    assert "expected:" in proc.stderr
    assert "actual:" in proc.stderr
    assert fake_anchor in proc.stderr


def test_anchor_binding_blocks_when_review_missing_with_adr_nnn(tmp_path: Path):
    """ADR-018: [ADR-NNN] + review.json 不存在 → 阻塞 + 提示 spec-vc review 命令。"""
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("doc\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    msg = repo / "msg.txt"
    msg.write_text("docs: update [ADR-000]\n")
    proc = run(repo, "hook", "commit-msg", str(msg))
    assert proc.returncode != 0
    assert "review.json" in proc.stderr
    assert "spec-vc review" in proc.stderr


def test_anchor_binding_skipped_for_adr_none(tmp_path: Path):
    """ADR-018: [ADR-none] 不检查 review.json（走量化判定）。"""
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("doc\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    assert not (repo / ".git" / "spec-vc-review.json").exists()
    msg = repo / "msg.txt"
    msg.write_text("docs: update [ADR-none]\n")
    proc = run(repo, "hook", "commit-msg", str(msg))
    assert proc.returncode == 0, f"[ADR-none] 应跳过 review 检查, stderr={proc.stderr}"


def test_bypass_skips_anchor_binding(tmp_path: Path):
    """ADR-018: SPEC_VC_BYPASS 旁路 review.json 检查。"""
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("doc\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    msg = repo / "msg.txt"
    msg.write_text("docs: update [ADR-000]\n")
    proc = _run_with_env(
        repo, "hook", "commit-msg", str(msg),
        extra_env={"SPEC_VC_BYPASS": "emergency"},
    )
    assert proc.returncode == 0, f"BYPASS 应旁路 review 检查, stderr={proc.stderr}"


def test_review_simple_mode_with_anchor_in_note_passes(tmp_path: Path):
    """ADR-018: simple 模式 --note 含 anchor → 成功 + review.json 含 simple mode。"""
    import json as _json
    from spec_vc.commit import compute_audit_anchor

    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("doc\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    anchor = compute_audit_anchor(repo, "ADR-000")
    note = f"已读 staged diff 指纹 {anchor}，结论：无问题"
    proc = run(repo, "review", "--mode", "simple", "--message", "docs: x [ADR-000]", "--note", note)
    assert proc.returncode == 0, proc.stderr
    record = _json.loads((repo / ".git" / "spec-vc-review.json").read_text())
    assert record["mode"] == "simple"
    assert anchor in record["note"]


def test_review_verified_flag_written(tmp_path: Path):
    """ADR-018: --verified 写入 review.json.verified=true。"""
    import json as _json
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("doc\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    proc = run(repo, "review", "--message", "docs: x [ADR-000]", "--verified")
    assert proc.returncode == 0
    record = _json.loads((repo / ".git" / "spec-vc-review.json").read_text())
    assert record["verified"] is True


# ─── ADR-018: BlockingError 结构 + require_user_verified 升级开关 ─────────


def test_blocking_error_output_contains_four_sections(tmp_path: Path):
    """ADR-018: hook 阻塞 stderr 必须含 reason / current_state / fix_commands / docs_ref 四段。"""
    repo = init_repo(tmp_path)
    (repo / "README.md").write_text("doc\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    msg = repo / "msg.txt"
    msg.write_text("docs: update [ADR-000]\n")
    proc = run(repo, "hook", "commit-msg", str(msg))
    assert proc.returncode != 0
    assert "BLOCKED:" in proc.stderr
    assert "Current state:" in proc.stderr
    assert "How to fix:" in proc.stderr
    assert "Docs:" in proc.stderr
    # fix_commands 至少一条以 "$" 前缀
    assert "$ " in proc.stderr


def test_post_tool_use_still_writes_session_log(tmp_path: Path):
    """ADR-018: PostToolUse hook 仍写 session log（保留为辅助日志，commit-msg hook 不再读）。"""
    repo = init_repo(tmp_path)
    payload = json.dumps({
        "hook_event_name": "PostToolUse",
        "tool_name": "Agent",
        "tool_input": {"description": "test audit"},
    })
    proc = run(repo, "hook", "post-tool-use", stdin=payload)
    assert proc.returncode == 0
    log_path = repo / ".git" / "spec-vc-subagent-sessions.log"
    assert log_path.exists()
    assert "test audit" in log_path.read_text()
