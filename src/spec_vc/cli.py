from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys

from ._sections import validate_title
from .adr import list_adrs, next_adr_id, render_adr
from .adr import parse_adr as parse_adr_file
from .adr import ensure_referenceable as ensure_adr_referenceable
from .change import (
    ClarifyInput,
    close_change,
    create_plan,
    infer_adr_required,
    load_active,
    next_question,
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
from .commit import (
    cleanup_tests,
    gather_commit_context,
    prepare_audit_prompt,
    prepare_test_prompt,
    write_commit_token,
)
from .spec import (
    create_spec,
    formalize_spec,
    list_formal_files,
    list_specs,
    next_spec_id,
    specs_root as get_specs_root,
    validate_title as validate_spec_title,
)
from .templates import skill_root, template_path


def _repo_root() -> Path:
    return repo_root_from(Path.cwd())


def _write_if_missing(path: Path, content: str) -> None:
    if not path.exists():
        path.write_text(content)


def _install_hook(repo_root: Path, name: str) -> Path:
    hook_path = repo_root / ".git" / "hooks" / name
    hook_path.write_text((skill_root() / "hooks" / name).read_text())
    hook_path.chmod(0o755)
    return hook_path


def _run_uv_sync(project_root: Path) -> None:
    import subprocess

    proc = subprocess.run(
        ["uv", "sync"],
        cwd=project_root,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        msg = proc.stderr.strip() or proc.stdout.strip() or "uv sync 失败"
        raise UsageError(f"环境安装失败: {msg}")


def cmd_adr_init(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    project_root = skill_root()

    _run_uv_sync(project_root)

    config_path = repo_root / ".spec-vc.toml"
    _write_if_missing(config_path, (project_root / ".spec-vc.toml").read_text())
    config = load_config(repo_root)
    adr_dir = repo_root / config.project.adr_dir
    adr_dir.mkdir(parents=True, exist_ok=True)

    readme_path = adr_dir / "README.md"
    _write_if_missing(readme_path, template_path("index.md").read_text())

    seed_path = adr_dir / "adr-000.md"
    if args.seed and not seed_path.exists():
        author = run_git(repo_root, "config", "user.name", check=False).strip() or "unknown"
        content = template_path("seed-adr-000.md").read_text()
        content = content.replace("{{DATE}}", date.today().isoformat())
        content = content.replace("{{AUTHOR}}", author)
        seed_path.write_text(content)

    update_index(adr_dir)

    prepare_hook = _install_hook(repo_root, "prepare-commit-msg")
    commit_hook = _install_hook(repo_root, "commit-msg")
    run_git(repo_root, "config", "commit.template", str(template_path("commit-msg")))

    venv_path = project_root / ".venv"
    print("✅ spec-vc 初始化成功")
    print("  - uv sync (环境已安装)" if venv_path.exists() else "  - uv sync (已完成)")
    print(f"  - {config_path.relative_to(repo_root)}")
    print(f"  - {readme_path.relative_to(repo_root)}")
    if args.seed and seed_path.exists():
        print(f"  - {seed_path.relative_to(repo_root)}")
    print(f"  - {prepare_hook.relative_to(repo_root)}")
    print(f"  - {commit_hook.relative_to(repo_root)}")
    print("  - git config commit.template (已配置)")
    return 0


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
            motivation=args.motivation or "",
            boundary=args.boundary or "",
            design=args.design or "",
            implementation=args.implementation or "",
            verification=args.verification or "",
            rollback=args.rollback or "",
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


def cmd_change_next_question(_args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    config = load_config(repo_root)
    question = next_question(repo_root / config.project.adr_dir)
    print(f"stage: {question.stage}")
    if question.missing_fields:
        print("missing: " + ", ".join(question.missing_fields))
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
    spec_count = context.get("spec_count", 0)
    print(f"spec_count: {spec_count}")
    recent_specs = context.get("recent_specs", [])
    for s in recent_specs:
        print(f"recent Spec-{s.spec_id} [{s.status}] {s.title}")
    return 0


def cmd_commit(args: argparse.Namespace) -> int:
    if args.subcommand == "clean":
        repo_root = _repo_root()
        config = load_config(repo_root)
        specs_root = get_specs_root(repo_root, config.spec.dir)
        removed = cleanup_tests(specs_root)
        if removed:
            print("已清理测试目录:")
            for d in removed:
                print(f"  {d}")
        else:
            print("(无测试目录需要清理)")
        return 0

    repo_root = _repo_root()
    config = load_config(repo_root)
    ctx = gather_commit_context(repo_root, config)

    if not ctx.staged_files:
        print("(无 staged changes，无需提交)")
        return 0

    write_commit_token(repo_root)

    print(f"## Staged Files ({len(ctx.staged_files)})")
    for f in ctx.staged_files:
        print(f"  {f}")

    print(f"\n## Specs ({len(ctx.spec_dirs)})")
    if not ctx.spec_dirs:
        print("  (尚无 Spec 文件，跳过审计)")
    else:
        for spec_id in ctx.spec_dirs:
            formal = ctx.formal_files.get(spec_id, [])
            doc_status = "✓" if spec_id in ctx.dev_docs else "✗"
            print(f"  Spec-{spec_id}: dev-doc [{doc_status}], formal: {', '.join(formal) if formal else '无'}")

    print(f"\n## === AUDIT SUBAGENT PROMPT ===")
    print(prepare_audit_prompt(ctx))

    print(f"\n## === TEST SUBAGENT PROMPT ===")
    print(prepare_test_prompt(ctx))

    return 0


def cmd_spec_new(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    config = load_config(repo_root)
    specs_root = get_specs_root(repo_root, config.spec.dir)
    adr_dir = repo_root / config.project.adr_dir

    if not args.adr:
        raise UsageError("spec new 需要 --adr ADR-NNN, Spec 必须关联 ADR")
    adr_id = args.adr.replace("ADR-", "").zfill(3)
    adr_path = adr_dir / f"adr-{adr_id}.md"
    if not adr_path.exists():
        raise UsageError(f"关联的 ADR 不存在: ADR-{adr_id}")
    adr = parse_adr_file(adr_path)
    ensure_adr_referenceable(adr, adr_id)

    title = validate_spec_title(args.title)
    spec_id = next_spec_id(specs_root)
    author = run_git(repo_root, "config", "user.name", check=False).strip() or "unknown"
    doc_path = create_spec(specs_root, spec_id, title, author, f"ADR-{adr_id}", template_dir=skill_root() / "templates")
    print(f"Spec-{spec_id}: {title}")
    print(f"  {specs_root / spec_id / 'dev-doc.md'}")
    for fname in ["contract.openapi.yaml", "schema.json", "behavior.feature"]:
        print(f"  {specs_root / spec_id / fname}")
    print(f"推荐 commit message: feat(<scope>): <subject> [ADR-{adr_id}]")
    return 0


def cmd_spec_list(_args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    config = load_config(repo_root)
    specs_root = get_specs_root(repo_root, config.spec.dir)
    specs = list_specs(specs_root)
    if not specs:
        print("(尚无 Spec 文件)")
        return 0
    for s in specs:
        adr_info = f" -> {s.adr_ref}" if s.adr_ref else ""
        print(f"Spec-{s.spec_id} [{s.status}] {s.title}{adr_info}")
    return 0


def cmd_spec_show(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    config = load_config(repo_root)
    specs_root = get_specs_root(repo_root, config.spec.dir)
    spec_id = args.id.replace("Spec-", "").zfill(3)
    doc_path = specs_root / spec_id / "dev-doc.md"
    if not doc_path.exists():
        raise UsageError(f"Spec 不存在: Spec-{spec_id}")
    print(doc_path.read_text())
    formal = list_formal_files(specs_root, spec_id)
    if formal:
        print("---")
        print("形式化文件:")
        for fname in formal:
            fpath = specs_root / spec_id / fname
            print(f"  [{fname}] ({fpath.stat().st_size} bytes)")
    else:
        print("---")
        print("(尚无形式化文件)")
    return 0


def cmd_spec_formalize(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    config = load_config(repo_root)
    specs_root = get_specs_root(repo_root, config.spec.dir)
    spec_id = args.id.replace("Spec-", "").zfill(3)

    types: list[str]
    if args.type == "all":
        types = ["openapi", "jsonschema", "gherkin"]
    else:
        types = [args.type]

    for ft in types:
        out = formalize_spec(specs_root, spec_id, ft)
        print(out)
    return 0


def cmd_hook_commit_msg(args: argparse.Namespace) -> int:
    return run_commit_msg(Path(args.message_file))


def cmd_hook_prepare_commit_msg(args: argparse.Namespace) -> int:
    return run_prepare_commit_msg(Path(args.message_file), args.source or "", args.sha or "")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spec-vc")
    sub = parser.add_subparsers(dest="command")

    init = sub.add_parser("init")
    init.add_argument("--seed", action=argparse.BooleanOptionalAction, default=True)
    init.set_defaults(func=cmd_adr_init)

    adr = sub.add_parser("adr")
    adr_sub = adr.add_subparsers(dest="adr_command")

    adr_init = adr_sub.add_parser("init")
    adr_init.add_argument("--seed", action=argparse.BooleanOptionalAction, default=True)
    adr_init.set_defaults(func=cmd_adr_init)

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
    change_clarify.add_argument("--motivation")
    change_clarify.add_argument("--boundary")
    change_clarify.add_argument("--design")
    change_clarify.add_argument("--implementation")
    change_clarify.add_argument("--verification")
    change_clarify.add_argument("--rollback")
    change_clarify.set_defaults(func=cmd_change_clarify)

    change_validate = change_sub.add_parser("validate")
    change_validate.add_argument("--phase", choices=["pre", "post"], required=True)
    change_validate.add_argument("--content", required=True)
    change_validate.set_defaults(func=cmd_change_validate)

    change_should = change_sub.add_parser("should-adr")
    change_should.add_argument("--prompt")
    change_should.add_argument("paths", nargs="*")
    change_should.set_defaults(func=cmd_change_should_adr)

    change_next = change_sub.add_parser("next-question")
    change_next.set_defaults(func=cmd_change_next_question)

    change_show = change_sub.add_parser("show-active")
    change_show.set_defaults(func=cmd_change_show_active)

    change_close = change_sub.add_parser("close")
    change_close.add_argument("--summary", required=True)
    change_close.set_defaults(func=cmd_change_close)

    spec = sub.add_parser("spec")
    spec_sub = spec.add_subparsers(dest="spec_command")

    spec_new = spec_sub.add_parser("new")
    spec_new.add_argument("title")
    spec_new.add_argument("--adr", required=True)
    spec_new.set_defaults(func=cmd_spec_new)

    spec_list = spec_sub.add_parser("list")
    spec_list.set_defaults(func=cmd_spec_list)

    spec_show = spec_sub.add_parser("show")
    spec_show.add_argument("id")
    spec_show.set_defaults(func=cmd_spec_show)

    spec_formalize = spec_sub.add_parser("formalize")
    spec_formalize.add_argument("id")
    spec_formalize.add_argument("--type", required=True, choices=["openapi", "jsonschema", "gherkin", "all"])
    spec_formalize.set_defaults(func=cmd_spec_formalize)

    commit = sub.add_parser("commit")
    commit_sub = commit.add_subparsers(dest="subcommand")
    commit_clean = commit_sub.add_parser("clean")
    commit_clean.set_defaults(func=cmd_commit)
    commit.set_defaults(func=cmd_commit)

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
