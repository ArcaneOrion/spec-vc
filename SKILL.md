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
3. **意图分类（流程守卫）**：在进入任何流程之前，先判断用户当前请求的性质（见下方"意图分类与流程守卫"）。只有确认或倾向为变更相关时，才继续进入 spec-vc 流程。
4. 如果存在 active change：优先恢复该变更，不新建 plan
5. 如果不存在 active change 且 `adr_required=True`：进入澄清入口
6. 如果不存在 active change 且 `adr_required=False`：明确告诉用户这是轻量路径，可走简化流程

## 阶段机

### 1. `clarify`

Clarify 是**自然语言对齐**阶段，不是问答填表。你作为 AI 的职责是：

**核心原则：6 个字段是必要条件，不是充分条件。** 对齐阶段的目标是让 AI 和用户对变更达成完整理解——任何有助于理解变更的信息（项目现状、代码结构、历史决策、技术约束、用户探索中发现的问题等）都应该被自然获取和保留。不要为了凑齐 6 个字段而跳过理解过程；反过来，也不要因为 6 个字段还没齐就阻断有价值的探索性对话。

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
  - CLI: `~/.claude/skills/spec-vc/.venv/bin/spec-vc change show` 可直接输出当前 plan
- 向用户确认：计划已具备执行前提
- **如果本次变更涉及接口契约、数据形状或行为规则的修改/新增，必须先完成 Spec 创作协议（见下方）再进入 pre-validation**
- 然后引导做修改前验证：`~/.claude/skills/spec-vc/.venv/bin/spec-vc change validate --phase pre --content "..."`
- **`change validate --phase pre` 包含 3 项检查**：(1) 当前 stage ∈ {discover, clarify} 且字段未补齐时阻塞并打印缺失项；(2) 当前 ADR 关联的 Spec 是否就绪（仅检查关联 Spec，不被无关 ADR 的 Spec 误伤）；(3) 若 ADR 无关联 Spec，则给出"是否需要走 Spec 创作协议"的提示但不阻塞。任一阻塞项失败都会打印可执行指引和 SKILL.md 引用，命令返回非零
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

**查看完整 Spec（含形式化文件内容）**：
- `spec-vc spec show <id>` — 查看 dev-doc.md
- `spec-vc spec show <id> --formal` — 查看 dev-doc.md + 所有形式化文件内容
- `spec-vc adr show <id>` — 查看任意 ADR 完整内容

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

### 6. `review` + `commit`（审查/提交解耦，ADR-018）

提交流程从 ADR-018 起拆为两个独立动作：`spec-vc review`（写审计证据） → 用户可实际跑代码验证 → `spec-vc commit`（薄包装 git commit） → commit-msg hook 校验。

**核心原则**：
- 审查与提交解耦——commit 不再承担审查门禁，AI 可以"先审查、再让用户验证、再提交"
- 审计证据用直接文件 `.git/spec-vc-review.json` 承载，commit-msg hook 直接读这个文件
- 所有阻塞错误统一为 `BlockingError` 结构：`reason / current_state / fix_commands / docs_ref`，AI 读取后可自我修复
- `[ADR-none]` 走量化判定（文件数 + 类型白名单 + 行数）

ADR-018 supersedes ADR-011 的"prepare + hook 单路径"和 ADR-017 的"session log + anchor 间接证据"——审计证据不再依赖 PostToolUse hook 这条间接通道（PostToolUse hook 仍保留写 session log，但 commit-msg hook 不再读）。

#### 6a. AI 域：`spec-vc review` —— 独立审查命令

0. **前置检查**：`spec-vc review` 内置 Spec 就绪检查——若有未完成 Spec，命令返回非零并输出缺失项清单到 stderr。**必须回退到 Spec 创作协议补齐**。

