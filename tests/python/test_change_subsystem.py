from __future__ import annotations

import subprocess
from pathlib import Path
import sys
import os


def run(repo: Path, *args: str):
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, 'PYTHONPATH': str(root / 'src')}
    return subprocess.run([sys.executable, '-m', 'spec_vc.cli', *args], cwd=repo, text=True, capture_output=True, env=env)


def init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / 'repo'
    repo.mkdir()
    subprocess.run(['git', 'init', '-q'], cwd=repo, check=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=repo, check=True)
    subprocess.run(['git', 'config', 'user.name', 'test'], cwd=repo, check=True)
    root = Path(__file__).resolve().parents[2]
    (repo / '.spec-vc.toml').write_text((root / '.spec-vc.toml').read_text())
    (repo / 'doc' / 'arch').mkdir(parents=True)
    (repo / 'doc' / 'arch' / 'README.md').write_text((root / 'templates' / 'index.md').read_text())
    seed = (root / 'templates' / 'seed-adr-000.md').read_text().replace('{{DATE}}', '2026-04-23').replace('{{AUTHOR}}', 'test')
    (repo / 'doc' / 'arch' / 'adr-000.md').write_text(seed)
    return repo


def test_skill_load_reports_context(tmp_path: Path):
    repo = init_repo(tmp_path)
    proc = run(repo, 'skill', 'load')
    assert proc.returncode == 0
    assert 'initialized: True' in proc.stdout
    assert 'recent ADR-000' in proc.stdout


def test_skill_load_auto_routes_adr_required(tmp_path: Path):
    repo = init_repo(tmp_path)
    (repo / 'src').mkdir()
    (repo / 'src' / 'main.py').write_text('print(1)\n')
    proc = run(repo, 'skill', 'load', '--user-prompt', '我要重构状态机')
    assert proc.returncode == 0
    assert 'adr_required: True' in proc.stdout


def test_change_start_creates_plan_and_active(tmp_path: Path):
    repo = init_repo(tmp_path)
    proc = run(repo, 'change', 'start', '--adr', 'ADR-000', '--summary', '准备实施 LDAP 细则')
    assert proc.returncode == 0
    assert 'ADR-000-plan-001.md' in proc.stdout
    plan = repo / 'doc' / 'arch' / 'plans' / 'ADR-000-plan-001.md'
    active = repo / 'doc' / 'arch' / 'plans' / '_active.md'
    assert plan.exists()
    assert active.exists()


def test_change_next_question_without_active_change_fails(tmp_path: Path):
    repo = init_repo(tmp_path)
    proc = run(repo, 'change', 'next-question')
    assert proc.returncode == 1
    assert '当前没有 active change' in proc.stderr


def test_change_next_question_reports_missing(tmp_path: Path):
    repo = init_repo(tmp_path)
    run(repo, 'change', 'start', '--adr', '000', '--summary', '第一次')
    proc = run(repo, 'change', 'next-question')
    assert proc.returncode == 0
    assert 'missing:' in proc.stdout
    assert 'motivation' in proc.stdout


def test_change_clarify_supports_incremental_updates(tmp_path: Path):
    repo = init_repo(tmp_path)
    run(repo, 'change', 'start', '--adr', '000', '--summary', '第一次')

    first = run(repo, 'change', 'clarify', '--motivation', '这是重构 CLI 的必要步骤')
    assert first.returncode == 1
    assert 'missing:' in first.stdout
    first_plan = (repo / 'doc' / 'arch' / 'plans' / 'ADR-000-plan-001.md').read_text()
    assert '这是重构 CLI 的必要步骤' in first_plan

    second = run(repo, 'change', 'clarify', '--boundary', '只改 hooks 和 CLI', '--implementation', '先补 change 阶段命令再回填 ADR')
    assert second.returncode == 1
    assert 'missing:' in second.stdout
    second_plan = (repo / 'doc' / 'arch' / 'plans' / 'ADR-000-plan-001.md').read_text()
    assert '这是重构 CLI 的必要步骤' in second_plan
    assert '只改 hooks 和 CLI' in second_plan
    assert '先补 change 阶段命令再回填 ADR' in second_plan
    assert '- **Stage**: clarify' in second_plan


