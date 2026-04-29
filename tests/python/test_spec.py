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


def test_spec_new_creates_subdir_and_files(tmp_path: Path):
    repo = init_repo(tmp_path)
    proc = run(repo, "spec", "new", "用户认证接口契约", "--adr", "ADR-000")
    assert proc.returncode == 0
    assert "Spec-001" in proc.stdout

    base = repo / "doc" / "arch" / "specs" / "001"
    assert base.is_dir()
    assert (base / "dev-doc.md").exists()
    assert (base / "contract.openapi.yaml").exists()
    assert (base / "schema.json").exists()
    assert (base / "behavior.feature").exists()

    content = (base / "dev-doc.md").read_text()
    assert "Spec-001" in content
    assert "用户认证接口契约" in content
    assert "ADR-000" in content


def test_spec_new_rejects_nonexistent_adr(tmp_path: Path):
    repo = init_repo(tmp_path)
    proc = run(repo, "spec", "new", "测试", "--adr", "ADR-999")
    assert proc.returncode != 0
    assert "ADR-999" in proc.stderr


def test_spec_new_requires_adr(tmp_path: Path):
    repo = init_repo(tmp_path)
    proc = run(repo, "spec", "new", "测试")
    assert proc.returncode != 0


def test_spec_list_empty(tmp_path: Path):
    repo = init_repo(tmp_path)
    proc = run(repo, "spec", "list")
    assert proc.returncode == 0
    assert "尚无 Spec 文件" in proc.stdout


def test_spec_list_shows_specs(tmp_path: Path):
    repo = init_repo(tmp_path)
    run(repo, "spec", "new", "用户认证", "--adr", "ADR-000")
    proc = run(repo, "spec", "list")
    assert proc.returncode == 0
    assert "Spec-001" in proc.stdout
    assert "用户认证" in proc.stdout
    assert "Draft" in proc.stdout
    assert "ADR-000" in proc.stdout


def test_spec_show_displays_dev_doc(tmp_path: Path):
    repo = init_repo(tmp_path)
    run(repo, "spec", "new", "用户认证", "--adr", "ADR-000")
    proc = run(repo, "spec", "show", "001")
    assert proc.returncode == 0
    assert "用户认证" in proc.stdout
    assert "ADR-000" in proc.stdout
    assert "## 概述" in proc.stdout
    assert "## 接口契约" in proc.stdout
    assert "形式化文件" in proc.stdout


def test_spec_show_rejects_nonexistent(tmp_path: Path):
    repo = init_repo(tmp_path)
    proc = run(repo, "spec", "show", "999")
    assert proc.returncode != 0
    assert "Spec-999" in proc.stderr


def test_spec_id_increments(tmp_path: Path):
    repo = init_repo(tmp_path)
    run(repo, "spec", "new", "第一个", "--adr", "ADR-000")
    run(repo, "spec", "new", "第二个", "--adr", "ADR-000")
    assert (repo / "doc" / "arch" / "specs" / "001").is_dir()
    assert (repo / "doc" / "arch" / "specs" / "002").is_dir()


def _fill_sections(doc: str) -> str:
    """Replace section placeholders with targetable content."""
    import re

    # Helper: replace the body of a ## section
    # Handles both old ("待补充") and new (HTML comments + tables) template formats
    def _replace_section(text: str, name: str, body: str) -> str:
        # Match: ## name\n  optionally followed by comment line(s)  then blank line
        pattern = re.compile(
            rf"(## {re.escape(name)}\n(?:<!--.*?-->\n)*\n)(.*?)(?=\n## |\Z)", re.S
        )
        return pattern.sub(rf"\1{body}\n\n", text, count=1)

    doc = _replace_section(doc, "概述", "认证模块的接口规格，覆盖登录和 Token 刷新。")
    doc = _replace_section(doc, "接口契约", "```yaml\nPOST /login:\n  request:\n    username: string\n```")
    doc = _replace_section(doc, "数据形状", "Token 使用 JWT RS256 签名。")
    doc = _replace_section(doc, "行为规则", "Feature: 连续失败 3 次锁定账户\n\nScenario: 失败计数器")
    doc = _replace_section(doc, "测试策略", "验收标准: 登录成功返回 200。")
    doc = _replace_section(doc, "日志实现", "INFO 级别记录登录事件，包含 user_id 和 trace_id。")
    return doc


