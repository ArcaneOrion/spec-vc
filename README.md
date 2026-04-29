# spec-vc

一个在 Claude Code 中运行的变更治理工具。它试图解决一个问题：软件开发中，"为什么这么做"和"应该做什么"这两层信息往往散落在 PR、Slack、口头讨论里，事后很难追溯。

## 设计理念

传统版本控制（Git）只记录"做了什么"。spec-vc 在此基础上补了两层：

- **ADR（Architecture Decision Record）**：记录"为什么这么做"——决策的背景、权衡和结论
- **Spec（形式化规格）**：记录"应该做什么"——接口契约、数据形状、行为规则，用 OpenAPI / JSON Schema / Gherkin 描述

三层叠在一起，形成一个从"为什么"到"做什么"到"做了什么"的完整链路。

核心原则是：**先澄清，再落计划，再改代码**。轻量改动允许简化路径（`[ADR-none]`），不强制走完整流程。

## 架构

```
spec-vc/
├── src/spec_vc/          # Python CLI
│   ├── cli.py            # 命令路由
│   ├── adr.py            # ADR 领域模型
│   ├── spec.py           # Spec 领域模型
│   ├── change.py         # 变更状态机
│   ├── commit.py         # commit 验证协议
│   ├── hooks.py          # Git hook 校验
│   └── ...
├── templates/            # ADR/Spec/commit 模板
├── hooks/                # Git hook 脚本
└── SKILL.md              # Claude Code skill 入口
```

初始化到项目后：

```
<project>/
├── doc/arch/
│   ├── adr-NNN.md        # ADR 文件
│   ├── specs/NNN/        # Spec 目录（dev-doc + 形式化文件）
│   └── plans/            # 执行方案
├── .spec-vc.toml         # 项目配置
└── .git/hooks/           # commit-msg hook
```

## 运行流程

一个变更从开始到结束的典型路径：

```
用户提出变更意图
    ↓
skill load → 意图分类 → 确认需要 ADR
    ↓
clarify：自然语言对齐（动机、边界、设计、实现、验证、风险）
    ↓
plan：落为结构化计划文件
    ↓
spec：创建形式化规格（如果涉及接口/数据/行为）
    ↓
pre-validation：修改前验证口径
    ↓
代码修改
    ↓
post-validation：修改后验证
    ↓
spec-vc commit：多 agent 验证 → 提交
    ↓
close：回填 ADR 摘要，关闭变更
```

轻量改动（文档修改、小修小补）可以走 `[ADR-none]` 路径，跳过完整流程。

## spec-vc commit 做了什么

`spec-vc commit` 不只是 `git commit` 的包装。它在提交前会执行一个多 agent 验证协议：

1. **收集上下文**：CLI 收集 staged diff、关联的 Spec、形式化文件，生成 manifest
2. **动态分配 subagent**：根据复杂度报告，启动多个审计 subagent 和测试 subagent 并行工作
   - 审计 subagent：检查代码是否符合 Spec（接口契约、数据形状、行为规则）
   - 测试 subagent：验证形式化规格的可测试性
3. **机械化 post-check**：覆盖率检查、格式合规检查、物证检查
4. **语义审查**：主 agent 做矛盾检测和遗漏判断
5. **判定**：
   - 全部通过 → 自动提交
   - 存在警告 → 展示给用户确认
   - 存在问题 → BLOCKED，修复后重试

这个机制的目的是：**让每次提交都有可追溯的验证证据**，而不只是"代码能跑就行"。

## 快速使用

### 安装

```bash
git clone <repo-url> ~/.claude/skills/spec-vc
cd ~/.claude/skills/spec-vc
uv sync
```

### 初始化项目

在 Claude Code 中进入你的项目目录，运行：

```
/spec-vc init
```

### 提交代码

修改代码后，在 Claude Code 中运行：

```
/spec-vc commit
```

AI 会引导你完成验证流程，通过后自动提交。

### 其他命令

其余命令（`adr new`、`spec new`、`spec formalize` 等）由 AI 在对话流程中自动执行，一般不需要手动输入。

## Commit message 规范

```
<type>(<scope>): <subject> [ADR-NNN]
```

示例：
```
feat(auth): 引入 LDAP 客户端 [ADR-007]
refactor(core): 拆分 message bus 为独立模块 [ADR-012]
docs: 修正 README 拼写 [ADR-none]
```

`[ADR-none]` 仅限不影响架构的改动。

## 友情链接

- [Linux.do](https://linux.do/)

## License

MIT
