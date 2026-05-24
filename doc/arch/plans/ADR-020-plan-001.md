# ADR-020 执行方案 001

- **ADR**: ADR-020
- **ADR Title**: spec-vc 做减法：删除 reasoning scaffolding，保留 operational harness
- **Stage**: close
- **Created At**: 2026-05-24T16:05:15
- **Summary**: spec-vc 做减法：commit-msg hook 校验链从 6 步压到 4 步（删 plan stage / simple note anchor / [ADR-none] 量化 / require_user_verified），删除 lightweight.py，相应删除测试；新增 ADR 写作规范硬约束到 CLAUDE.md（自包含可读 / file:line 锚点 / 禁宣示句式）；保留 BYPASS audit / ADR 引用 / Spec 完整性 / review.json anchor+mtime / BlockingError / review 助手报告

## Clarification

- 动机与上下文: 详细动机见 doc/arch/adr-020.md Context 段。核心：spec-vc 当前 19 条 ADR 偏离初心（语义对齐），多数机制为'逼 AI 走流程'而非'让 AI 容易消费语义'。业界证据（VILA-Lab arXiv 2604.14228v1: Claude Code 98.4% 是 operational harness / 1.6% 是 AI 决策逻辑；Anthropic Building Effective Agents: 'simple, composable patterns'；Anthropic Claude 4.x guide: 'remove scaffolding that forces interim status messages'）支持判别法：operational harness 留 / reasoning scaffolding 删。本 ADR 实施减法。
- 目标与边界: 做：(1) hooks.py 删 _check_plan_stage + _check_lightweight；run_commit_msg 中 [ADR-NNN] 移除 plan stage 调用、[ADR-none] 仅 BYPASS audit；_check_review_record 删除 simple 模式 note anchor 校验 + require_user_verified 升级开关；(2) 删除 src/spec_vc/lightweight.py 整个文件；(3) config.py 删除 LightweightConfig.require_user_verified（其他 lightweight.* 字段一并删除——已无消费者）；(4) review.py cmd_review 删 simple 模式 note 含 anchor 阻塞分支；(5) 删除 ~15 项被影响的测试（lightweight 量化 5 项 + plan stage 相关 + simple note anchor + require_user_verified）；(6) CLAUDE.md 新增 ADR 写作规范段（自包含可读 / file:line 锚点 / 禁宣示句式 / 哲学讨论 ≤ 1 段 / 行为假设需数据支撑）；(7) SKILL.md commit 流程小节同步 4 步 hook 校验链描述。不做：删除 BYPASS audit / ADR 引用校验 / Spec 完整性校验 / review.json anchor+mtime 校验（这些是 operational harness 必留）；不删除 lightweight.py 历史在 git 中（git revert 即可回滚）；不动 ADR/Spec 创作协议；不动 review 助手报告（ADR-019）；不动 BlockingError 结构。
- 设计与架构: 减法后 commit-msg hook 校验链 4 步（hooks.py:run_commit_msg）：(1) SPEC_VC_BYPASS 非空 → 写 bypass log → 跳到 ADR 引用；(2) ADR 引用格式校验（[ADR-NNN] / [ADR-none] / [ADR-???]）；(3) [ADR-NNN] → Spec 完整性 + review.json (anchor 匹配 + mtime 新鲜)（删除 plan stage / simple note anchor / require_user_verified 三项）；(4) [ADR-none] → 直接放行（删除 lightweight 量化判定）。simple 模式仍保留为 review 子命令的参数，cmd_review 删除 note anchor 强制校验但保留 --note 参数作记录。config.py LightweightConfig 整体删除（dataclass + load_config 中加载逻辑），review_assistance 配置保留。CLAUDE.md ADR 写作规范段：'## ADR 写作规范（ADR-020）' 标题下列 5 条硬约束，引用 ADR-020 作为依据。SKILL.md '#### 6b' commit-msg hook 校验链小节改写为 4 步描述。
- 实现路径: 1. src/spec_vc/hooks.py: 删除 _check_plan_stage / _check_lightweight 函数；run_commit_msg [ADR-NNN] 分支移除 _check_plan_stage 调用；[ADR-none] 分支移除 _check_lightweight 调用；_check_review_record 移除 simple 模式 note 含 anchor 检查 + require_user_verified 检查；移除 IMPLEMENT_READY_OR_LATER / PLAN_DIR_NAME / ACTIVE_FILE_NAME 等 plan stage 相关常量与 _load_stage_for_adr 函数；2. src/spec_vc/lightweight.py: rm 整个文件；3. src/spec_vc/config.py: 删除 LightweightConfig dataclass + Config.lightweight 字段 + load_config 中加载 [lightweight] 段的代码；4. src/spec_vc/review.py: cmd_review 中 simple 模式分支删除 note 含 anchor 校验；5. tests/python/: 删除 test_lightweight_* 5 项 / test_freshness_passes_when_review_newer / test_freshness_blocks / test_freshness_skips（plan stage 间接相关）/ test_review_simple_mode_note_must_contain_anchor / test_require_user_verified_blocks_when_verified_false / test_commit_msg_rejects_adr_none_for_code_change（[ADR-none] 量化）等 ~15 项；保留 test_hook_accepts_review_json_with_context_summary / test_hook_accepts_legacy_review_json_without_context_summary / test_blocking_error_output_contains_four_sections 等核心 operational harness 测试；6. CLAUDE.md: 在 '## 关键设计约定' 后新增 '## ADR 写作规范' 段；7. SKILL.md: 6b 段 commit-msg hook 校验链改写为 4 步；8. cp 新代码到 ~/.claude/skills/spec-vc/src/spec_vc/；9. 自举：本 ADR-020 自身 commit 走 simple 模式 + --verified，note 不含 anchor 应正常通过（碰巧验证 simple anchor 校验已删）；10. 移除 _load_stage_for_adr 测试（IMPLEMENT_READY 边界相关）。
- 验证与测试: 回归：现有 139 测试减去 ~15 项被减法影响的（应剩 ~120-125 测试），全过。新增 0 项测试（减法本质是降低复杂度，不增加新行为分支）。端到端自举：本 ADR-020 自身 commit 走 simple 模式 + --note '审查完毕'（不含 anchor）+ --verified，应通过新 4 步 hook 校验链 + bypass log 无新增。预期 ADR 写作规范的生效验证：本 ADR-020 自身的 plan summary 含具体 file:line（hooks.py 函数名 / 配置字段名），不含 'sticks/carrots' 'X 取代 Y' 'senior dev workflow' 'XXX 设计哲学转向 YYY' 等宣示句式（本字段自身就是范例）。spec-vc spec check 应通过（Spec-020 dev-doc 6 必查区块填齐）。
- 风险与回滚: 全部为删除 + 配置项移除 + 文档新增，无新增功能逻辑，回滚路径清晰：(1) git revert ADR-020 整链 commit 即恢复 plan stage 校验 / lightweight.py / simple note anchor / require_user_verified；(2) 旧测试在 git 历史中可一并 revert；(3) CLAUDE.md ADR 写作规范是新增段，回滚就是删段；(4) review.json schema 不变（context_summary / verified 字段保持），向后兼容；(5) SPEC_VC_BYPASS 逃生口语义保持不变；(6) 若 30 天内观察到 AI 大量 [ADR-none] 误用或 simple 模式滥用：先记录到 bypass log 或 git log 分析作为 ADR-021 输入，不直接回滚——本 ADR 的'信任 AI 判断'就预期会有边界探索期。


