---
name: spec-vc
description: 加载 ADR 驱动的变更治理子系统，并以持续追问的方式推动变更从澄清到计划、验证与关闭。
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

在执行任何 `spec-vc` CLI 命令前,先确认当前仓库根目录可用以下两种方式之一:

- 优先使用 `uv run spec-vc ...`
- 若用户已手动激活本项目虚拟环境,也可直接使用 `spec-vc ...`

如果未确认虚拟环境已激活,**默认一律使用 `uv run`**,不要假设 shell 里已经存在 `spec-vc` 可执行文件。

推荐顺序:

1. 先在仓库根目录执行 `uv sync`
2. 后续所有 CLI 调用统一写成 `uv run spec-vc ...`

这样即使用户 shell 没有激活 `.venv`,也不会出现 `zsh: command not found: spec-vc`。

加载本 skill 后，始终按下面顺序执行：

1. 运行 `uv run spec-vc skill load --user-prompt "<用户当前请求>"`
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

如果当前 stage 是 `clarify`，不要让用户手写完整命令参数。你要：

1. 运行 `uv run spec-vc change next-question`
2. 读取返回的：
   - `missing`
   - `next_field`
   - `next_prompt`
3. 只围绕 `next_prompt` 对用户发问
4. 得到回答后，把**已知字段 + 新回答**统一写回 `uv run spec-vc change clarify ...`
5. 如果 CLI 返回仍有 `missing:`，继续下一轮追问
6. 只有当不再有缺项时，才停止澄清并进入 `plan`

固定追问顺序如下：

1. `goal` → 目标
2. `scope` → 范围
3. `non_goals` → 非目标
4. `strategy` → 实现策略
5. `risks` → 风险与回滚
6. `acceptance` → 验收标准

**禁止**：
- 一次追问多个缺项，除非用户主动一次性补全
- 重复问已经明确的字段
- 在仍有缺项时进入实现阶段

### 2. `plan`

当 `clarify` 完成、stage 进入 `plan` 后：

- 先向用户确认：计划已具备执行前提
- 然后引导做修改前验证：`uv run spec-vc change validate --phase pre --content "..."`
- 未有 pre-validation 前，不进入代码修改

### 3. `implement-ready`

当 stage 为 `implement-ready`：

- 允许进入代码修改
- 修改前后应沿用同一验证口径

### 4. `validate`

代码修改完成后：

- 引导记录后置验证：`uv run spec-vc change validate --phase post --content "..."`
- 验证完成后，引导关闭变更

### 5. `close`

关闭时：

- 调用 `uv run spec-vc change close --summary "..."`
- 该命令会自动回填 ADR 摘要、Implementation Plans、References/Commits
- 关闭后 active context 会被清理

## 新变更入口

如果当前请求需要 ADR，且没有 active change：

1. 先确认应关联哪个 ADR
2. 运行 `uv run spec-vc change start --adr ADR-XXX --summary "<本轮变更摘要>"`
3. 创建完成后立刻进入 `clarify` 协议

## 只读/轻量路径

如果 `adr_required=False`：

- 不自动创建新 plan
- 不强制进入完整澄清协议
- 可继续使用：
  - `uv run spec-vc adr list`
  - `uv run spec-vc adr status`
- 或走 `[ADR-none]` 提交流程

## 你必须遵守的停机条件

只有在以下六项全部明确后，才能结束 `clarify`：

- 目标（goal）
- 范围（scope）
- 非目标（non_goals）
- 实现策略（strategy）
- 风险与回滚（risks）
- 验收标准（acceptance）

若缺任一项，继续追问。