def test_change_clarify_reports_missing_fields(tmp_path: Path):
    repo = init_repo(tmp_path)
    run(repo, 'change', 'start', '--adr', '000', '--summary', '第一次')
    proc = run(repo, 'change', 'clarify', '--motivation', '这是测试')
    assert proc.returncode == 1
    assert 'missing:' in proc.stdout
    plan = (repo / 'doc' / 'arch' / 'plans' / 'ADR-000-plan-001.md').read_text()
    assert '待补充字段' in plan
    assert '- **Stage**: clarify' in plan


def test_change_clarify_updates_plan_when_complete(tmp_path: Path):
    repo = init_repo(tmp_path)
    run(repo, 'change', 'start', '--adr', '000', '--summary', '第一次')
    proc = run(
        repo,
        'change', 'clarify',
        '--motivation', '明确改动目标',
        '--boundary', '只改 hooks 和 CLI',
        '--design', '不改 Layer 3 架构',
        '--implementation', '先补 change 阶段命令再回填 ADR',
        '--verification', '能记录 clarify 并进入 plan',
        '--rollback', '可能破坏旧工作流，需要保留 e2e',
    )
    assert proc.returncode == 0
    plan = (repo / 'doc' / 'arch' / 'plans' / 'ADR-000-plan-001.md').read_text()
    assert '明确改动目标' in plan
    assert 'Clarification History' in plan
    assert '- **Stage**: plan' in plan

    question = run(repo, 'change', 'next-question')
    assert question.returncode == 0
    assert 'missing: ' not in question.stdout  # all fields filled, no missing


def test_change_validate_writes_pre_and_post(tmp_path: Path):
    repo = init_repo(tmp_path)
    run(repo, 'change', 'start', '--adr', '000', '--summary', '第一次')
    run(
        repo,
        'change', 'clarify',
        '--motivation', '明确改动目标',
        '--boundary', '只改 hooks 和 CLI',
        '--design', '不改 Layer 3 架构',
        '--implementation', '先补 change 阶段命令再回填 ADR',
        '--verification', '能记录 clarify 并进入 plan',
        '--rollback', '可能破坏旧工作流，需要保留 e2e',
    )
    pre = run(repo, 'change', 'validate', '--phase', 'pre', '--content', '修改前运行 pytest 和 e2e')
    post = run(repo, 'change', 'validate', '--phase', 'post', '--content', '修改后再次运行 pytest 和 e2e')
    assert pre.returncode == 0
    assert post.returncode == 0
    plan = (repo / 'doc' / 'arch' / 'plans' / 'ADR-000-plan-001.md').read_text()
    assert '修改前运行 pytest 和 e2e' in plan
    assert '修改后再次运行 pytest 和 e2e' in plan


def test_change_close_backfills_adr_and_refs(tmp_path: Path):
    repo = init_repo(tmp_path)
    run(repo, 'change', 'start', '--adr', '000', '--summary', '第一次')
    run(
        repo,
        'change', 'clarify',
        '--motivation', '明确改动目标',
        '--boundary', '只改 hooks 和 CLI',
        '--design', '不改 Layer 3 架构',
        '--implementation', '先补 change 阶段命令再回填 ADR',
        '--verification', '能记录 clarify 并进入 plan',
        '--rollback', '可能破坏旧工作流，需要保留 e2e',
    )
    run(repo, 'change', 'validate', '--phase', 'pre', '--content', '修改前通过')
    run(repo, 'change', 'validate', '--phase', 'post', '--content', '修改后通过')
    proc = run(repo, 'change', 'close', '--summary', '完成 clarify/validate/回填闭环')
    assert proc.returncode == 0
    adr = (repo / 'doc' / 'arch' / 'adr-000.md').read_text()
    plan = (repo / 'doc' / 'arch' / 'plans' / 'ADR-000-plan-001.md').read_text()
    assert '## Implementation Plans' in adr
    assert '完成 clarify/validate/回填闭环' in adr
    assert '- **Plan**: doc/arch/plans/ADR-000-plan-001.md' in adr
    assert '- **Commits**:' in adr
    assert '- **Plan**: doc/arch/plans/ADR-000-plan-001.md' in plan
    assert '- **Stage**: close' in plan
    assert not (repo / 'doc' / 'arch' / 'plans' / '_active.md').exists()