## Clarification History

- 动机与上下文: 详细动机见 doc/arch/adr-020.md Context 段。核心：spec-vc 当前 19 条 ADR 偏离初心（语义对齐），多数机制为'逼 AI 走流程'而非'让 AI 容易消费语义'。业界证据（VILA-Lab arXiv 2604.14228v1: Claude Code 98.4% 是 operational harness / 1.6% 是 AI 决策逻辑；Anthropic Building Effective Agents: 'simple, composable patterns'；Anthropic Claude 4.x guide: 'remove scaffolding that forces interim status messages'）支持判别法：operational harness 留 / reasoning scaffolding 删。本 ADR 实施减法。
- 目标与边界: 做：(1) hooks.py 删 _check_plan_stage + _check_lightweight；run_commit_msg 中 [ADR-NNN] 移除 plan stage 调用、[ADR-none] 仅 BYPASS audit；_check_review_record 删除 simple 模式 note anchor 校验 + require_user_verified 升级开关；(2) 删除 src/spec_vc/lightweight.py 整个文件；(3) config.py 删除 LightweightConfig.require_user_verified（其他 lightweight.* 字段一并删除——已无消费者）；(4) review.py cmd_review 删 simple 模式 note 含 anchor 阻塞分支；(5) 删除 ~15 项被影响的测试（lightweight 量化 5 项 + plan stage 相关 + simple note anchor + require_user_verified）；(6) CLAUDE.md 新增 ADR 写作规范段（自包含可读 / file:line 锚点 / 禁宣示句式 / 哲学讨论 ≤ 1 段 / 行为假设需数据支撑）；(7) SKILL.md commit 流程小节同步 4 步 hook 校验链描述。不做：删除 BYPASS audit / ADR 引用校验 / Spec 完整性校验 / review.json anchor+mtime 校验（这些是 operational harness 必留）；不删除 lightweight.py 历史在 git 中（git revert 即可回滚）；不动 ADR/Spec 创作协议；不动 review 助手报告（ADR-019）；不动 BlockingError 结构。
- 设计与架构: 减法后 commit-msg hook 校验链 4 步（hooks.py:run_commit_msg）：(1) SPEC_VC_BYPASS 非空 → 写 bypass log → 跳到 ADR 引用；(2) ADR 引用格式校验（[ADR-NNN] / [ADR-none] / [ADR-???]）；(3) [ADR-NNN] → Spec 完整性 + review.json (anchor 匹配 + mtime 新鲜)（删除 plan stage / simple note anchor / require_user_verified 三项）；(4) [ADR-none] → 直接放行（删除 lightweight 量化判定）。simple 模式仍保留为 review 子命令的参数，cmd_review 删除 note anchor 强制校验但保留 --note 参数作记录。config.py LightweightConfig 整体删除（dataclass + load_config 中加载逻辑），review_assistance 配置保留。CLAUDE.md ADR 写作规范段：'## ADR 写作规范（ADR-020）' 标题下列 5 条硬约束，引用 ADR-020 作为依据。SKILL.md '#### 6b' commit-msg hook 校验链小节改写为 4 步描述。
- 实现路径: 1. src/spec_vc/hooks.py: 删除 _check_plan_stage / _check_lightweight 函数；run_commit_msg [ADR-NNN] 分支移除 _check_plan_stage 调用；[ADR-none] 分支移除 _check_lightweight 调用；_check_review_record 移除 simple 模式 note 含 anchor 检查 + require_user_verified 检查；移除 IMPLEMENT_READY_OR_LATER / PLAN_DIR_NAME / ACTIVE_FILE_NAME 等 plan stage 相关常量与 _load_stage_for_adr 函数；2. src/spec_vc/lightweight.py: rm 整个文件；3. src/spec_vc/config.py: 删除 LightweightConfig dataclass + Config.lightweight 字段 + load_config 中加载 [lightweight] 段的代码；4. src/spec_vc/review.py: cmd_review 中 simple 模式分支删除 note 含 anchor 校验；5. tests/python/: 删除 test_lightweight_* 5 项 / test_freshness_passes_when_review_newer / test_freshness_blocks / test_freshness_skips（plan stage 间接相关）/ test_review_simple_mode_note_must_contain_anchor / test_require_user_verified_blocks_when_verified_false / test_commit_msg_rejects_adr_none_for_code_change（[ADR-none] 量化）等 ~15 项；保留 test_hook_accepts_review_json_with_context_summary / test_hook_accepts_legacy_review_json_without_context_summary / test_blocking_error_output_contains_four_sections 等核心 operational harness 测试；6. CLAUDE.md: 在 '## 关键设计约定' 后新增 '## ADR 写作规范' 段；7. SKILL.md: 6b 段 commit-msg hook 校验链改写为 4 步；8. cp 新代码到 ~/.claude/skills/spec-vc/src/spec_vc/；9. 自举：本 ADR-020 自身 commit 走 simple 模式 + --verified，note 不含 anchor 应正常通过（碰巧验证 simple anchor 校验已删）；10. 移除 _load_stage_for_adr 测试（IMPLEMENT_READY 边界相关）。
- 验证与测试: 回归：现有 139 测试减去 ~15 项被减法影响的（应剩 ~120-125 测试），全过。新增 0 项测试（减法本质是降低复杂度，不增加新行为分支）。端到端自举：本 ADR-020 自身 commit 走 simple 模式 + --note '审查完毕'（不含 anchor）+ --verified，应通过新 4 步 hook 校验链 + bypass log 无新增。预期 ADR 写作规范的生效验证：本 ADR-020 自身的 plan summary 含具体 file:line（hooks.py 函数名 / 配置字段名），不含 'sticks/carrots' 'X 取代 Y' 'senior dev workflow' 'XXX 设计哲学转向 YYY' 等宣示句式（本字段自身就是范例）。spec-vc spec check 应通过（Spec-020 dev-doc 6 必查区块填齐）。
- 风险与回滚: 全部为删除 + 配置项移除 + 文档新增，无新增功能逻辑，回滚路径清晰：(1) git revert ADR-020 整链 commit 即恢复 plan stage 校验 / lightweight.py / simple note anchor / require_user_verified；(2) 旧测试在 git 历史中可一并 revert；(3) CLAUDE.md ADR 写作规范是新增段，回滚就是删段；(4) review.json schema 不变（context_summary / verified 字段保持），向后兼容；(5) SPEC_VC_BYPASS 逃生口语义保持不变；(6) 若 30 天内观察到 AI 大量 [ADR-none] 误用或 simple 模式滥用：先记录到 bypass log 或 git log 分析作为 ADR-021 输入，不直接回滚——本 ADR 的'信任 AI 判断'就预期会有边界探索期。


