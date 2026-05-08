# 修改计划：门禁消息增强 + ADR→Spec 编号对齐 + ADR 编号连续性检查

## 原因

ADR-011 的实施过程暴露了两个流程断点：

1. **改代码之前没有强制门禁**：`change validate --phase pre` 只检查全局 Spec 就绪，不检查 ADR 是否有关联 Spec、clarify 是否完成。AI 可以跳过 Spec 创作协议直接改代码。
2. **commit 阻塞消息只有"不行"没有"怎么做"**：错误消息是功能性描述，AI 不知道下一步该干什么。
3. **ADR 和 Spec 编号不对齐**：ADR-011 创建了 Spec-005，但编号应该对齐为 Spec-011。Spec 编号应跟随其关联的 ADR 编号。
4. **ADR 创建前不检查编号连续性**：`next_adr_id` 取最大值+1，可能产生编号空洞。

核心改进：门禁失败时输出分步指引 + SKILL.md 引用；Spec 编号与 ADR 编号对齐。

## 行为变更

### 1. `hooks.py` — commit-msg hook 错误消息增强

每条阻塞消息追加"下一步"指引和 SKILL.md 引用：

| 当前消息 | 增强后 |
|---------|--------|
| `"未找到 subagent 审计记录"` | 追加：下一步使用 Agent 工具执行审计，PostToolUse hook 自动记录。如未配置 hook，运行 spec-vc init |
| `"stage 为 '{stage}'，需推进到 implement-ready"` | 追加：下一步运行 `spec-vc change validate --phase pre --content "..."` |
| `"Spec 未完成"` | 追加：分步指引（spec new → 填写 dev-doc → formalize → spec check）|

所有阻塞消息末尾追加：`详细流程请查看 SKILL.md`

### 2. `cli.py` — `cmd_commit_prepare` 提示消息增强

改后：
```
[spec-vc] 请完成 subagent 审计后直接 git commit。commit-msg hook 会自动校验：
  1. subagent session log 非空（PostToolUse hook 自动记录）
  2. ADR 引用合法
  3. [ADR-NNN 时] plan stage ≥ implement-ready
  4. [ADR-NNN 时] Spec 完整（非骨架）
详细流程请查看 SKILL.md
```

### 3. `change.py` / `cli.py` — `change validate --phase pre` 增强

- **clarify 完整性检查**：如果 active change stage 仍为 discover/clarify，阻塞并提示需要完成 clarify
- **ADR→Spec 关联检查**：如果 active change 的 ADR 没有关联 Spec 且变更涉及代码路径，提示需要走 Spec 创作协议
- **失败输出格式**：问题列表 + 分步指引 + SKILL.md 引用

### 4. `spec.py` / `cli.py` — Spec 编号与 ADR 编号对齐

`spec new --adr ADR-012` 时，Spec 编号使用 ADR 编号（012），而非自动递增。如果该编号的 Spec 目录已存在，则报错。

### 5. `adr.py` / `cli.py` — ADR 创建前编号连续性检查

`adr new` 创建前检查是否有编号空洞（如存在 000-010 但没有 011），如果有空洞则提示。仍然允许用户使用下一个连续编号，但给出警告。

### 6. `hooks.py` — `_check_plan_stage` 和 `_check_spec_readiness_for_adr` 消息增强

这两个函数在 ADR-011 中已实现，现在增强错误消息，加入可执行指引。

## 文件改动清单

| 文件 | 改动 |
|------|------|
| `src/spec_vc/hooks.py` | 增强 5 处错误消息，每处加"下一步"指引 + SKILL.md 引用 |
| `src/spec_vc/cli.py` | 增强 `cmd_commit_prepare` 输出；增强 `cmd_change_validate` pre 阶段检查；`cmd_spec_new` 使用 ADR 编号作为 Spec 编号 |
| `src/spec_vc/spec.py` | 修改 `cmd_spec_new` 调用逻辑，当有 --adr 时用 ADR 编号而非 next_spec_id |
| `src/spec_vc/change.py` | 新增 `has_associated_spec()` 辅助函数 |
| `src/spec_vc/adr.py` | 新增 `check_adr_continuity()` 检查编号空洞 |
| `tests/python/test_cli.py` | 更新断言匹配新消息格式；新增门禁指引测试 |
| `tests/python/test_spec.py` | 新增 Spec 编号对齐测试 |

## 测试设计

### Spec 编号对齐

- `test_spec_new_uses_adr_id_for_spec_id`: `spec new --adr ADR-012` 创建 Spec-012 目录
- `test_spec_new_auto_increment_without_adr`: 不带 --adr 时仍自动递增
- `test_spec_new_rejects_duplicate_spec_id`: 如果 Spec-012 已存在，报错

### ADR 编号连续性

- `test_adr_new_warns_on_gap`: 存在 000-010 但缺 005 时，`adr new` 输出警告但仍然创建 011

### 门禁消息增强

- `test_hook_blocks_without_subagent_session`: 断言消息含 "Agent 工具" + "SKILL.md"
- `test_hook_blocks_adr_with_plan_stage_below_implement_ready`: 断言消息含 "change validate" + "SKILL.md"

### change validate --phase pre 增强

- `test_change_validate_pre_blocks_on_incomplete_clarify`: clarify 未完成时阻塞
- `test_change_validate_pre_warns_missing_spec_for_code_paths`: ADR 无对应 Spec 时提示

## 不做的事

- 不做 PreToolUse hook（靠错误消息指引 + SKILL.md 行为约束）
- 不改变 SKILL.md 的流程描述
- 不改变 `_active.md` 的结构