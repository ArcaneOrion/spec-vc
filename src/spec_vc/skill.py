from __future__ import annotations

from pathlib import Path

from .change import change_context, infer_adr_required
from .config import load_config
from .gitops import repo_root_from, run_git


def load_subsystem_context(cwd: Path, user_prompt: str = "") -> dict[str, object]:
    repo_root = repo_root_from(cwd)
    config = load_config(repo_root)
    adr_dir = repo_root / config.project.adr_dir
    initialized = adr_dir.exists()
    dirty = bool(run_git(repo_root, 'status', '--porcelain', check=False).strip())
    context: dict[str, object] = {
        'repo_root': repo_root,
        'initialized': initialized,
        'dirty': dirty,
    }
    if initialized:
        context.update(change_context(adr_dir))
        staged = [line.strip().split(maxsplit=1)[-1] for line in run_git(repo_root, 'status', '--porcelain', check=False).splitlines() if line.strip()]
        required, reason = infer_adr_required(staged, user_prompt, config.adr_required)
        context['adr_required'] = required
        context['adr_required_reason'] = reason
    return context