## Motivation and Context

详细动机见 doc/arch/adr-020.md Context 段。核心：spec-vc 当前 19 条 ADR 偏离初心（语义对齐），多数机制为'逼 AI 走流程'而非'让 AI 容易消费语义'。业界证据（VILA-Lab arXiv 2604.14228v1: Claude Code 98.4% 是 operational harness / 1.6% 是 AI 决策逻辑；Anthropic Building Effective Agents: 'simple, composable patterns'；Anthropic Claude 4.x guide: 'remove scaffolding that forces interim status messages'）支持判别法：operational harness 留 / reasoning scaffolding 删。本 ADR 实施减法。


## Goals and Boundaries

做：(1) hooks.py 删 _check_plan_stage + _check_lightweight；run_commit_msg 中 [ADR-NNN] 移除 plan stage 调用、[ADR-none] 仅 BYPASS audit；_check_review_record 删除 simple 模式 note anchor 校验 + require_user_verified 升级开关；(2) 删除 src/spec_vc/lightweight.py 整个文件；(3) config.py 删除 LightweightConfig.require_user_verified（其他 lightweight.* 字段一并删除——已无消费者）；(4) review.py cmd_review 删 simple 模式 note 含 anchor 阻塞分支；(5) 删除 ~15 项被影响的测试（lightweight 量化 5 项 + plan stage 相关 + simple note anchor + require_user_verified）；(6) CLAUDE.md 新增 ADR 写作规范段（自包含可读 / file:line 锚点 / 禁宣示句式 / 哲学讨论 ≤ 1 段 / 行为假设需数据支撑）；(7) SKILL.md commit 流程小节同步 4 步 hook 校验链描述。不做：删除 BYPASS audit / ADR 引用校验 / Spec 完整性校验 / review.json anchor+mtime 校验（这些是 operational harness 必留）；不删除 lightweight.py 历史在 git 中（git revert 即可回滚）；不动 ADR/Spec 创作协议；不动 review 助手报告（ADR-019）；不动 BlockingError 结构。


