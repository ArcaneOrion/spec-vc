from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .adr import list_adrs, next_adr_id, render_adr, validate_title
from .config import load_config
from .errors import SpecVCError, UsageError
from .change import clear_active, create_plan, load_active
from .skill import load_subsystem_context
from .gitops import repo_root_from, run_git
from .hooks import run_commit_msg, run_prepare_commit_msg
from .index import update_index
from .status import build_status
from .templates import template_path


def _repo_root() -> Path:
    return repo_root_from(Path.cwd())


def cmd_adr_list(_args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    config = load_config(repo_root)
    adr_dir = repo_root / config.project.adr_dir
    for adr in list_adrs(adr_dir):
        print(f"ADR-{adr.adr_id} [{adr.status}] {adr.title}")
    return 0


def cmd_adr_new(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    config = load_config(repo_root)
    adr_dir = repo_root / config.project.adr_dir
    title = validate_title(args.title)
    adr_id = next_adr_id(adr_dir)
    output = adr_dir / f"adr-{adr_id}.md"
    if output.exists():
        raise UsageError(f"目标 ADR 已存在: {output}")
    author = run_git(repo_root, "config", "user.name", check=False).strip() or "unknown"
    content = render_adr(template_path("adr.md").read_text(), adr_id, title, author)
    output.write_text(content)
    update_index(adr_dir)
    print(output)
    print(f"推荐 commit message: feat(<scope>): <subject> [ADR-{adr_id}]")
    return 0


def cmd_adr_status(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    config = load_config(repo_root)
    report = build_status(repo_root, repo_root / config.project.adr_dir, rev_range=args.rev_range)
    for item in report.errors:
        print(f"ERROR: {item}")
    for item in report.warnings:
        print(f"WARN: {item}")
    return 1 if report.errors else 0




def cmd_change_start(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    config = load_config(repo_root)
    adr_dir = repo_root / config.project.adr_dir
    context = load_subsystem_context(Path.cwd())
    active = context.get("active")
    if active is not None:
        print(f"active ADR: ADR-{active.adr_id}")
        print(f"plan: {active.plan_path}")
        print(f"stage: {active.stage}")
        return 0
    if not args.adr:
        raise UsageError("change start 需要 --adr ADR-NNN 或三位编号")
    adr_id = args.adr.replace("ADR-", "").zfill(3)
    plan = create_plan(adr_dir, adr_id, args.summary or "待澄清的变更")
    print(plan)
    return 0


def cmd_change_show_active(_args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    config = load_config(repo_root)
    active = load_active(repo_root / config.project.adr_dir)
    if active is None:
        print("no active change")
        return 0
    print(f"ADR-{active.adr_id} {active.stage} {active.plan_path}")
    return 0


def cmd_change_close(_args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    config = load_config(repo_root)
    adr_dir = repo_root / config.project.adr_dir
    active = load_active(adr_dir)
    if active is None:
        raise UsageError("当前没有 active change")
    clear_active(adr_dir)
    print(f"closed ADR-{active.adr_id}")
    return 0


def cmd_skill_load(_args: argparse.Namespace) -> int:
    context = load_subsystem_context(Path.cwd())
    print(f"initialized: {context['initialized']}")
    print(f"dirty: {context['dirty']}")
    active = context.get('active')
    if active is not None:
        print(f"active ADR: ADR-{active.adr_id}")
        print(f"active stage: {active.stage}")
    recent = context.get('recent_adrs', [])
    for adr in recent:
        print(f"recent ADR-{adr.adr_id} [{adr.status}] {adr.title}")
    return 0

def cmd_hook_commit_msg(args: argparse.Namespace) -> int:
    return run_commit_msg(Path(args.message_file))


def cmd_hook_prepare_commit_msg(args: argparse.Namespace) -> int:
    return run_prepare_commit_msg(Path(args.message_file), args.source or "", args.sha or "")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spec-vc")
    sub = parser.add_subparsers(dest="command")

    adr = sub.add_parser("adr")
    adr_sub = adr.add_subparsers(dest="adr_command")

    adr_list = adr_sub.add_parser("list")
    adr_list.set_defaults(func=cmd_adr_list)

    adr_new = adr_sub.add_parser("new")
    adr_new.add_argument("title")
    adr_new.set_defaults(func=cmd_adr_new)

    adr_status = adr_sub.add_parser("status")
    adr_status.add_argument("--rev-range")
    adr_status.set_defaults(func=cmd_adr_status)

    change = sub.add_parser("change")
    change_sub = change.add_subparsers(dest="change_command")

    change_start = change_sub.add_parser("start")
    change_start.add_argument("--adr", required=False)
    change_start.add_argument("--summary")
    change_start.set_defaults(func=cmd_change_start)

    change_show = change_sub.add_parser("show-active")
    change_show.set_defaults(func=cmd_change_show_active)

    change_close = change_sub.add_parser("close")
    change_close.set_defaults(func=cmd_change_close)

    skill = sub.add_parser("skill")
    skill_sub = skill.add_subparsers(dest="skill_command")
    skill_load = skill_sub.add_parser("load")
    skill_load.set_defaults(func=cmd_skill_load)

    hook = sub.add_parser("hook")
    hook_sub = hook.add_subparsers(dest="hook_command")

    hook_commit = hook_sub.add_parser("commit-msg")
    hook_commit.add_argument("message_file")
    hook_commit.set_defaults(func=cmd_hook_commit_msg)

    hook_prepare = hook_sub.add_parser("prepare-commit-msg")
    hook_prepare.add_argument("message_file")
    hook_prepare.add_argument("source", nargs="?")
    hook_prepare.add_argument("sha", nargs="?")
    hook_prepare.set_defaults(func=cmd_hook_prepare_commit_msg)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    try:
        return args.func(args)
    except SpecVCError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
