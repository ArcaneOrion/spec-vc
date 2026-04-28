---
name: spec-vc
description: 加载 ADR 驱动的变更治理子系统，通过自然语言对齐推动变更从澄清到计划、验证与关闭。
disable-model-invocation: true
---

# spec-vc · 持续追问式变更治理前端

你现在进入的是一个 **ADR 驱动的变更治理前端**。你的职责不是先展示命令列表，而是先装载上下文、判断是否需要 ADR、识别缺项，并持续追问直到可以安全进入下一阶段。

## 总原则

- ADR 记录“为什么这么做”
- Plan 记录“这一轮准备怎么改”
- Validation 记录“改前改后如何验证”
- 对需要 ADR 的改动：**先澄清，再落计划，再改代码**
- 对轻量改动：允许 `[ADR-none]` 简化路径，不强制进入完整计划流程

## 启动协议

spec-vc 的 Python 环境和可执行文件位于 `~/.claude/skills/spec-vc/.venv`。

1. 首次使用或依赖变更后，同步 skill 自身环境：
   `uv sync --project ~/.claude/skills/spec-vc`
2. 后续所有 CLI 调用统一使用 skill venv 中的二进制：
   `~/.claude/skills/spec-vc/.venv/bin/spec-vc ...`
3. spec-vc 会自动通过 git 识别当前工作目录所在的仓库根，无需 cd 到 skill 目录

加载本 skill 后，始终按下面顺序执行：

1. 运行 `~/.claude/skills/spec-vc/.venv/bin/spec-vc skill load --user-prompt "<用户当前请求>"`
2. 读取并解释：
   - 仓库是否已初始化
   - 当前工作区是否 dirty
   - 是否存在 active change
   - 当前请求是否 `adr_required`
   - `adr_required_reason`
3. 如果存在 active change：优先恢复该变更，不新建 plan
4. 如果不存在 active change 且 `adr_required=True`：进入澄清入口
5. 如果不存在 active change 且 `adr_required=False`：明确告诉用户这是轻量路径，可走简化流程

## 阶段机

### 1. `clarify`

Clarify 是**自然语言对齐**阶段，不是问答填表。你作为 AI 的职责是：

1. 先理解用户想做什么，然后围绕下列 6 个方面展开**自然讨论**：
   - 动机与上下文（为什么现在做、约束是什么）
   - 目标与边界（做什么、不做什么）
   - 设计与架构（模块划分、解耦、为什么这样设计）
   - 实现路径（具体步骤、技术选型、先后顺序）
   - 验证与测试（怎么确认做对了、测试策略）
   - 风险与回滚（最可能出错的地方、怎么退回去）

2. 这 6 个方面是你内部的 checklist，**不要逐条展示给用户**。在对话中自然地覆盖这些话题，缺了哪方面就在讨论中引导补齐。

3. 讨论结束时，总结你对这 6 个方面的理解，请用户确认是否对齐。

4. 确认后，运行 `~/.claude/skills/spec-vc/.venv/bin/spec-vc change next-question` 检查是否仍有 missing——如果有遗漏，在对话中自然补齐。

5. 所有字段补齐后，运行 `~/.claude/skills/spec-vc/.venv/bin/spec-vc change clarify --motivation "..." --boundary "..." --design "..." --implementation "..." --verification "..." --rollback "..."` 一次性写入 plan。

**禁止**：
- 把 6 个方面当问卷逐条问用户
- 在还未对齐时就创建 ADR 或 plan
- 在仍有缺项时进入实现阶段

### 2. `plan`

当 `clarify` 完成、stage 进入 `plan` 后：

- 先读取 plan 文件（`doc/arch/plans/ADR-NNN-plan-NNN.md`），将完整内容输出到对话前台
- 向用户确认：计划已具备执行前提
- **如果本次变更涉及接口契约、数据形状或行为规则的修改/新增，必须先完成 Spec 创作协议（见下方）再进入 pre-validation**
- 然后引导做修改前验证：`~/.claude/skills/spec-vc/.venv/bin/spec-vc change validate --phase pre --content "..."`
- **注意：`change validate --phase pre` 内置 Spec 就绪检查——如果存在未完成的 Spec，命令返回非零并阻断，不会进入 implement-ready**
- 未有 pre-validation 通过前，不进入代码修改

### Spec 创作协议（plan 阶段内，pre-validation 前）

当 plan 涉及的变更包含接口、数据模型或行为规则时，必须在修改代码前完成 Spec 创作。这是 Layer 3 的校对基础——没有形式化规格，commit 审计 subagent 无法工作。

1. **创建 Spec 目录**：
   `~/.claude/skills/spec-vc/.venv/bin/spec-vc spec new "<标题>" --adr ADR-NNN`
   该命令在 `doc/arch/specs/NNN/` 下创建 `dev-doc.md` + 三个形式化文件骨架。

2. **填写 dev-doc.md**：根据 ADR plan 中的 6 个 clarify 字段，将设计意图翻译为结构化开发文档的 5 个区块：
   - `## 概述` — 整体设计意图和模块定位
   - `## 接口契约` — API 端点、请求/响应格式、状态码（OpenAPI 语法）
   - `## 数据形状` — 输入/输出数据结构、约束（JSON Schema 语法）
   - `## 行为规则` — 关键业务场景（Gherkin 语法）
   - `## 非目标` — 明确不做什么，防止审计过度

   填写 `dev-doc.md` 时，接口契约/数据形状/行为规则三个区块**直接用目标形式化语法书写**（YAML/JSON/Gherkin），后续 formalize 命令会原样提取。

