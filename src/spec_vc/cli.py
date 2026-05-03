from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import json
import os
import re
import sys

from ._sections import validate_title
from .adr import list_adrs, next_adr_id, render_adr, read_adr_content
from .adr import parse_adr as parse_adr_file
from .adr import ensure_referenceable as ensure_adr_referenceable
from .change import (
    ClarifyInput,
    close_change,
    create_plan,
    infer_adr_required,
    load_active,
    next_question,
    plan_path,
    record_validation,
    clarify_plan,
    read_plan_content,
    read_active_change_context,
)
from .config import load_config
from .errors import SpecVCError, UsageError
from .gitops import repo_root_from, run_git
from .hooks import run_commit_msg, run_prepare_commit_msg
from .index import update_index
from .skill import load_subsystem_context
from .status import build_status
from .commit import (
    AUDIT_REPORT_FILENAME,
    COMMIT_MSG_FILENAME,
    MANIFEST_FILENAME,
    PREPARE_TS_FILENAME,
    SUBAGENT_SESSIONS_FILENAME,
    TEST_REPORT_FILENAME,
    build_audit_manifest,
    cleanup_tests,
    gather_commit_context,
    manifest_to_json,
    prepare_audit_prompt,
    prepare_test_prompt,
    write_commit_message,
    write_commit_token,
)
from .spec import (
    check_spec_readiness,
    create_spec,
    formalize_spec,
    list_formal_files,
    list_specs,
    next_spec_id,
    read_spec_full,
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


def _init_claude_hook(repo_root: Path) -> Path | None:
    """写入/合并 PostToolUse hook 到目标项目的 .claude/settings.json。"""
    claude_dir = repo_root / ".claude"
    settings_path = claude_dir / "settings.json"

    hook_entry = {
        "matcher": "Agent",
        "hooks": [{
            "type": "command",
            "command": "~/.claude/skills/spec-vc/.venv/bin/spec-vc hook post-tool-use --tool-name Agent --description \"${CLAUDE_TOOL_DESCRIPTION}\""
        }]
    }

    if settings_path.exists():
        try:
            existing = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            raise UsageError(
                f".claude/settings.json 格式损坏，请手动修复后重试: {settings_path}"
            )
        existing_hooks = existing.get("hooks", {})
        existing_post = existing_hooks.get("PostToolUse", [])
        for entry in existing_post:
            if entry.get("matcher") == "Agent":
                for h in entry.get("hooks", []):
                    if "spec-vc hook post-tool-use" in h.get("command", ""):
                        return None
        existing.setdefault("hooks", {}).setdefault("PostToolUse", []).append(hook_entry)
        claude_dir.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n")
    else:
        claude_dir.mkdir(parents=True, exist_ok=True)
        hook_config = {"hooks": {"PostToolUse": [hook_entry]}}
        settings_path.write_text(json.dumps(hook_config, ensure_ascii=False, indent=2) + "\n")

    return settings_path


def cmd_init(args: argparse.Namespace) -> int:
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

    claude_settings = _init_claude_hook(repo_root)

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
    if claude_settings:
        print(f"  - {claude_settings.relative_to(repo_root)} (PostToolUse hook)")
    return 0


def cmd_adr_show(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    config = load_config(repo_root)
    adr_dir = repo_root / config.project.adr_dir
    adr_id = args.id.replace("ADR-", "").zfill(3)
    adr_path = adr_dir / f"adr-{adr_id}.md"
    if not adr_path.exists():
        raise UsageError(f"ADR 不存在: ADR-{adr_id}")
    print(adr_path.read_text())
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

    if args.phase == "pre":
        specs_root = get_specs_root(repo_root, config.spec.dir)
        issues = check_spec_readiness(specs_root)
        if issues:
            print("Spec 就绪检查 - 未通过")
            print("")
            print("在进入 implement-ready（代码修改）前，以下 Spec 必须完成：")
            print("")
            for issue in issues:
                print(f"  Spec-{issue.spec_id} / {issue.location}")
                print(f"    → {issue.problem}")
            print("")
            print("修复步骤：")
            print("  1. 填写 dev-doc.md 中各区块内容")
            print("  2. 运行 spec-vc spec formalize 生成形式化文件")
            print("  3. 运行 spec-vc spec check 确认就绪")
            return 1

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


def cmd_change_show(_args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    config = load_config(repo_root)
    adr_dir = repo_root / config.project.adr_dir
    active = load_active(adr_dir)
    if active is None:
        raise UsageError("当前没有 active change")
    path = plan_path(adr_dir, active)
    print(path.read_text())
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


def _print_spec_readiness_issues(issues):
    print("## Spec 就绪检查 - 未通过", file=sys.stderr)
    print("", file=sys.stderr)
    print("以下 Spec 未完成填写或形式化，请先补齐后再提交：", file=sys.stderr)
    print("", file=sys.stderr)
    for issue in issues:
        print(f"  Spec-{issue.spec_id} / {issue.location}", file=sys.stderr)
        print(f"    → {issue.problem}", file=sys.stderr)
    print("", file=sys.stderr)
    print("修复步骤：", file=sys.stderr)
    print("  1. 填写 dev-doc.md 中各区块内容（概述/接口契约/数据形状/行为规则）", file=sys.stderr)
    print("  2. 运行 spec-vc spec formalize 生成形式化文件", file=sys.stderr)
    print("  3. 运行 spec-vc spec check 确认就绪", file=sys.stderr)


def _print_staged_and_specs(ctx):
    print(f"## Staged Files ({len(ctx.staged_files)})", file=sys.stderr)
    for f in ctx.staged_files:
        print(f"  {f}", file=sys.stderr)
    print(f"\n## Specs ({len(ctx.spec_dirs)})", file=sys.stderr)
    if not ctx.spec_dirs:
        print("  (尚无 Spec 文件，跳过审计)", file=sys.stderr)
    else:
        for spec_id in ctx.spec_dirs:
            formal = ctx.formal_files.get(spec_id, [])
            doc_status = "✓" if spec_id in ctx.dev_docs else "✗"
            print(f"  Spec-{spec_id}: dev-doc [{doc_status}], formal: {', '.join(formal) if formal else '无'}", file=sys.stderr)


def cmd_commit_prepare(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    config = load_config(repo_root)
    ctx = gather_commit_context(repo_root, config)

    if not ctx.staged_files:
        print("(无 staged changes，无需提交)")
        return 0

    if ctx.spec_readiness_issues:
        _print_spec_readiness_issues(ctx.spec_readiness_issues)
        return 1

    manifest = build_audit_manifest(ctx)
    manifest_json = manifest_to_json(manifest)
    manifest_path = repo_root / ".git" / MANIFEST_FILENAME
    manifest_path.write_text(manifest_json)

    from datetime import datetime, timezone
    ts_path = repo_root / ".git" / PREPARE_TS_FILENAME
    ts_path.write_text(datetime.now(timezone.utc).isoformat())

    if getattr(args, 'message', None):
        write_commit_message(repo_root, args.message)

    use_text = getattr(args, 'format', 'json') == 'text'

    _print_staged_and_specs(ctx)

    if use_text:
        print(f"\n## === AUDIT SUBAGENT PROMPT ===")
        print(prepare_audit_prompt(ctx))
        print(f"\n## === TEST SUBAGENT PROMPT ===")
        print(prepare_test_prompt(ctx))
    else:
        print(manifest_json)

    print("\n[spec-vc] manifest 已写入 .git/spec-vc-manifest.json", file=sys.stderr)
    if getattr(args, 'message', None):
        print("[spec-vc] commit message 已写入 .git/spec-vc-commit-msg", file=sys.stderr)
    print("[spec-vc] 请完成审计后由用户在终端运行: spec-vc commit submit", file=sys.stderr)

    return 0


def cmd_commit_submit(args: argparse.Namespace) -> int:
    if not os.isatty(sys.stdin.fileno()) and not os.environ.get("SPEC_VC_TEST_TTY_BYPASS"):
        print("[spec-vc] 此命令仅在真实终端中运行。", file=sys.stderr)
        print("[spec-vc] 请在终端中输入 spec-vc commit submit 手动提交。", file=sys.stderr)
        return 1

    repo_root = _repo_root()
    config = load_config(repo_root)
    git_dir = repo_root / ".git"

    manifest_path = git_dir / MANIFEST_FILENAME
    if not manifest_path.exists():
        print("[spec-vc] 未找到 manifest 文件，请先运行 spec-vc commit prepare", file=sys.stderr)
        return 1

    saved_manifest = json.loads(manifest_path.read_text())

    ctx = gather_commit_context(repo_root, config)

    if not ctx.staged_files:
        print("(无 staged changes，无需提交)")
        return 0

    current_manifest = build_audit_manifest(ctx)
    current_manifest_dict = json.loads(manifest_to_json(current_manifest))

    mismatch_fields = []
    if sorted(saved_manifest.get("staged_files", [])) != sorted(current_manifest_dict.get("staged_files", [])):
        mismatch_fields.append("staged_files")
    if sorted(saved_manifest.get("spec_dirs", [])) != sorted(current_manifest_dict.get("spec_dirs", [])):
        mismatch_fields.append("spec_dirs")

    if mismatch_fields:
        print(f"[spec-vc] manifest 不匹配（{', '.join(mismatch_fields)} 在 prepare 后已变更），请重新运行 spec-vc commit prepare", file=sys.stderr)
        return 1

    audit_path = git_dir / AUDIT_REPORT_FILENAME
    test_path = git_dir / TEST_REPORT_FILENAME

    if not audit_path.exists():
        print("[spec-vc] 未找到审计报告 .git/spec-vc-audit-report.json", file=sys.stderr)
        return 1
    if not test_path.exists():
        print("[spec-vc] 未找到测试报告 .git/spec-vc-test-report.json", file=sys.stderr)
        return 1

    from .verify import run_verify
    verify_result = run_verify(
        audit_report_path=audit_path,
        test_report_path=test_path,
        manifest_path=manifest_path,
    )

    from dataclasses import asdict as _asdict
    vr = json.dumps(_asdict(verify_result), ensure_ascii=False, indent=2)
    print(vr)

    if not verify_result.all_pass:
        print("[spec-vc] verify 未通过，无法继续提交。", file=sys.stderr)
        return 1

    if not os.environ.get("SPEC_VC_TEST_TTY_BYPASS"):
        try:
            input("[spec-vc] 按 Enter 确认提交，Ctrl-C 取消... ")
        except (EOFError, KeyboardInterrupt):
            print("\n[spec-vc] 提交已取消。", file=sys.stderr)
            return 1

    write_commit_token(repo_root)

    msg_path = git_dir / COMMIT_MSG_FILENAME
    try:
        if msg_path.exists():
            run_git(repo_root, "commit", "-F", str(msg_path))
            msg_path.unlink()
        else:
            run_git(repo_root, "commit", "-m", getattr(args, 'message', 'commit [ADR-008]'))
    except SpecVCError as e:
        print(f"[spec-vc] git commit 失败:\n{e}", file=sys.stderr)
        return 1

    print("[spec-vc] 提交完成。", file=sys.stderr)
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

    if args.subcommand == "prepare":
        return cmd_commit_prepare(args)

    if args.subcommand == "submit":
        return cmd_commit_submit(args)

    print("[spec-vc] 请指定子命令: prepare, submit, clean, verify", file=sys.stderr)
    return 1


def cmd_commit_verify(args: argparse.Namespace) -> int:
    from .verify import run_verify

    result = run_verify(
        audit_report_path=Path(args.audit_report),
        test_report_path=Path(args.test_report),
        manifest_path=Path(args.manifest),
    )

    import json
    from dataclasses import asdict

    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 0 if result.all_pass else 1


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
        if args.formal:
            for fname in formal:
                fpath = specs_root / spec_id / fname
                print(f"\n--- [{fname}] ---")
                print(fpath.read_text())
        else:
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


def cmd_spec_check(_args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    config = load_config(repo_root)
    specs_root = get_specs_root(repo_root, config.spec.dir)
    specs = list_specs(specs_root)
    if not specs:
        print("(尚无 Spec 文件)")
        return 0
    issues = check_spec_readiness(specs_root)
    if not issues:
        print(f"全部 {len(specs)} 个 Spec 就绪")
        return 0
    print("以下 Spec 未完成：")
    for issue in issues:
        print(f"  Spec-{issue.spec_id} / {issue.location}")
        print(f"    → {issue.problem}")
    return 1


def cmd_hook_commit_msg(args: argparse.Namespace) -> int:
    return run_commit_msg(Path(args.message_file))


def cmd_hook_prepare_commit_msg(args: argparse.Namespace) -> int:
    return run_prepare_commit_msg(Path(args.message_file), args.source or "", args.sha or "")


def cmd_hook_post_tool_use(args: argparse.Namespace) -> int:
    from .hooks import run_post_tool_use
    return run_post_tool_use(
        repo_root=_repo_root(),
        tool_name=getattr(args, 'tool_name', ''),
        description=getattr(args, 'description', ''),
    )


def cmd_show_adr(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    config = load_config(repo_root)
    adr_dir = repo_root / config.project.adr_dir
    adr_id = args.id.replace("ADR-", "").zfill(3)
    content = read_adr_content(adr_dir, adr_id)
    print(content)
    return 0


def cmd_show_plan(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    config = load_config(repo_root)
    adr_dir = repo_root / config.project.adr_dir
    plan_id = args.plan_id if hasattr(args, "plan_id") and args.plan_id else None
    content = read_plan_content(adr_dir, plan_id)
    print(content)
    return 0


def cmd_show_spec(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    config = load_config(repo_root)
    specs_root = get_specs_root(repo_root, config.spec.dir)
    spec_id = args.id.replace("Spec-", "").zfill(3)
    content = read_spec_full(specs_root, spec_id)
    print(content)
    return 0


def cmd_show_change(_args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    config = load_config(repo_root)
    adr_dir = repo_root / config.project.adr_dir
    content = read_active_change_context(adr_dir)
    print(content)
    return 0


def _cmd_hook_post_tool_use_legacy(_args: argparse.Namespace) -> int:
    """已废弃：旧的 stdin-JSON 上下文注入 hook。
    被 ADR-009 PostToolUse session logging 机制取代。
    保留此函数仅用于向后兼容——spec-vc init --seed 不再注册此路径。"""

    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    if data.get("tool_name") != "Bash":
        return 0

    command = data.get("tool_input", {}).get("command", "")
    stdout = data.get("tool_output", "")

    repo_root = _repo_root()
    cfg = load_config(repo_root)
    adr_dir = repo_root / cfg.project.adr_dir

    output: str = ""
    header: str = ""

    # change clarify 完成（无 missing 字段）
    if "change clarify" in command and "--motivation" in command:
        if "missing:" not in stdout:
            active = load_active(adr_dir)
            if active is not None:
                output = plan_path(adr_dir, active).read_text()
                header = "当前 Plan 文件"

    # spec formalize 完成
    elif "spec formalize" in command and "--type" in command:
        m = re.search(r"formalize\s+(\S+)", command)
        if m:
            spec_id = m.group(1).replace("Spec-", "").zfill(3)
            specs_root = get_specs_root(repo_root, cfg.spec.dir)
            doc_path = specs_root / spec_id / "dev-doc.md"
            if doc_path.exists():
                output = doc_path.read_text()
                for fname in list_formal_files(specs_root, spec_id):
                    fpath = specs_root / spec_id / fname
                    output += f"\n\n--- [{fname}] ---\n"
                    output += fpath.read_text()
                header = f"当前 Spec-{spec_id} 文件"

    # change start 完成
    elif "change start" in command and "--adr" in command:
        if "ADR-" in stdout and "plan-" in stdout:
            active = load_active(adr_dir)
            if active is not None:
                output = plan_path(adr_dir, active).read_text()
                header = "当前 Plan 文件"

    # show 命令：直接使用 stdout 中的内容（CLI 已经输出了）
    elif " show " in command:
        if stdout.strip():
            pass

    if not output:
        return 0

    print("\n" + "=" * 60)
    print(f"[spec-vc]  以下是最新{header}内容，请展示给用户：")
    print("=" * 60 + "\n")
    print(output)

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spec-vc")
    sub = parser.add_subparsers(dest="command")

    init = sub.add_parser("init")
    init.add_argument("--seed", action=argparse.BooleanOptionalAction, default=True)
    init.set_defaults(func=cmd_init)

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

    adr_show = adr_sub.add_parser("show")
    adr_show.add_argument("id")
    adr_show.set_defaults(func=cmd_adr_show)

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

    change_show = change_sub.add_parser("show")
    change_show.set_defaults(func=cmd_change_show)

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
    spec_show.add_argument("--formal", action="store_true")
    spec_show.set_defaults(func=cmd_spec_show)

    spec_formalize = spec_sub.add_parser("formalize")
    spec_formalize.add_argument("id")
    spec_formalize.add_argument("--type", required=True, choices=["openapi", "jsonschema", "gherkin", "all"])
    spec_formalize.set_defaults(func=cmd_spec_formalize)

    spec_check = spec_sub.add_parser("check")
    spec_check.set_defaults(func=cmd_spec_check)

    show = sub.add_parser("show")
    show_sub = show.add_subparsers(dest="show_command")

    show_adr = show_sub.add_parser("adr")
    show_adr.add_argument("id")
    show_adr.set_defaults(func=cmd_show_adr)

    show_plan = show_sub.add_parser("plan")
    show_plan.add_argument("plan_id", nargs="?")
    show_plan.set_defaults(func=cmd_show_plan)

    show_spec = show_sub.add_parser("spec")
    show_spec.add_argument("id")
    show_spec.set_defaults(func=cmd_show_spec)

    show_change = show_sub.add_parser("change")
    show_change.set_defaults(func=cmd_show_change)

    commit = sub.add_parser("commit")
    commit.add_argument("--format", choices=["json", "text"], default="json")
    commit_sub = commit.add_subparsers(dest="subcommand")
    commit_prepare = commit_sub.add_parser("prepare")
    commit_prepare.add_argument("--message")
    commit_prepare.add_argument("--format", choices=["json", "text"], default="json")
    commit_prepare.set_defaults(func=cmd_commit)
    commit_submit = commit_sub.add_parser("submit")
    commit_submit.set_defaults(func=cmd_commit)
    commit_clean = commit_sub.add_parser("clean")
    commit_clean.set_defaults(func=cmd_commit)
    commit_verify = commit_sub.add_parser("verify")
    commit_verify.add_argument("--audit-report", required=True)
    commit_verify.add_argument("--test-report", required=True)
    commit_verify.add_argument("--manifest", required=True)
    commit_verify.set_defaults(func=cmd_commit_verify)
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

    hook_post_tool = hook_sub.add_parser("post-tool-use")
    hook_post_tool.add_argument("--tool-name", default="")
    hook_post_tool.add_argument("--description", default="")
    hook_post_tool.set_defaults(func=cmd_hook_post_tool_use)

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
