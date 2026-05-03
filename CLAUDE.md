# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 常用命令

```bash
uv sync                                        # 准备虚拟环境（首次或 pyproject.toml 变更后）
uv run spec-vc --help                          # 运行 CLI
uv run spec-vc commit prepare --message "..."  # AI 域：生成 manifest（不写 token）
uv run spec-vc commit submit                   # 用户域：TTY 终审提交
uv run spec-vc commit clean                    # 清理测试文件
uv run pytest tests/python/ -v                 # 运行全部测试
uv run pytest tests/python/test_spec.py -v     # 运行单个测试文件
uv run pytest tests/python/ -k "formalize"     # 按关键词筛选运行
```

## 架构概览

`src/spec_vc/` 下是 Python CLI,按**领域模型解耦**组织:

| 模块 | 职责 |
|------|------|
| `cli.py` | argparse 命令路由,所有入口函数 |
| `adr.py` | ADR 数据模型(dataclass)、解析、渲染、编号、豁免判定 |
| `spec.py` | Spec 数据模型(dataclass)、子目录管理、形式化文件生成 |
| `change.py` | 变更状态机(discover→clarify→plan→implement-ready→validate→close)、plan 文件 CRUD |
| `commit.py` | 提交上下文收集、审计/测试 subagent 提示词生成、test 清理 |
| `hooks.py` | commit-msg / prepare-commit-msg hook 校验逻辑 |
| `config.py` | `.spec-vc.toml` 配置模型(ExemptionConfig/AdrRequiredConfig/SpecConfig) |
| `status.py` | ADR↔commit 漂移检测 |
| `index.py` | ADR 索引维护 |
| `skill.py` | 子系统上下文加载(`skill load` 后端的聚合入口) |
| `gitops.py` | `git` 命令封装(run_git, staged_files, repo_root_from) |
| `_sections.py` | Markdown 区块解析/替换/标题校验(被 adr/spec/change 复用) |
| `errors.py` | 异常层次(SpecVCError → UsageError / ValidationError) |

**依赖方向**: 基础层(errors/config/templates/gitops) ← 领域层(adr/spec/change/commit) ← 集成层(hooks/skill) ← CLI。

## 关键设计约定

**数据模型**: 所有领域对象用 `@dataclass(slots=True)`,Markdown 文件为持久化载体,正则解析。

**命令命名**: `spec-vc <domain> <action>`，如 `spec-vc spec new`、`spec-vc adr list`。`spec-vc commit` 和 `spec-vc adr init` 是顶层特殊命令。

**commit message**: `<type>(<scope>): <subject> [ADR-NNN]`，subject 用中文简述。严格模式(hook)阻塞无 `[ADR-NNN]` 或 `[ADR-none]` 的 commit。提交采用 prepare/submit 两阶段协议：AI 运行 `commit prepare` 生成 manifest 并完成 subagent 审计，用户在终端运行 `commit submit` 完成 TTY 终审提交。

**模板系统**: `templates/` 下存放 ADR/Spec/commit 模板文件,通过 `template_path()` 访问。

**配置**: 项目配置在 `.spec-vc.toml`,CLI 通过 `load_config(repo_root)` 加载,dataclass 承载每个配置段。

**Skill 入口**: `SKILL.md` 是 Claude Code skill 的入口文件(给 AI 读的操作协议),`README.md` 是给人看的项目介绍。两者职责不同:SKILL.md 描述 AI 内部执行流程,README 描述项目功能。

## 新增 CLI 命令的模式

1. 在对应的领域模块写命令函数
2. 在 `cli.py::build_parser()` 注册子命令和参数
3. 命令函数签名: `def cmd_<name>(args: argparse.Namespace) -> int`
4. 通过 `_repo_root()` 获取仓库根,`load_config(repo_root)` 获取配置
5. 错误用 `raise UsageError(msg)` 或 `raise ValidationError(msg)`

## 测试

pytest,临时 git 仓库隔离测试。每个测试通过 `init_repo(tmp_path)` 创建干净的测试仓库,用 `run(repo, *args)` 执行 CLI 命令。
