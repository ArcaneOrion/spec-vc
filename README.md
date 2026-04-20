# spec-vc

**三层版本控制框架**的工具化实现仓库。

- **当前版本 (v0.1)**:`decision-vc/` skill 落地——ADR + Commit 双向锚定
- **未来 (v0.3+)**:`spec-vc/` skill 将新增——弱形式化(OpenAPI/Protobuf/JSON Schema/Gherkin)到强形式化(Lean 4/TLA+)的规格版本控制

## 为什么需要它

传统 `git` 只记录两件事:
- **做了什么**(diff)
- **怎么做的**(代码本身)

但系统的演进还涉及两件事没被版本控制:

- **为什么这么做**(决策 rationale) —— 留在人脑,人会遗忘、会离开。本仓库的 `decision-vc/` skill 用 ADR 的 markdown 文本把它显式化,校验手段是人工审阅。
- **应该做什么**(规格 normative) —— 需要一份**可机械验证的契约**,而不是散落在测试和文档里的非形式化约束。仓库未来的 `spec-vc/` skill 用 OpenAPI / Protobuf / JSON Schema / Gherkin(弱形式化)乃至 Lean 4 / TLA+(强形式化)作为载体,校验手段是 typechecker / prover / schema validator——**必须由机械过程产出**,不能是 AI 生成的"验证报告",否则规格版本控制退化为高级注释。

Agent 时代把这两个裂缝都放大了:

- Agent 参与生成代码,但不参与生成决策记忆。过两周连写代码的人自己都还原不出当时的约束。
- Agent 生成的代码"看起来正确"的门槛很低,但"被证明正确"的门槛没变。没有可机械验证的规格,Agent 按错误理解的契约生成完全自洽的代码,错得更隐蔽——所有测试都可能通过,因为测试也是它写的。

## 三层命题类型(正交,不可归约)

| 层级 | 对象 | 命题类型 | 回答 | 版本化载体 | 验证方式 |
|------|------|----------|------|------------|----------|
| Git | 代码实现 | descriptive | 做了什么 | 源文件 diff | 测试、运行时行为 |
| Spec VC | 行为规格 | normative | 应该做什么 | OpenAPI / Protobuf / Lean 4 | 类型检查 / 证明 / schema 校验 |
| ADR | 架构决策 | rationale | 为什么这么选 | Markdown | 人工审阅、上下文一致性 |

三者**正交**——用同一个 artifact 承载多种命题类型,必然互相污染。

## 仓库布局

```
spec-vc/                      ← 本仓库(伞 / 三层框架的主仓)
├── README.md                 ← 本文件,框架总览
├── LICENSE                   ← (待定)
├── decision-vc/              ← v0.1 的 skill
│   ├── SKILL.md              ← Claude skill 入口(name: decision-vc)
│   ├── commands/             ← 斜杠命令实现
│   │   ├── init.md
│   │   ├── new.md
│   │   ├── link.md
│   │   ├── status.md
│   │   ├── list.md
│   │   └── upgrade.md
│   ├── templates/
│   │   ├── adr.md            ← Nygard 五段式
│   │   ├── index.md          ← ADR 索引模板
│   │   ├── commit-msg        ← git commit message 模板
│   │   └── seed-adr-000.md   ← init 时的种子 ADR(固定内容)
│   ├── hooks/
│   │   ├── prepare-commit-msg ← 起草时注入 [ADR-???] 槽位
│   │   └── commit-msg         ← 严格校验 ADR 引用存在 + 状态有效
│   ├── scripts/
│   │   ├── check-refs.sh      ← ADR↔commit 双向引用扫描
│   │   └── new-adr.sh         ← 自增编号生成 ADR
│   └── tests/
│       └── e2e-init.sh        ← 最小端到端测试
└── (未来:spec-vc-skill/)      ← v0.3 的 normative 层 skill
```

初始化一个目标项目(如 Alice)后,目标项目会多出:

```
<project>/
├── doc/
│   └── arch/
│       ├── README.md         ← ADR 索引(由 decision-vc 维护)
│       ├── adr-000.md        ← 种子:采用 ADR 方法论
│       └── adr-NNN.md ...
└── .git/
    └── hooks/
        ├── prepare-commit-msg
        └── commit-msg
```

## 快速使用

前置:你在 Claude Code 中加载了本仓库的 `decision-vc/` 作为 skill。

```bash
# 1. 在目标项目中初始化
cd /path/to/your/project
git init  # 若尚未初始化
# 在 Claude Code 中运行
/decision-vc init

# 2. 每次做架构决策时
/decision-vc new "使用 LDAP 进行多租户集成"
# → 生成 doc/arch/adr-007.md,打开编辑器填写五段式

# 3. 写完代码后 commit
git add .
git commit
# → prepare-commit-msg hook 提示 [ADR-???]
# → 把它替换为 [ADR-007]
# → commit-msg hook 校验 ADR-007 存在且状态有效后放行

# 4. 定期检查三层锚定健康
/decision-vc status

# 5. 本仓库更新了 hook 后,同步到已初始化项目
/decision-vc upgrade
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

**豁免规则** (`[ADR-none]`):仅限不影响架构的改动。具体判定见 `decision-vc/hooks/commit-msg` 中的 `check_exemption` 函数(当前为占位,需按项目定制)。

## 路线图

- **v0.1(当前)**:`decision-vc` skill——ADR + Commit 锚定闭环
- **v0.2**:在 Alice 项目做首次实战,迭代严格度参数、打磨 `check_exemption` 规则
- **v0.3**:新增 `spec-vc/` skill——弱形式化(OpenAPI/Protobuf/JSON Schema/Gherkin)
- **v0.4**:三层锚定——ADR 引用 Spec 版本,Spec 引用 Code 契约
- **v1.0**:强形式化预留位——Lean 4 / TLA+ 规格的创建和验证

## 思想基础

- Michael Nygard (2011) · Documenting Architecture Decisions
- 三层命题类型的分离:descriptive ≠ normative ≠ rationale
- Agent 时代的版本控制语义层扩展:从"代码的时间机器"升级为"决策的时间机器"

## License

待定(计划:MIT 或 CC0,以鼓励复用)。

## Contributing

本仓库遵循自己的规范——内部开发也用 decision-vc 管理架构演进,ADR 存于本仓库 `decision-vc/doc/arch/`(初始化后)。