def test_spec_formalize_extracts_openapi(tmp_path: Path):
    repo = init_repo(tmp_path)
    run(repo, "spec", "new", "用户认证", "--adr", "ADR-000")
    base = repo / "doc" / "arch" / "specs" / "001"
    doc = _fill_sections((base / "dev-doc.md").read_text())
    (base / "dev-doc.md").write_text(doc)

    proc = run(repo, "spec", "formalize", "001", "--type", "openapi")
    assert proc.returncode == 0
    assert "contract.openapi.yaml" in proc.stdout
    out = (base / "contract.openapi.yaml").read_text()
    assert "POST /login" in out


def test_spec_formalize_rejects_empty_section(tmp_path: Path):
    repo = init_repo(tmp_path)
    run(repo, "spec", "new", "用户认证", "--adr", "ADR-000")
    # 新模板有结构化占位内容，需显式清空区块来测试拒绝逻辑
    base = repo / "doc" / "arch" / "specs" / "001"
    doc = (base / "dev-doc.md").read_text()
    import re as _re
    def _clear_sec(text: str, name: str) -> str:
        pat = _re.compile(rf"(## {_re.escape(name)}\n(?:<!--.*?-->\n)*\n)(.*?)(?=\n## |\Z)", _re.S)
        return pat.sub(r"\1待补充\n\n", text, count=1)
    doc = _clear_sec(doc, "接口契约")
    (base / "dev-doc.md").write_text(doc)
    proc = run(repo, "spec", "formalize", "001", "--type", "openapi")
    assert proc.returncode != 0
    assert "无法生成" in proc.stderr


def test_spec_formalize_all_types(tmp_path: Path):
    repo = init_repo(tmp_path)
    run(repo, "spec", "new", "用户认证", "--adr", "ADR-000")
    base = repo / "doc" / "arch" / "specs" / "001"
    doc = _fill_sections((base / "dev-doc.md").read_text())
    (base / "dev-doc.md").write_text(doc)

    proc = run(repo, "spec", "formalize", "001", "--type", "all")
    assert proc.returncode == 0
    for fname in ["contract.openapi.yaml", "schema.json", "behavior.feature"]:
        assert (base / fname).stat().st_size > 0


def test_spec_show_accepts_spec_prefix(tmp_path: Path):
    repo = init_repo(tmp_path)
    run(repo, "spec", "new", "用户认证", "--adr", "ADR-000")
    proc = run(repo, "spec", "show", "Spec-001")
    assert proc.returncode == 0
    assert "用户认证" in proc.stdout


def test_skill_load_includes_spec_context(tmp_path: Path):
    repo = init_repo(tmp_path)
    run(repo, "spec", "new", "用户认证", "--adr", "ADR-000")
    proc = run(repo, "skill", "load")
    assert proc.returncode == 0
    assert "spec_count: 1" in proc.stdout
    assert "recent Spec-001" in proc.stdout


def test_skill_load_zero_specs(tmp_path: Path):
    repo = init_repo(tmp_path)
    proc = run(repo, "skill", "load")
    assert proc.returncode == 0
    assert "spec_count: 0" in proc.stdout


def test_spec_check_all_ready(tmp_path: Path):
    repo = init_repo(tmp_path)
    run(repo, "spec", "new", "用户认证", "--adr", "ADR-000")
    base = repo / "doc" / "arch" / "specs" / "001"
    doc = _fill_sections((base / "dev-doc.md").read_text())
    (base / "dev-doc.md").write_text(doc)
    run(repo, "spec", "formalize", "001", "--type", "all")

    proc = run(repo, "spec", "check")
    assert proc.returncode == 0
    assert "就绪" in proc.stdout


