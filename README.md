# spec-vc

**三层版本控制框架**的工具化实现仓库。仓库本身即为 Claude Code skill,`name: spec-vc`。

## 实现进度

| 层 | 命题类型 | 回答 | 版本化载体 | 子命令族 | 状态 |
|---|---|---|---|---|---|
| Layer 1 · Git | descriptive | 做了什么 | 源文件 diff | (git 原生,不由本 skill 提供) | ✅ 基础设施 |
| Layer 2 · 决策版本控制(ADR) | rationale | 为什么这么选 | Markdown | `/spec-vc adr-*` | 🟢 **v0.1 可用** |
| Layer 3 · 规格版本控制(可审计) | normative | 应该做什么 | OpenAPI / JSON Schema / Gherkin | `/spec-vc spec-*` | 🟢 **v0.2 可用** |

Layer 3 已实现:结构化开发文档(dev-doc.md) + 形式化文件(.yaml/.json/.feature) + 双 subagent 验证协议(spec-vc commit)。三层并非独立 skill——都在同一个 `spec-vc` skill 内,用子命令前缀区分层。

## 为什么需要它

传统 `git` 只记录两件事:
- **做了什么**(diff)
- **怎么做的**(代码本身)

但系统的演进还涉及两件事没被版本控制:

- **为什么这么做**(决策 rationale) —— 留在人脑,人会遗忘、会离开。本 skill 的 `adr-*` 子命令族用 ADR 的 markdown 文本把它显式化,校验手段是人工审阅。
- **应该做什么**(规格 normative) —— 需要一份**可机械验证的契约**,而不是散落在测试和文档里的非形式化约束。未来的 `spec-*` 子命令族将用 OpenAPI / Protobuf / JSON Schema / Gherkin(弱形式化)乃至 Lean 4 / TLA+(强形式化)作为载体,校验手段是 typechecker / prover / schema validator——**必须由机械过程产出**,不能是 AI 生成的"验证报告",否则规格版本控制退化为高级注释。

Agent 时代把这两个裂缝都放大了:

- Agent 参与生成代码,但不参与生成决策记忆。过两周连写代码的人自己都还原不出当时的约束。
- Agent 生成的代码"看起来正确"的门槛很低,但"被证明正确"的门槛没变。没有可机械验证的规格,Agent 按错误理解的契约生成完全自洽的代码,错得更隐蔽——所有测试都可能通过,因为测试也是它写的。

## 三层命题类型(正交,不可归约)

三者正交——用同一个 artifact 承载多种命题类型,必然互相污染。它们通过**显式引用**相互锚定,不是线性栈:一条 ADR 可锚定多个 spec 单元;一个 spec 版本对应一组 code commit 范围。

## 仓库布局(扁平)

```
spec-vc/                       ← 本仓库即 skill
├── README.md                  ← 本文件(框架总览 + 实现进度)
├── LICENSE                    ← (待定)
├── SKILL.md                   ← Claude skill 入口(name: spec-vc)
├── commands/                  ← 斜杠命令实现
│   ├── adr-init.md            ← /spec-vc adr-init
│   ├── adr-new.md
│   ├── adr-link.md
│   ├── adr-status.md
│   ├── adr-list.md
│   ├── adr-upgrade.md
│   └── (未来:spec-init.md / spec-new.md / spec-validate.md / ...)
├── templates/
│   ├── adr.md                 ← Nygard 五段式
│   ├── dev-doc.md             ← 结构化开发文档
│   ├── index.md               ← ADR 索引模板
│   ├── commit-msg             ← git commit message 模板
│   ├── seed-adr-000.md        ← init 时的种子 ADR(固定内容)
│   ├── contract.openapi.yaml  ← OpenAPI 骨架
│   ├── schema.json            ← JSON Schema 骨架
│   └── behavior.feature       ← Gherkin 骨架
├── hooks/
│   ├── prepare-commit-msg     ← 起草时注入 [ADR-???] 槽位
│   └── commit-msg             ← 严格校验 ADR 引用存在 + 状态有效
├── scripts/
│   ├── check-refs.sh          ← ADR↔commit 双向引用扫描
│   └── new-adr.sh             ← 自增编号生成 ADR
├── tests/
│   └── e2e-init.sh            ← 最小端到端测试(12 用例)
└── doc/                       ← 本仓库自身的决策记录(吃狗粮)
    └── arch/
        ├── README.md
        ├── adr-000.md         ← 采用 ADR 方法论
        ├── adr-001.md         ← 严格模式 + [ADR-none] 豁免
        └── adr-NNN.md ...
```

初始化一个目标项目(如 Alice)后,**目标项目**会多出:

```
<project>/
├── doc/
│   └── arch/
│       ├── README.md          ← ADR 索引(由 spec-vc 维护)
│       ├── adr-000.md         ← 种子:采用 ADR 方法论
│       └── adr-NNN.md ...
└── .git/
    └── hooks/
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

```bash
# 1. 在目标项目中初始化
cd /path/to/your/project
git init  # 若尚未初始化
# 在 Claude Code 中运行
/spec-vc adr-init

# 2. 每次做架构决策时
/spec-vc adr-new "使用 LDAP 进行多租户集成"
# → 生成 doc/arch/adr-007.md,打开编辑器填写五段式

# 3. 写完代码后 commit
git add .
git commit
# → prepare-commit-msg hook 提示 [ADR-???]
# → 把它替换为 [ADR-007]
# → commit-msg hook 校验 ADR-007 存在且状态有效后放行

# 4. 定期检查三层锚定健康
/spec-vc adr-status

# 5. 本仓库更新了 hook 后,同步到已初始化项目
/spec-vc adr-upgrade
```

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

**豁免规则** (`[ADR-none]`):仅限不影响架构的改动。具体判定见 `hooks/commit-msg` 中的 `check_exemption` 函数(当前为占位,需按项目定制)。

## 路线图

- **v0.1**:`adr-*` 子命令族——ADR + Commit 锚定闭环 🟢
- **v0.2(当前)**:`spec-*` 子命令族——结构化开发文档 + 形式化文件 + 双 subagent 验证协议 🟢
- **v0.3**:Alice 项目首次实战,迭代严格度参数、打磨 subagent 审计协议、三层锚定漂移检测
- **v0.4**:强形式化预留位——spectral / ajv / Cucumber 机械验证器集成
- **v1.0**:Lean 4 / TLA+ 规格的创建和验证

## 思想基础

- Michael Nygard (2011) · Documenting Architecture Decisions
- 三层命题类型的分离:descriptive ≠ normative ≠ rationale
- Agent 时代的版本控制语义层扩展:从"代码的时间机器"升级为"决策的时间机器"

## License

待定(计划:MIT 或 CC0,以鼓励复用)。

## Contributing

本仓库遵循自己的规范——内部开发也用 spec-vc 管理架构演进,ADR 存于本仓库 `doc/arch/`。查看 `doc/arch/README.md` 了解本仓库自身的决策史。
