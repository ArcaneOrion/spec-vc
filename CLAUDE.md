# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 常用命令

```bash
# 准备虚拟环境（首次或 pyproject.toml 变更后）
uv sync

# CLI 命令（开发时用 uv run，用户安装后用 skill venv）
uv run spec-vc --help                              # 查看帮助
uv run spec-vc init                                 # 初始化项目（安装 hooks、配置、seed ADR）
uv run spec-vc skill load --user-prompt "..."       # 加载子系统上下文
uv run spec-vc review --mode subagent --message "..."  # ADR-018: 审查命令（写 review.json + commit-msg）
uv run spec-vc commit                                # ADR-018: 薄包装提交入口（应用 commit-msg + git commit）
uv run spec-vc adr new "标题"                        # 创建新 ADR
uv run spec-vc adr list                              # 列出所有 ADR
uv run spec-vc spec new "标题" --adr ADR-NNN         # 创建 Spec
uv run spec-vc spec formalize <id> --type all        # 从 dev-doc.md 生成形式化文件
uv run spec-vc spec check                            # 检查所有 Spec 就绪状态
uv run spec-vc change start --adr ADR-XXX --summary "..."  # 创建变更
uv run spec-vc change clarify --motivation "..." ...        # 澄清阶段写入
uv run spec-vc change validate --phase pre/post --content "..."  # 验证记录
uv run spec-vc change close --summary "..."          # 关闭变更并回填 ADR

# 测试
uv run pytest tests/python/ -v                       # 运行全部测试
uv run pytest tests/python/test_spec.py -v           # 运行单个测试文件
uv run pytest tests/python/ -k "formalize"            # 按关键词筛选
```

## 架构概览

`src/spec_vc/` 下是 Python CLI，按**领域模型解耦**组织：

| 模块 | 职责 |
|------|------|
| `cli.py` | argparse 命令路由，所有入口函数（`build_parser()` 注册子命令，`cmd_<name>()` 实现） |
| `adr.py` | ADR 数据模型(dataclass)、解析、渲染、编号、豁免判定 |
| `spec.py` | Spec 数据模型(dataclass)、子目录管理、形式化文件生成、就绪检查 |
| `change.py` | 变更状态机(discover→clarify→plan→implement-ready→validate→close)、plan 文件 CRUD |
| `commit.py` | commit-msg 文件写入、subagent session 日志校验(`check_subagent_session`)、提交上下文收集 |
| `hooks.py` | commit-msg hook 校验链（session log → ADR 引用 → plan stage → Spec 完整性）、prepare-commit-msg hook、PostToolUse Agent 调用记录 |
| `config.py` | `.spec-vc.toml` 配置模型(ExemptionConfig/AdrRequiredConfig/SpecConfig)，支持 `ADR_DIR` 环境变量覆盖 |
| `status.py` | ADR↔commit 漂移检测（幽灵引用、孤儿 ADR、引用不一致） |
| `index.py` | ADR 索引维护（更新 README.md 表格） |
| `skill.py` | `skill load` 后端的聚合入口，组装上下文（active change、ADR required、spec 状态等） |
| `gitops.py` | `git` 命令封装(run_git, staged_files, staged_diff_numstat, repo_root_from) |
| `_sections.py` | Markdown 区块解析/替换/标题校验（被 adr/spec/change 复用） |
| `templates.py` | 模板路径定位（skill_root()/templates/） |
| `errors.py` | 异常层次(SpecVCError → UsageError / ValidationError) |

**依赖方向**: 基础层(errors/config/templates/gitops) ← 领域层(adr/spec/change/commit) ← 集成层(hooks/skill) ← CLI。

## 关键设计约定

**数据模型**: 所有领域对象用 `@dataclass(slots=True)`，Markdown 文件为持久化载体，正则解析。

**命令命名**: `spec-vc <domain> <action>`，如 `spec-vc spec new`、`spec-vc adr list`。`spec-vc commit` 和 `spec-vc adr init` 是顶层特殊命令。

**commit message**: `<type>(<scope>): <subject> [ADR-NNN]`，subject 用中文简述。严格模式(hook)阻塞无 `[ADR-NNN]` 或 `[ADR-none]` 的 commit。