## Design and Architecture

减法后 commit-msg hook 校验链 4 步（hooks.py:run_commit_msg）：(1) SPEC_VC_BYPASS 非空 → 写 bypass log → 跳到 ADR 引用；(2) ADR 引用格式校验（[ADR-NNN] / [ADR-none] / [ADR-???]）；(3) [ADR-NNN] → Spec 完整性 + review.json (anchor 匹配 + mtime 新鲜)（删除 plan stage / simple note anchor / require_user_verified 三项）；(4) [ADR-none] → 直接放行（删除 lightweight 量化判定）。simple 模式仍保留为 review 子命令的参数，cmd_review 删除 note anchor 强制校验但保留 --note 参数作记录。config.py LightweightConfig 整体删除（dataclass + load_config 中加载逻辑），review_assistance 配置保留。CLAUDE.md ADR 写作规范段：'## ADR 写作规范（ADR-020）' 标题下列 5 条硬约束，引用 ADR-020 作为依据。SKILL.md '#### 6b' commit-msg hook 校验链小节改写为 4 步描述。


## Implementation Path

1. src/spec_vc/hooks.py: 删除 _check_plan_stage / _check_lightweight 函数；run_commit_msg [ADR-NNN] 分支移除 _check_plan_stage 调用；[ADR-none] 分支移除 _check_lightweight 调用；_check_review_record 移除 simple 模式 note 含 anchor 检查 + require_user_verified 检查；移除 IMPLEMENT_READY_OR_LATER / PLAN_DIR_NAME / ACTIVE_FILE_NAME 等 plan stage 相关常量与 _load_stage_for_adr 函数；2. src/spec_vc/lightweight.py: rm 整个文件；3. src/spec_vc/config.py: 删除 LightweightConfig dataclass + Config.lightweight 字段 + load_config 中加载 [lightweight] 段的代码；4. src/spec_vc/review.py: cmd_review 中 simple 模式分支删除 note 含 anchor 校验；5. tests/python/: 删除 test_lightweight_* 5 项 / test_freshness_passes_when_review_newer / test_freshness_blocks / test_freshness_skips（plan stage 间接相关）/ test_review_simple_mode_note_must_contain_anchor / test_require_user_verified_blocks_when_verified_false / test_commit_msg_rejects_adr_none_for_code_change（[ADR-none] 量化）等 ~15 项；保留 test_hook_accepts_review_json_with_context_summary / test_hook_accepts_legacy_review_json_without_context_summary / test_blocking_error_output_contains_four_sections 等核心 operational harness 测试；6. CLAUDE.md: 在 '## 关键设计约定' 后新增 '## ADR 写作规范' 段；7. SKILL.md: 6b 段 commit-msg hook 校验链改写为 4 步；8. cp 新代码到 ~/.claude/skills/spec-vc/src/spec_vc/；9. 自举：本 ADR-020 自身 commit 走 simple 模式 + --verified，note 不含 anchor 应正常通过（碰巧验证 simple anchor 校验已删）；10. 移除 _load_stage_for_adr 测试（IMPLEMENT_READY 边界相关）。