1. 运行 `~/.claude/skills/spec-vc/.venv/bin/spec-vc review --mode subagent --message "<完整 commit message>"`
   - 参数：
     - `--mode subagent|simple`（默认 subagent）
     - `--note "<审查结论>"`（simple 模式必填且必须含 anchor 子串）
     - `--verified`（标记用户已实际跑过代码验证使用）
   - 行为：
     - 计算 `anchor = "ADR-XXX@<staged-diff-sha12>"`，`sha12` 是 staged diff 内容指纹
     - 写 `.git/spec-vc-review.json`（含 anchor / mode / verified / note / created_at）
     - 写 `.git/spec-vc-commit-msg`（commit message 文本）
     - stdout 输出 `audit-anchor: <anchor>` + 下一步指引

2. **subagent 模式（默认，推荐）**：可启动 audit subagent 做代码审查（可选）。subagent 仍会通过 PostToolUse hook 写 session log，但本 ADR 后这条通道仅作辅助日志，不再是 commit-msg hook 的硬证据。

3. **simple 模式**：当不想或无法启动 subagent 时，AI 必须在 `--note` 文本里复述 anchor 子串。"通过门禁的最小成本 = 至少看一眼 review 输出抄一次 sha12"。

4. **用户实际验证**：审查完成后用户可跑代码、点 UI、测接口。完成后用 `--verified` 标记（写入 `review.json.verified=true`）。默认 honor system；配置 `.spec-vc.toml` 的 `[lightweight] require_user_verified = true` 后升级为硬门禁。

5. **AI 执行 commit**：`spec-vc commit`（薄包装）或直接 `git commit`，commit-msg hook 自动校验。

#### 6b. commit-msg hook 校验链（ADR-018 重构）

hook 在 `git commit` 时自动触发：

1. `SPEC_VC_BYPASS` 非空 → 写 bypass 审计日志，跳到第 2 步
2. ADR 引用格式：
   - 无 `[ADR-NNN]`/`[ADR-none]` → 阻塞（`BlockingError` 输出）
   - `[ADR-???]` 未填充 → 阻塞
   - `[ADR-none]` → 走第 5 步（量化判定）
   - `[ADR-NNN]` → 走第 3-4 步
3. `[ADR-NNN]` plan stage：按 adr_id 路由查 stage，必须 ≥ `implement-ready`；ADR 已 close 无 plan 文件 → 放行
4. `[ADR-NNN]` 审计校验（`SPEC_VC_BYPASS` 时跳过）：
   - Spec 完整性（ADR 关联的 Spec dev-doc 与形式化文件就绪）
   - `.git/spec-vc-review.json` 存在 + 可解析
   - `review.json.anchor` 匹配当前 staged sha12（不匹配 → 阻塞 + 输出 expected/actual）
   - `review.json` mtime > `.git/spec-vc-commit-msg` mtime（证据不新鲜 → 阻塞）
   - `mode == simple` 时 `review.json.note` 含 anchor 子串
   - `require_user_verified=true` 且 `review.json.verified=false` → 阻塞
5. `[ADR-none]` 量化判定（`SPEC_VC_BYPASS` 时跳过）：
   - staged files ≤ `lightweight.files_max`（默认 5）
   - 全部命中 `lightweight.type_whitelist`（默认 `*.md / *.txt / doc/** / docs/** / .gitignore / .editorconfig / *.json`）
   - 净变更 ≤ `lightweight.lines_max`（默认 50）
   - 未命中 → `BlockingError` 阻塞，输出未命中规则与升级指引
6. 全部通过 → 放行

阻塞输出统一格式：

```
[spec-vc] BLOCKED: <reason>

Current state:
  <事实摘要，含文件存在性·mtime·anchor 实际值>

How to fix:
  $ <可粘贴 shell 命令>

Docs:
  - <SKILL.md 章节 / ADR / Spec 锚点>
```

AI 读取 stderr 后可按 `How to fix` 直接修复，避免循环 bypass。

#### 6c. `spec-vc commit` —— 薄包装提交入口

