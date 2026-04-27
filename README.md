# spec-vc

**三层版本控制框架**的工具化实现仓库。仓库本身即为 Claude Code skill,`name: spec-vc`。

## 实现进度

| 层 | 命题类型 | 回答 | 版本化载体 | 子命令族 | 状态 |
|---|---|---|---|---|---|
| Layer 1 · Git | descriptive | 做了什么 | 源文件 diff | (git 原生,不由本 skill 提供) | ✅ 基础设施 |
| Layer 2 · 决策版本控制(ADR) | rationale | 为什么这么选 | Markdown | `/spec-vc adr-*` | 🟢 **v0.1 可用** |
| Layer 3 · 规格版本控制(可审计) | normative | 应该做什么 | OpenAPI / JSON Schema / Gherkin | `/spec-vc spec-*` | 🟢 **v0.2 可用** |

Layer 3 已实现:结构化开发文档(dev-doc.md) + 形式化文件(.yaml/.json/.feature) + 双 subagent 验证协议(spec-vc commit)。三层并非独立 skill——都在同一个 `spec-vc` skill 内,用子命令前缀区分层。

> 为什么需要三层版本控制？见 [前言 · 三层版本控制的动机与思想基础](doc/preface.md)。

## 仓库布局

```
spec-vc/                       ← 本仓库即 skill
├── README.md                  ← 框架总览 + 使用指南
├── SKILL.md                   ← Claude skill 入口(name: spec-vc)
├── pyproject.toml
├── .spec-vc.toml              ← 自身配置(吃狗粮)
├── src/spec_vc/               ← Python CLI 实现
│   ├── cli.py                 ← 命令路由
│   ├── adr.py                 ← ADR 领域模型
│   ├── change.py              ← 变更状态机
│   ├── spec.py                ← Spec 领域模型
│   ├── commit.py              ← 双 subagent 验证协议
│   ├── hooks.py               ← Git hook 校验
│   ├── config.py              ← 配置模型
│   ├── gitops.py              ← Git 操作封装
│   ├── skill.py               ← 子系统上下文加载
│   ├── status.py              ← ADR↔commit 漂移检测
│   ├── index.py               ← ADR 索引导出
│   └── _sections.py           ← Markdown 区块解析
├── templates/
│   ├── adr.md                 ← Nygard 五段式
│   ├── dev-doc.md             ← 结构化开发文档
│   ├── contract.openapi.yaml  ← OpenAPI 骨架
│   ├── schema.json            ← JSON Schema 骨架
│   ├── behavior.feature       ← Gherkin 骨架
│   ├── index.md               ← ADR 索引模板
│   ├── commit-msg             ← commit message 模板
│   └── seed-adr-000.md        ← 种子 ADR
├── hooks/
│   ├── prepare-commit-msg     ← 注入 [ADR-???] 槽位
│   └── commit-msg             ← 校验 ADR 引用
├── tests/python/              ← pytest 测试套件
└── doc/                       ← 本仓库自身的决策记录(吃狗粮)
    ├── preface.md             ← 前言:为什么需要三层版本控制
    └── arch/
        ├── README.md          ← ADR 索引
        ├── adr-NNN.md         ← ADR 文件
        └── plans/             ← 执行方案
```

初始化到目标项目后：

```
<project>/
├── doc/arch/
│   ├── README.md              ← ADR 索引
│   ├── adr-000.md             ← 种子 ADR
│   ├── adr-NNN.md             ← 自定义 ADR
│   ├── specs/                 ← Spec 目录
│   │   └── NNN/
│   │       ├── dev-doc.md
│   │       ├── contract.openapi.yaml
│   │       ├── schema.json
│   │       └── behavior.feature
│   └── plans/                 ← 执行方案
├── .spec-vc.toml              ← 项目配置
└── .git/hooks/
    ├── prepare-commit-msg
    └── commit-msg
```

## 快速使用

前置:你在 Claude Code 中加载了本仓库作为 skill。

### CLI 运行前提

`spec-vc` 是本项目在 `pyproject.toml` 中声明的 Python console script。第一性原理上说,它只有在下面两种条件之一成立时才能直接被 shell 找到:

- 该 entry point 已安装到当前 shell 可见的环境里
- 你已经激活了本项目对应的虚拟环境

skill 启动阶段最稳妥的做法,不是假设环境已激活,而是显式通过 `uv` 进入项目虚拟环境执行:

```bash
# 首次在仓库根目录准备环境
uv sync

# 之后统一这样调用
uv run spec-vc --help
uv run spec-vc skill load --user-prompt "你的请求"
```

如果你已经手动激活 `.venv`,也可以直接写 `spec-vc ...`;但 **SKILL 的引导文本默认应写成 `uv run spec-vc ...`**,否则很容易出现:

```bash
zsh: command not found: spec-vc
```

人在 Claude Code 中只需要三个动作：

```bash
# 1. 加载 skill（在 Claude Code 对话中）
/spec-vc

# 2. 初始化项目（AI 引导执行）
uv run spec-vc adr init

# 3. 提交代码（AI 引导验证后执行）
uv run spec-vc commit
```

其余命令（`adr new`、`spec new`、`spec formalize` 等）由 skill 的 AI 在对话流程中自动执行，人不必手动输入。详见 `SKILL.md`。

## Commit message 规范

```
<type>(<scope>): <subject> [ADR-NNN]

<body 可选>

<footer 可选>
```

示例:
```
feat(auth): 引入 LDAP 客户端 [ADR-007]
refactor(core): 拆分 message bus 为独立模块 [ADR-012]
docs: 修正 README 拼写 [ADR-none]
```

**豁免规则** (`[ADR-none]`):仅限不影响架构的改动。通过 `.spec-vc.toml` 的 `[exemption]` 配置段定制（路径、扩展名、行数阈值）。

## 路线图

- **v0.1**:`adr-*` 子命令族——ADR + Commit 锚定闭环 🟢
- **v0.2(当前)**:`spec-*` 子命令族——结构化开发文档 + 形式化文件 + 双 subagent 验证协议 🟢
- **v0.3**:Alice 项目首次实战,迭代严格度参数、打磨 subagent 审计协议、三层锚定漂移检测
- **v0.4**:强形式化预留位——spectral / ajv / Cucumber 机械验证器集成
- **v1.0**:Lean 4 / TLA+ 规格的创建和验证

## License

MIT
