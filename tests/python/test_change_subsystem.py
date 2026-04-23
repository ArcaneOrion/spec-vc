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


def test_change_start_creates_plan_and_active(tmp_path: Path):
    repo = init_repo(tmp_path)
    proc = run(repo, 'change', 'start', '--adr', 'ADR-000', '--summary', '准备实施 LDAP 细则')
    assert proc.returncode == 0
    assert 'ADR-000-plan-001.md' in proc.stdout
    plan = repo / 'doc' / 'arch' / 'plans' / 'ADR-000-plan-001.md'
    active = repo / 'doc' / 'arch' / 'plans' / '_active.md'
    assert plan.exists()
    assert active.exists()


def test_change_start_recovers_existing_active(tmp_path: Path):
    repo = init_repo(tmp_path)
    run(repo, 'change', 'start', '--adr', '000', '--summary', '第一次')
    proc = run(repo, 'change', 'start', '--adr', '000', '--summary', '第二次')
    assert proc.returncode == 0
    assert 'active ADR: ADR-000' in proc.stdout


def test_change_close_clears_active(tmp_path: Path):
    repo = init_repo(tmp_path)
    run(repo, 'change', 'start', '--adr', '000', '--summary', '第一次')
    proc = run(repo, 'change', 'close')
    assert proc.returncode == 0
    assert not (repo / 'doc' / 'arch' / 'plans' / '_active.md').exists()