def test_spec_check_empty_dev_doc_sections(tmp_path: Path):
    repo = init_repo(tmp_path)
    run(repo, "spec", "new", "用户认证", "--adr", "ADR-000")

    proc = run(repo, "spec", "check")
    assert proc.returncode == 1
    assert "dev-doc.md" in proc.stdout
    assert "未完成" in proc.stdout


def test_spec_check_skeleton_formal_files(tmp_path: Path):
    repo = init_repo(tmp_path)
    run(repo, "spec", "new", "用户认证", "--adr", "ADR-000")
    base = repo / "doc" / "arch" / "specs" / "001"
    doc = _fill_sections((base / "dev-doc.md").read_text())
    (base / "dev-doc.md").write_text(doc)
    # formal files not generated — still skeleton

    proc = run(repo, "spec", "check")
    assert proc.returncode == 1
    assert "形式化文件未生成" in proc.stdout


def test_commit_blocks_on_incomplete_specs(tmp_path: Path):
    repo = init_repo(tmp_path)
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "main.py").write_text("print('test')")
    import subprocess
    subprocess.run(["git", "add", "src/main.py"], cwd=repo, check=True)

    run(repo, "spec", "new", "用户认证", "--adr", "ADR-000")
    # dev-doc still "待补充", formal files still skeleton

    proc = run(repo, "commit")
    assert proc.returncode == 1
    assert "Spec 就绪检查" in proc.stderr
    assert "未通过" in proc.stderr


def test_commit_passes_with_ready_specs(tmp_path: Path):
    repo = init_repo(tmp_path)
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "main.py").write_text("print('test')")
    import subprocess
    subprocess.run(["git", "add", "src/main.py"], cwd=repo, check=True)

    run(repo, "spec", "new", "用户认证", "--adr", "ADR-000")
    base = repo / "doc" / "arch" / "specs" / "001"
    doc = _fill_sections((base / "dev-doc.md").read_text())
    (base / "dev-doc.md").write_text(doc)
    run(repo, "spec", "formalize", "001", "--type", "all")

    proc = run(repo, "commit")
    assert proc.returncode == 0
    import json
    manifest = json.loads(proc.stdout)
    assert "audit_units" in manifest
    assert len(manifest["audit_units"]) == 1
    assert manifest["audit_units"][0]["spec_id"] == "001"
    assert "Spec-001" in proc.stderr


def test_adr_show_displays_content(tmp_path: Path):
    repo = init_repo(tmp_path)
    proc = run(repo, "adr", "show", "000")
    assert proc.returncode == 0
    assert "ADR-000" in proc.stdout
    assert "采用 ADR 方法论" in proc.stdout


def test_adr_show_rejects_nonexistent(tmp_path: Path):
    repo = init_repo(tmp_path)
    proc = run(repo, "adr", "show", "999")
    assert proc.returncode != 0
    assert "ADR-999" in proc.stderr


def test_adr_show_accepts_adr_prefix(tmp_path: Path):
    repo = init_repo(tmp_path)
    proc = run(repo, "adr", "show", "ADR-000")
    assert proc.returncode == 0
    assert "ADR-000" in proc.stdout


def test_spec_show_formal_displays_content(tmp_path: Path):
    repo = init_repo(tmp_path)
    run(repo, "spec", "new", "用户认证", "--adr", "ADR-000")
    base = repo / "doc" / "arch" / "specs" / "001"
    doc = _fill_sections((base / "dev-doc.md").read_text())
    (base / "dev-doc.md").write_text(doc)
    run(repo, "spec", "formalize", "001", "--type", "all")

    proc = run(repo, "spec", "show", "001", "--formal")
    assert proc.returncode == 0
    assert "用户认证" in proc.stdout
    assert "[contract.openapi.yaml]" in proc.stdout
    assert "[schema.json]" in proc.stdout
    assert "[behavior.feature]" in proc.stdout
    assert "POST /login" in proc.stdout