`spec-vc commit` 不做审查，只做：
1. 防御性 Spec 就绪检查
2. 应用 `.git/spec-vc-commit-msg` 调 `git commit -F`
3. hook 阻塞时透传 stderr + 输出引导信息

`spec-vc commit prepare` 保留为 deprecation alias（等价于 `spec-vc review --mode subagent`），调用时打 `[spec-vc] DEPRECATION:` 警告。

#### 6d. PostToolUse hook（保留为辅助日志）

PostToolUse hook 仍按 ADR-016 的 stdin JSON 协议写 `.git/spec-vc-subagent-sessions.log`，但本 ADR 后 commit-msg hook 不再读它——审计证据全部由 `review.json` 承载。

`.claude/settings.json` 配置（由 `spec-vc init` 自动写入）：

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Agent",
        "hooks": [{
          "type": "command",
          "command": "~/.claude/skills/spec-vc/.venv/bin/spec-vc hook post-tool-use"
        }]
      }
    ]
  }
}
```

ADR-013 / ADR-016 / ADR-017 对 PostToolUse hook 的行为约束保持有效（空 description 跳过 / stdin JSON 优先 / PostToolUseFailure 守卫）。

#### 6e. 失败恢复

`git commit` 被 hook 阻塞后，按 `BlockingError` 的 `How to fix` 指引修复（重跑 `spec-vc review` / 推进 plan stage / 完成 Spec），然后重新 `git add` + `spec-vc commit` 或 `git commit`。

#### 6f. `SPEC_VC_BYPASS` 保留

bypass 在 spec-vc 损坏时作为逃生口：设置 `SPEC_VC_BYPASS=<原因>` 后 `git commit` 跳过 `review.json` 校验、量化判定。ADR 引用校验、plan stage 检查、Spec 完整性检查照常。bypass 触发写入 `.git/spec-vc-bypass.log`。

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

## 意图分类与流程守卫

加载 spec-vc skill 后，**不管用户说什么**，AI 必须先判断请求性质，再决定走哪条路径。这是流程的入口守卫——防止 AI 默认进入"解答模式"而跳过治理流程。

### 分类标准

| 类型 | 特征 | 处理方式 |
|------|------|----------|
| **信息查询** | 用户在问"是什么"、"为什么"、"怎么用"、"介绍一下" | 直接回答，不进入变更流程。可以自然过渡到变更（见下方） |
| **变更相关** | 用户在说"我要改"、"这里有问题"、"加个功能"、"重构"、"修 bug" | 必须进入 spec-vc 流程 |
| **模糊/探索** | 用户说"帮我看看"、"这个功能"、"有什么问题"、"我觉得可以优化" | 先对话帮助用户明确意图，识别出属于上述哪类后再决定 |

### 从信息查询自然过渡到变更

用户经常先通过对话获取项目上下文，然后才发现需要做变更。这是正常的探索过程，不是流程漏洞。

- 当信息查询对话中浮现出变更意图时，AI 应主动提示："看起来你想做 X 变更，我们需要进入 clarify 流程来对齐。"
- 对话中获得的上下文（代码分析、问题定位、现状理解等）**直接带入 clarify 阶段**，不需要重新讨论
- 不要因为一开始没走流程就丢弃已有的对话上下文

### 误判恢复

- **变更误判为信息查询**：用户明确说"我要改这个"时，立即切换到流程模式，不坚持"这是信息查询"
- **信息查询误判为变更**：用户澄清只是想了解时，退出流程模式，直接回答问题
- 判断标准是**用户意图的实质**，不是 `adr_required` 的返回值——`adr_required` 只在确认为变更后才生效

## 你必须遵守的停机条件

只有在以下六项全部明确后，才能结束 `clarify`：

- 动机与上下文（motivation）
- 目标与边界（boundary）
- 设计与架构（design）
- 实现路径（implementation）
- 验证与测试（verification）
- 风险与回滚（rollback）

若缺任一项，继续在对话中自然补齐。