def test_change_start_recovers_existing_active(tmp_path: Path):
    repo = init_repo(tmp_path)
    run(repo, 'change', 'start', '--adr', '000', '--summary', '第一次')
    proc = run(repo, 'change', 'start', '--adr', '000', '--summary', '第二次')
    assert proc.returncode == 0
    assert 'active ADR: ADR-000' in proc.stdout


def test_change_should_adr_for_code_paths(tmp_path: Path):
    repo = init_repo(tmp_path)
    proc = run(repo, 'change', 'should-adr', 'src/main.py')
    assert proc.returncode == 0
    assert 'required: True' in proc.stdout


def test_change_should_adr_for_docs_only(tmp_path: Path):
    repo = init_repo(tmp_path)
    proc = run(repo, 'change', 'should-adr', 'README.md', 'doc/notes.md')
    assert proc.returncode == 1
    assert 'required: False' in proc.stdout


def test_change_validate_pre_blocks_on_incomplete_specs(tmp_path: Path):
    repo = init_repo(tmp_path)
    run(repo, 'change', 'start', '--adr', '000', '--summary', '第一次')
    run(
        repo,
        'change', 'clarify',
        '--motivation', '明确改动目标',
        '--boundary', '只改 hooks 和 CLI',
        '--design', '不改 Layer 3 架构',
        '--implementation', '先补 change 阶段命令再回填 ADR',
        '--verification', '能记录 clarify 并进入 plan',
        '--rollback', '可能破坏旧工作流，需要保留 e2e',
    )
    # 创建 Spec 但不填写 dev-doc 也不 formalize
    run(repo, 'spec', 'new', '用户认证', '--adr', 'ADR-000')

    proc = run(repo, 'change', 'validate', '--phase', 'pre', '--content', '修改前验证')
    assert proc.returncode == 1
    assert 'Spec 就绪检查' in proc.stdout
    assert '未通过' in proc.stdout
    assert 'dev-doc.md' in proc.stdout


def test_change_validate_pre_passes_with_ready_specs(tmp_path: Path):
    repo = init_repo(tmp_path)
    run(repo, 'change', 'start', '--adr', '000', '--summary', '第一次')
    run(
        repo,
        'change', 'clarify',
        '--motivation', '明确改动目标',
        '--boundary', '只改 hooks 和 CLI',
        '--design', '不改 Layer 3 架构',
        '--implementation', '先补 change 阶段命令再回填 ADR',
        '--verification', '能记录 clarify 并进入 plan',
        '--rollback', '可能破坏旧工作流，需要保留 e2e',
    )
    run(repo, 'spec', 'new', '用户认证', '--adr', 'ADR-000')
    # 填写 dev-doc
    base = repo / 'doc' / 'arch' / 'specs' / '001'
    doc = (base / 'dev-doc.md').read_text()
    sections = [
        ('## 概述\n\n待补充', '## 概述\n\n认证模块接口规格。'),
        ('## 接口契约\n\n待补充', '## 接口契约\n\n```yaml\nPOST /login\n```'),
        ('## 数据形状\n\n待补充', '## 数据形状\n\nJWT RS256 签名。'),
        ('## 行为规则\n\n待补充', '## 行为规则\n\nFeature: 连续失败锁定\n'),
    ]
    for old, new in sections:
        doc = doc.replace(old, new)
    (base / 'dev-doc.md').write_text(doc)
    run(repo, 'spec', 'formalize', '001', '--type', 'all')

    proc = run(repo, 'change', 'validate', '--phase', 'pre', '--content', '修改前验证')
    assert proc.returncode == 0
    plan = (repo / 'doc' / 'arch' / 'plans' / 'ADR-000-plan-001.md').read_text()
    assert '- **Stage**: implement-ready' in plan


def test_change_show_displays_plan_content(tmp_path: Path):
    repo = init_repo(tmp_path)
    run(repo, 'change', 'start', '--adr', '000', '--summary', '重构 CLI')
    proc = run(repo, 'change', 'show')
    assert proc.returncode == 0
    assert 'ADR-000 执行方案' in proc.stdout
    assert '重构 CLI' in proc.stdout
    assert '## Motivation and Context' in proc.stdout


def test_change_show_rejects_no_active(tmp_path: Path):
    repo = init_repo(tmp_path)
    proc = run(repo, 'change', 'show')
    assert proc.returncode != 0
    assert '当前没有 active change' in proc.stderr
