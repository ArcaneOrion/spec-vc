from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .adr import list_adrs, next_adr_id, render_adr, validate_title
from .change import (
    ClarifyInput,
    close_change,
    create_plan,
    infer_adr_required,
    load_active,
    record_validation,
    clarify_plan,
)
from .config import load_config
from .errors import SpecVCError, UsageError
from .gitops import repo_root_from, run_git
from .hooks import run_commit_msg, run_prepare_commit_msg
from .index import update_index
from .skill import load_subsystem_context
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
    context = load_subsystem_context(Path.cwd(), user_prompt=args.summary or "")
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


def cmd_change_clarify(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    config = load_config(repo_root)
    adr_dir = repo_root / config.project.adr_dir
    plan, missing = clarify_plan(
        adr_dir,
        ClarifyInput(
            goal=args.goal or "",
            scope=args.scope or "",
            non_goals=args.non_goals or "",
            strategy=args.strategy or "",
            risks=args.risks or "",
            acceptance=args.acceptance or "",
        ),
    )
    print(plan)
    if missing:
        print("missing: " + ", ".join(missing))
        return 1
    return 0


def cmd_change_validate(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    config = load_config(repo_root)
    plan = record_validation(repo_root / config.project.adr_dir, args.phase, args.content)
    print(plan)
    return 0


def cmd_change_should_adr(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    config = load_config(repo_root)
    required, reason = infer_adr_required(args.paths or [], args.prompt or "", config.adr_required)
    print(f"required: {required}")
    print(f"reason: {reason}")
    return 0 if required else 1


def cmd_change_show_active(_args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    config = load_config(repo_root)
    active = load_active(repo_root / config.project.adr_dir)
    if active is None:
        print("no active change")
        return 0
    print(f"ADR-{active.adr_id} {active.stage} {active.plan_path}")
    return 0


def cmd_change_close(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    config = load_config(repo_root)
    plan, adr = close_change(repo_root, repo_root / config.project.adr_dir, args.summary)
    print(plan)
    print(adr)
    return 0


def cmd_skill_load(args: argparse.Namespace) -> int:
    context = load_subsystem_context(Path.cwd(), user_prompt=args.user_prompt or "")
    print(f"initialized: {context['initialized']}")
    print(f"dirty: {context['dirty']}")
    if 'adr_required' in context:
        print(f"adr_required: {context['adr_required']}")
        print(f"adr_required_reason: {context['adr_required_reason']}")
    active = context.get("active")
    if active is not None:
        print(f"active ADR: ADR-{active.adr_id}")
        print(f"active stage: {active.stage}")
    recent = context.get("recent_adrs", [])
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

    change_clarify = change_sub.add_parser("clarify")
    change_clarify.add_argument("--goal")
    change_clarify.add_argument("--scope")
    change_clarify.add_argument("--non-goals")
    change_clarify.add_argument("--strategy")
    change_clarify.add_argument("--risks")
    change_clarify.add_argument("--acceptance")
    change_clarify.set_defaults(func=cmd_change_clarify)

    change_validate = change_sub.add_parser("validate")
    change_validate.add_argument("--phase", choices=["pre", "post"], required=True)
    change_validate.add_argument("--content", required=True)
    change_validate.set_defaults(func=cmd_change_validate)

    change_should = change_sub.add_parser("should-adr")
    change_should.add_argument("--prompt")
    change_should.add_argument("paths", nargs="*")
    change_should.set_defaults(func=cmd_change_should_adr)

    change_show = change_sub.add_parser("show-active")
    change_show.set_defaults(func=cmd_change_show_active)

    change_close = change_sub.add_parser("close")
    change_close.add_argument("--summary", required=True)
    change_close.set_defaults(func=cmd_change_close)

    skill = sub.add_parser("skill")
    skill_sub = skill.add_subparsers(dest="skill_command")
    skill_load = skill_sub.add_parser("load")
    skill_load.add_argument("--user-prompt")
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