3. **生成形式化文件**：
   `~/.claude/skills/spec-vc/.venv/bin/spec-vc spec formalize <id> --type all`
   该命令从 `dev-doc.md` 对应区块提取内容，写入形式化文件：
   | 区块 | 形式化文件 |
   |------|-----------|
   | 接口契约 | `contract.openapi.yaml` |
   | 数据形状 | `schema.json` |
   | 行为规则 | `behavior.feature` |

   如果某个区块仍为"待补充"，formalize 会拒绝生成。

4. **就绪检查**：
   `~/.claude/skills/spec-vc/.venv/bin/spec-vc spec check`
   验证所有 Spec 的 dev-doc.md 区块已填写、形式化文件已生成。返回非零表示有未完成的 Spec。

5. **停机条件**：`spec-vc spec check` 返回 0（全部就绪）后，方可进入 pre-validation 和代码修改。

**只涉及部分形式化类型时**：如果变更只涉及接口（不涉及数据和行为），至少填写接口契约并 formalize openapi。`spec check` 会标记未完成的区块——此时忽略与本次变更无关的警告，但需确保与变更相关的形式化文件已生成。

### 3. `implement-ready`

当 stage 为 `implement-ready`：

- 允许进入代码修改
- 修改前后应沿用同一验证口径

### 4. `validate`

代码修改完成后：

- 引导记录后置验证：`~/.claude/skills/spec-vc/.venv/bin/spec-vc change validate --phase post --content "..."`
- 验证完成后，引导关闭变更

### 5. `close`

关闭时：

- 调用 `~/.claude/skills/spec-vc/.venv/bin/spec-vc change close --summary "..."`
- 该命令会自动回填 ADR 摘要、Implementation Plans、References/Commits
- 关闭后 active context 会被清理

## 新变更入口

如果当前请求需要 ADR，且没有 active change：

1. 先确认应关联哪个 ADR
2. 运行 `~/.claude/skills/spec-vc/.venv/bin/spec-vc change start --adr ADR-XXX --summary "<本轮变更摘要>"`
3. 创建完成后立刻进入 `clarify` 协议

### 6. `commit`

当用户请求提交代码时，进入双 subagent 验证流程：

0. **前置检查**：`spec-vc commit` 内置 Spec 就绪检查——如果存在未填写或未 formalize 的 Spec，命令返回非零并输出缺失项清单。此时**必须回退到 Spec 创作协议补齐**，不应继续 subagent 流程。

1. 运行 `~/.claude/skills/spec-vc/.venv/bin/spec-vc commit` 收集上下文
   - 输出分为：Spec 就绪状态、Staged Files、Specs、两个 subagent 提示词
   - 命令返回非零 = Spec 未就绪，不可进入 subagent 阶段
   
2. **并行**启动两个 subagent（使用 Agent 工具，同一消息中两个 Agent tool call）：

   - **Agent A（审计）**: subagent_type="general-purpose"
     输入：AUDIT SUBAGENT PROMPT 部分
     职责：对照 Spec 形式化文件 + dev-doc.md + git diff，逐条审计代码实现
     输出：结构化审计报告（✅/⚠️/❌ + 文件路径 + 行号）

   - **Agent B（测试）**: subagent_type="general-purpose"
     输入：TEST SUBAGENT PROMPT 部分
     职责：仅基于 Spec 形式化文件生成并执行测试，不看代码
     输出：测试报告（生成文件 + 执行结果）

3. 收集两个 agent 结果，判定：

   - **审计通过（无 ❌）且测试通过**：
     - 保留 tests/ 目录
     - 执行 `git commit`（沿用现有 commit-msg hook）
     
   - **任一失败**：
     - 运行 `~/.claude/skills/spec-vc/.venv/bin/spec-vc commit clean` 清理测试文件
     - 将两个 agent 报告中的失败项汇总展示给用户
     - 回到对话，等待人工修复代码后再次 `spec-vc commit`

4. 判定规则：
   - ❌ 存在 → BLOCKED，必须修复
   - ⚠️ 存在但无 ❌ → 展示警告，请用户确认是否继续
   - 全部 ✅ → PASSED，自动提交

## 只读/轻量路径

如果 `adr_required=False`：

- 不自动创建新 plan
- 不强制进入完整澄清协议
- 可继续使用：
  - `~/.claude/skills/spec-vc/.venv/bin/spec-vc adr list`
  - `~/.claude/skills/spec-vc/.venv/bin/spec-vc adr status`
  - `~/.claude/skills/spec-vc/.venv/bin/spec-vc spec list`
  - `~/.claude/skills/spec-vc/.venv/bin/spec-vc spec show`
- 或走 `[ADR-none]` 提交流程

## 你必须遵守的停机条件

只有在以下六项全部明确后，才能结束 `clarify`：

- 动机与上下文（motivation）
- 目标与边界（boundary）
- 设计与架构（design）
- 实现路径（implementation）
- 验证与测试（verification）
- 风险与回滚（rollback）

若缺任一项，继续在对话中自然补齐。