**提交流程**（ADR-018 解耦 + ADR-019 审查助手 + ADR-020 减法 + ADR-022 文档基线，supersedes ADR-011）：
- `spec-vc review --mode subagent|simple --message "..." [--note "..."] [--verified]`：独立审查命令
  - 计算 anchor=ADR-XXX@<staged-diff-sha12>
  - **ADR-019**：先调 assemble_review_report 输出 5 段审查报告到 stderr（Staged Diff / Plan / Spec / Static Checks / Your Response），AI 读这份报告就是审查发生
  - 写 `.git/spec-vc-review.json` + `.git/spec-vc-commit-msg`
  - **ADR-022**：`review.json.document_baseline` 记录当前 ADR/Plan/关联 Spec 的路径、存在性与 sha256，作为审计语义基线
  - **ADR-020**：simple 模式 `--note` 不再强制含 anchor 子串（移除 reasoning scaffolding）
  - `--verified` 仅作记录，hook 不再校验（ADR-020 删除 `require_user_verified` 升级开关）
- 用户可在审查后跑代码、点 UI、测接口验证使用
- `spec-vc commit`（薄包装）或直接 `git commit`，commit-msg hook 自动校验
- **commit-msg hook 校验链 4 步（ADR-020 减法后 + ADR-022）**：SPEC_VC_BYPASS → ADR 引用 → [ADR-NNN] Spec 完整性 + review.json (anchor 匹配 + mtime 新鲜 + document_baseline 未漂移) → 放行；[ADR-none] 直接放行
- 所有阻塞错误统一为 BlockingError 结构（reason / current_state / fix_commands / docs_ref），AI 读 stderr 后可按 fix_commands 修复
- `commit prepare` 保留为 deprecation alias（等价于 `review --mode subagent`），打 warning

**SPEC_VC_BYPASS**: 环境变量逃生口，设 `<原因>` 后 `git commit` 跳过 review.json 校验，ADR 引用校验、Spec 完整性照常。bypass 写审计日志到 `.git/spec-vc-bypass.log`。

**模板系统**: `templates/` 下存放 ADR/Spec/commit 模板文件，通过 `template_path()` 访问。

**配置**: 项目配置在 `.spec-vc.toml`，CLI 通过 `load_config(repo_root)` 加载，dataclass 承载每个配置段。

**Skill 入口**: `SKILL.md` 是 Claude Code skill 的入口文件（给 AI 读的操作协议），`README.md` 是给人看的项目介绍。两者职责不同。

## ADR 写作规范（ADR-020 硬约束）

ADR 是项目的核心 reference document，写作规范如下（详见 `doc/arch/adr-020.md`）：

1. **自包含可读**：每条 ADR 必须能在不依赖前置 ADR 的情况下被理解。Context 段需重申必要的背景与初心
2. **锚点必含**：Plan summary 与 ADR Implementation Plans 段必须含 ≥ 1 个具体引用（`file:line` / `function_name()` / commit hash 之一）
3. **禁用宣示句式**：避免 "设计哲学转向"、"心智模型"、"X 取代 Y"、"sticks/carrots" 等抽象宣示。改用工程语言陈述代码事实
4. **哲学讨论 ≤ 1 段**：超过的内容写到独立回顾文章，不进 ADR 本体
5. **AI 行为假设需数据支撑**：声称 "AI 会绕过 X 因为 Y" 时必须引用 bypass log、测试用例或外部研究链接；无数据则不写

这套规范的目的：把 ADR 从"叙事承载"约束为"工程决策记录"，避免 ADR-006~018 时期出现的"哲学叙事覆盖工程改动"模式（VILA-Lab 判别法：reasoning scaffolding 应删，operational harness 应留）。

## 变更状态机

变更有 6 个阶段，存储在 `doc/arch/plans/_active.md`：

`discover` → `clarify` → `plan` → `implement-ready` → `validate` → `close`

- **clarify**: 6 个字段（motivation/boundary/design/implementation/verification/rollback）全部补齐后自动推进到 plan
- **plan**: 如果变更涉及接口/数据/行为，必须先完成 Spec 创作协议再进入 pre-validation
- **implement-ready**: `change validate --phase pre` 通过后进入，允许代码修改
- **validate**: 代码修改完成后 `change validate --phase post` 记录后置验证
- **close**: 回填 ADR 摘要 + Implementation Plans + References/Commits，清理 active context

## 新增 CLI 命令的模式

1. 在对应的领域模块写命令函数
2. 在 `cli.py::build_parser()` 注册子命令和参数
3. 命令函数签名: `def cmd_<name>(args: argparse.Namespace) -> int`
4. 通过 `_repo_root()` 获取仓库根，`load_config(repo_root)` 获取配置
5. 错误用 `raise UsageError(msg)` 或 `raise ValidationError(msg)`

## 测试

pytest，临时 git 仓库隔离测试。每个测试通过 `init_repo(tmp_path)` 创建干净的测试仓库（含 seed ADR-000 和 `.spec-vc.toml`），用 `run(repo, *args)` 执行 CLI 命令。`init_empty_repo(tmp_path)` 创建不含 spec-vc 初始化的空仓库。测试入口统一通过 `python -m spec_vc.cli`。