## Verification and Testing

回归：现有 139 测试减去 ~15 项被减法影响的（应剩 ~120-125 测试），全过。新增 0 项测试（减法本质是降低复杂度，不增加新行为分支）。端到端自举：本 ADR-020 自身 commit 走 simple 模式 + --note '审查完毕'（不含 anchor）+ --verified，应通过新 4 步 hook 校验链 + bypass log 无新增。预期 ADR 写作规范的生效验证：本 ADR-020 自身的 plan summary 含具体 file:line（hooks.py 函数名 / 配置字段名），不含 'sticks/carrots' 'X 取代 Y' 'senior dev workflow' 'XXX 设计哲学转向 YYY' 等宣示句式（本字段自身就是范例）。spec-vc spec check 应通过（Spec-020 dev-doc 6 必查区块填齐）。


## Risks and Rollback

全部为删除 + 配置项移除 + 文档新增，无新增功能逻辑，回滚路径清晰：(1) git revert ADR-020 整链 commit 即恢复 plan stage 校验 / lightweight.py / simple note anchor / require_user_verified；(2) 旧测试在 git 历史中可一并 revert；(3) CLAUDE.md ADR 写作规范是新增段，回滚就是删段；(4) review.json schema 不变（context_summary / verified 字段保持），向后兼容；(5) SPEC_VC_BYPASS 逃生口语义保持不变；(6) 若 30 天内观察到 AI 大量 [ADR-none] 误用或 simple 模式滥用：先记录到 bypass log 或 git log 分析作为 ADR-021 输入，不直接回滚——本 ADR 的'信任 AI 判断'就预期会有边界探索期。


## Affected Areas

待补充

## Pre-Change Validation

Spec 创作协议完成：Spec-020 dev-doc 6 必查区块全填 + 3 形式化文件生成 + spec check 10/10 全过。baseline pytest 139/139 全过。设计理念已固化（详见 doc/arch/adr-020.md Context 段）：判别法 = operational harness 留 / reasoning scaffolding 删，依据 VILA-Lab arXiv 2604.14228v1 (Claude Code 98.4%/1.6%) + Anthropic Building Effective Agents + Claude 4.x prompt engineering guide。覆盖盲区：hooks.py 当前含 _check_plan_stage (line ~73) + _check_lightweight (line ~330+) + _load_stage_for_adr (line ~32) + _check_review_record 内 simple 模式 note anchor 校验 + require_user_verified 分支；lightweight.py 整个文件 76 行待删；config.py LightweightConfig dataclass + Config.lightweight 字段 + load_config 中 6 行 [lightweight] 加载逻辑待删；review.py cmd_review 内 simple 模式 note 阻塞分支 (cli.py ~514-535) 待删；测试套 ~15 项待删；CLAUDE.md 待新增 ADR 写作规范段。


## Post-Change Validation

代码 + 测试 + 文档全部实施完成。变更总结：(1) src/spec_vc/hooks.py 删除 _check_plan_stage / _load_stage_for_adr / _check_lightweight 函数 + ACTIVE_FILE_NAME / PLAN_DIR_NAME / IMPLEMENT_READY_OR_LATER 常量；删除 _check_review_record 中 simple 模式 note 含 anchor 校验 + require_user_verified 升级开关；删除 from .lightweight import detect_lightweight_change；run_commit_msg 中 [ADR-NNN] 分支移除 _check_plan_stage 调用，[ADR-none] 分支移除 _check_lightweight 调用直接 return 0。(2) 删除 src/spec_vc/lightweight.py 整个文件。(3) src/spec_vc/config.py 删除 LightweightConfig dataclass + Config.lightweight 字段 + load_config 中 6 行加载 [lightweight] 配置段的代码。(4) src/spec_vc/cli.py:cmd_review 删除 simple 模式 --note 必填校验 + --note 含 anchor 子串校验。(5) tests/python/test_cli.py 删除 14 项 reasoning scaffolding 测试（test_commit_msg_rejects_adr_none_for_code_change / test_hook_blocks_adr_with_plan_stage_below_implement_ready / test_load_stage_for_adr_* 4 项 / test_lightweight_* 5 项 / test_review_simple_mode_requires_note / test_review_simple_mode_note_must_contain_anchor / test_require_user_verified_blocks_when_verified_false）。(6) CLAUDE.md 新增 '## ADR 写作规范（ADR-020 硬约束）' 段含 5 条规范 + 修订'提交流程'小节描述 4 步 hook 校验链。(7) SKILL.md 6b 段重写为 4 步校验链（删除原第 3 步 plan stage / 第 4 步 simple note anchor + verified 子句 / 第 5 步量化判定），SPEC_VC_BYPASS 描述同步。回归测试：pytest 139→125 全过（净删 14 项，无新增）；删除的全部是测试被减法移除的 reasoning scaffolding 机制本身。代码已 cp 到 ~/.claude/skills/spec-vc/src/spec_vc/（hooks.py + config.py + cli.py），lightweight.py 也已从 skill venv 删除。集成验证将由本 ADR-020 自身 commit 完成——本 ADR 计划走 simple 模式 + --note '审查完毕'（故意不含 anchor）+ --verified（既验证 simple anchor 校验已删，又验证 verified 字段只作记录不阻塞）。


## Closure Summary

spec-vc 做减法：按 VILA-Lab 判别法删除 reasoning scaffolding，保留 operational harness。删除：hooks.py:_check_plan_stage / _check_lightweight / _load_stage_for_adr 函数 + ACTIVE_FILE_NAME / PLAN_DIR_NAME / IMPLEMENT_READY_OR_LATER 常量；_check_review_record 中 simple 模式 note 含 anchor 校验 + require_user_verified 升级开关；lightweight.py 整个文件；config.py:LightweightConfig dataclass + load_config [lightweight] 段；cli.py:cmd_review simple 模式 --note 必填 + anchor 子串校验；14 项测试。保留：BYPASS audit / ADR 引用 / Spec 完整性 / review.json (anchor + mtime) / BlockingError / ADR-019 review 助手报告。CLAUDE.md 新增 ADR 写作规范段（5 条硬约束：自包含可读 / file:line 锚点 / 禁宣示句式 / 哲学 ≤ 1 段 / 行为假设需数据支撑），引用 doc/arch/adr-020.md 为依据。SKILL.md 6b 段重写为 4 步校验链。测试 139→125（净删 14 项，无新增）。设计理念依据：VILA-Lab arXiv 2604.14228v1 (Claude Code 98.4%/1.6%) + Anthropic Building Effective Agents + Claude 4.x prompt engineering guide + Cognition Don't Build Multi-Agents（详见 doc/arch/adr-020.md Context 段与 References 段）。自举端到端：commit 62ee2c5 走 simple 模式 + --note 不含 anchor（验证旧 sticks 已删）+ --verified（验证仅作记录不阻塞），4 步 hook 全过，.git/spec-vc-bypass.log 无新增条目。本 ADR partial supersede ADR-011 (plan stage) / ADR-018 (量化判定 / require_user_verified / simple note anchor)；affirm ADR-019 (review 助手 = environment design 核心) / ADR-012 (错误可执行 = 降低 AI 消费成本)。


## References

- **Commits**: 待从 git 自动采集
- **Plan**: doc/arch/plans/ADR-020-plan-001.md


## Checkpoints

- [ ] 澄清完成
- [ ] 前置验证完成
- [ ] 实施完成
- [ ] 后置验证完成
- [ ] ADR 回填完成
