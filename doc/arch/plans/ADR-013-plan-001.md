# ADR-013 执行方案 001

- **ADR**: ADR-013
- **ADR Title**: hook 校验链补完：adr_id 路由与 session log 时间戳新鲜度
- **Stage**: validate
- **Created At**: 2026-05-08T14:00:57
- **Summary**: hook 校验链补完：_load_active_stage 按 adr_id 路由 + commit-msg hook 增加 session log 时间戳新鲜度 + PostToolUse 空 description 跳过

## Clarification

- 动机与上下文: ADR-011/012 收尾暴露两个 hook 校验链补完点：(1) hooks._load_active_stage(adr_dir, adr_id) 函数体未使用 adr_id，永远读 _active.md 的 stage——commit 引用 [ADR-X] 而 active 是 ADR-Y 时校验对象错位。当前因单 active change 约束未爆发，但是隐性 bug，未来扩展（追加 commit、并行 ADR）时会失效。(2) PostToolUse hook 仅以 session log 非空作审计证据，今天 Agent API 500 失败时 hook 仍写空 description 行（5 行中 3 行空 description），commit-msg hook 形式上仍通过——回到 ADR-008/011 想堵的仪式性问题。两点都属于 ADR-011/012 设计意图的漏检，不是新功能。
- 目标与边界: 修两点：(1) _load_active_stage 按 adr_id 真实查 stage（active 优先，fallback 到 plans/ADR-{adr_id}-plan-*.md 取编号最大）；(2) commit-msg hook 增加 session log 末行时间戳晚于 commit-msg 写入时间检查，证明审计是本次提交而非历史；(3) PostToolUse hook 空 description 跳过写日志。不做：不引入并行 active change；不做 description 内容质量校验；不改其他校验项语义。
- 设计与架构: hooks._load_active_stage 重写为 _load_stage_for_adr(adr_dir, adr_id)：active 匹配则用 active.stage，不匹配则从 plans/ADR-{adr_id}-plan-*.md 取编号最大的读 - **Stage**: 字段，无 plan 文件返回 None（流程已结束不阻塞）。commit.py 新增 check_session_log_freshness(repo_root)：比较 .git/spec-vc-commit-msg mtime 与 session log 末行时间戳，要求末行 > commit-msg mtime；commit-msg 不存在跳过（保留旁路）。run_commit_msg 在 check_subagent_session 之后追加 freshness 调用。run_post_tool_use 当 description 为空时不写日志。SKILL.md 同步描述。
- 实现路径: 1. 先写测试：(a) _load_stage_for_adr 三场景：active 匹配 / active 不匹配但目标 ADR 有 plan / 无 plan；(b) freshness 三场景：log 末行新鲜 / 老旧 / 无 commit-msg；(c) PostToolUse 空 description 不写。2. 改代码：commit.py 新增 freshness 函数；hooks.py 重写 _load_active_stage 为 _load_stage_for_adr，调整调用点；run_post_tool_use 加空判断。3. cmd_commit_prepare 输出 4 项校验描述微调：session log 改为非空且时间戳新鲜。4. SKILL.md 同步。5. pytest 全过 + 新增 6 测试不回退。
- 验证与测试: 新增约 6 个测试覆盖三组场景：_load_stage_for_adr active 匹配 / active 不匹配 fallback / 无 plan；freshness 新鲜放行 / 陈旧阻塞 / 无 commit-msg 跳过；PostToolUse 空 description 不写。手工：模拟 Agent 调用失败（空 description）+ git commit → 验证被 freshness 阻塞；模拟 active 是 ADR-X 但 commit 引用 ADR-Y → 验证查 ADR-Y plan 而非 active。pytest 78+6=84 测试全过。
- 风险与回滚: 风险：(a) freshness 检查可能误伤 prepare 后等待数小时再 commit 但中途无新 Agent 调用的场景——但这种情况说明审计陈旧，阻塞合理，用户可用 SPEC_VC_BYPASS 旁路；(b) plan 文件 stage 字段与 active.md 可能不一致——已有 update_active_stage 同步两边，无新风险。回滚：单 commit 内的两件事同进同退，git revert 即可。改动集中在 hooks.py / commit.py / 测试，回退范围明确。


## Clarification History

- 动机与上下文: ADR-011/012 收尾暴露两个 hook 校验链补完点：(1) hooks._load_active_stage(adr_dir, adr_id) 函数体未使用 adr_id，永远读 _active.md 的 stage——commit 引用 [ADR-X] 而 active 是 ADR-Y 时校验对象错位。当前因单 active change 约束未爆发，但是隐性 bug，未来扩展（追加 commit、并行 ADR）时会失效。(2) PostToolUse hook 仅以 session log 非空作审计证据，今天 Agent API 500 失败时 hook 仍写空 description 行（5 行中 3 行空 description），commit-msg hook 形式上仍通过——回到 ADR-008/011 想堵的仪式性问题。两点都属于 ADR-011/012 设计意图的漏检，不是新功能。
- 目标与边界: 修两点：(1) _load_active_stage 按 adr_id 真实查 stage（active 优先，fallback 到 plans/ADR-{adr_id}-plan-*.md 取编号最大）；(2) commit-msg hook 增加 session log 末行时间戳晚于 commit-msg 写入时间检查，证明审计是本次提交而非历史；(3) PostToolUse hook 空 description 跳过写日志。不做：不引入并行 active change；不做 description 内容质量校验；不改其他校验项语义。
- 设计与架构: hooks._load_active_stage 重写为 _load_stage_for_adr(adr_dir, adr_id)：active 匹配则用 active.stage，不匹配则从 plans/ADR-{adr_id}-plan-*.md 取编号最大的读 - **Stage**: 字段，无 plan 文件返回 None（流程已结束不阻塞）。commit.py 新增 check_session_log_freshness(repo_root)：比较 .git/spec-vc-commit-msg mtime 与 session log 末行时间戳，要求末行 > commit-msg mtime；commit-msg 不存在跳过（保留旁路）。run_commit_msg 在 check_subagent_session 之后追加 freshness 调用。run_post_tool_use 当 description 为空时不写日志。SKILL.md 同步描述。
- 实现路径: 1. 先写测试：(a) _load_stage_for_adr 三场景：active 匹配 / active 不匹配但目标 ADR 有 plan / 无 plan；(b) freshness 三场景：log 末行新鲜 / 老旧 / 无 commit-msg；(c) PostToolUse 空 description 不写。2. 改代码：commit.py 新增 freshness 函数；hooks.py 重写 _load_active_stage 为 _load_stage_for_adr，调整调用点；run_post_tool_use 加空判断。3. cmd_commit_prepare 输出 4 项校验描述微调：session log 改为非空且时间戳新鲜。4. SKILL.md 同步。5. pytest 全过 + 新增 6 测试不回退。
- 验证与测试: 新增约 6 个测试覆盖三组场景：_load_stage_for_adr active 匹配 / active 不匹配 fallback / 无 plan；freshness 新鲜放行 / 陈旧阻塞 / 无 commit-msg 跳过；PostToolUse 空 description 不写。手工：模拟 Agent 调用失败（空 description）+ git commit → 验证被 freshness 阻塞；模拟 active 是 ADR-X 但 commit 引用 ADR-Y → 验证查 ADR-Y plan 而非 active。pytest 78+6=84 测试全过。
- 风险与回滚: 风险：(a) freshness 检查可能误伤 prepare 后等待数小时再 commit 但中途无新 Agent 调用的场景——但这种情况说明审计陈旧，阻塞合理，用户可用 SPEC_VC_BYPASS 旁路；(b) plan 文件 stage 字段与 active.md 可能不一致——已有 update_active_stage 同步两边，无新风险。回滚：单 commit 内的两件事同进同退，git revert 即可。改动集中在 hooks.py / commit.py / 测试，回退范围明确。


## Motivation and Context

ADR-011/012 收尾暴露两个 hook 校验链补完点：(1) hooks._load_active_stage(adr_dir, adr_id) 函数体未使用 adr_id，永远读 _active.md 的 stage——commit 引用 [ADR-X] 而 active 是 ADR-Y 时校验对象错位。当前因单 active change 约束未爆发，但是隐性 bug，未来扩展（追加 commit、并行 ADR）时会失效。(2) PostToolUse hook 仅以 session log 非空作审计证据，今天 Agent API 500 失败时 hook 仍写空 description 行（5 行中 3 行空 description），commit-msg hook 形式上仍通过——回到 ADR-008/011 想堵的仪式性问题。两点都属于 ADR-011/012 设计意图的漏检，不是新功能。


## Goals and Boundaries

修两点：(1) _load_active_stage 按 adr_id 真实查 stage（active 优先，fallback 到 plans/ADR-{adr_id}-plan-*.md 取编号最大）；(2) commit-msg hook 增加 session log 末行时间戳晚于 commit-msg 写入时间检查，证明审计是本次提交而非历史；(3) PostToolUse hook 空 description 跳过写日志。不做：不引入并行 active change；不做 description 内容质量校验；不改其他校验项语义。


## Design and Architecture

hooks._load_active_stage 重写为 _load_stage_for_adr(adr_dir, adr_id)：active 匹配则用 active.stage，不匹配则从 plans/ADR-{adr_id}-plan-*.md 取编号最大的读 - **Stage**: 字段，无 plan 文件返回 None（流程已结束不阻塞）。commit.py 新增 check_session_log_freshness(repo_root)：比较 .git/spec-vc-commit-msg mtime 与 session log 末行时间戳，要求末行 > commit-msg mtime；commit-msg 不存在跳过（保留旁路）。run_commit_msg 在 check_subagent_session 之后追加 freshness 调用。run_post_tool_use 当 description 为空时不写日志。SKILL.md 同步描述。


## Implementation Path

1. 先写测试：(a) _load_stage_for_adr 三场景：active 匹配 / active 不匹配但目标 ADR 有 plan / 无 plan；(b) freshness 三场景：log 末行新鲜 / 老旧 / 无 commit-msg；(c) PostToolUse 空 description 不写。2. 改代码：commit.py 新增 freshness 函数；hooks.py 重写 _load_active_stage 为 _load_stage_for_adr，调整调用点；run_post_tool_use 加空判断。3. cmd_commit_prepare 输出 4 项校验描述微调：session log 改为非空且时间戳新鲜。4. SKILL.md 同步。5. pytest 全过 + 新增 6 测试不回退。


## Verification and Testing

新增约 6 个测试覆盖三组场景：_load_stage_for_adr active 匹配 / active 不匹配 fallback / 无 plan；freshness 新鲜放行 / 陈旧阻塞 / 无 commit-msg 跳过；PostToolUse 空 description 不写。手工：模拟 Agent 调用失败（空 description）+ git commit → 验证被 freshness 阻塞；模拟 active 是 ADR-X 但 commit 引用 ADR-Y → 验证查 ADR-Y plan 而非 active。pytest 78+6=84 测试全过。


## Risks and Rollback

风险：(a) freshness 检查可能误伤 prepare 后等待数小时再 commit 但中途无新 Agent 调用的场景——但这种情况说明审计陈旧，阻塞合理，用户可用 SPEC_VC_BYPASS 旁路；(b) plan 文件 stage 字段与 active.md 可能不一致——已有 update_active_stage 同步两边，无新风险。回滚：单 commit 内的两件事同进同退，git revert 即可。改动集中在 hooks.py / commit.py / 测试，回退范围明确。


## Affected Areas

待补充

## Pre-Change Validation

Spec-013 已 formalize 全部就绪。代码改动清单：(1) hooks.py: _load_active_stage 重写为 _load_stage_for_adr(adr_dir, adr_id)，active 匹配用 active.stage、不匹配 fallback 到 plans/ADR-{adr_id}-plan-*.md 取编号最大、无 plan 返回 None；调整 _check_plan_stage 的调用。(2) commit.py: 新增 check_session_log_freshness(repo_root) 比较 commit-msg mtime 与 log 末行时间戳，commit-msg 不存在跳过；新增 SKILL.md 引用。(3) hooks.py run_commit_msg: 在 check_subagent_session 之后追加 freshness 调用；run_post_tool_use 当 description 为空时跳过写日志。(4) cli.py cmd_commit_prepare 输出微调：session log 项改为 '非空且时间戳新鲜'。(5) SKILL.md commit 协议描述同步加 freshness。改动集中在 hooks.py / commit.py / cli.py / SKILL.md / 测试。回滚：git revert 单 commit。


## Post-Change Validation

ADR-013 plan-001 全部 3 项实施完成。代码改动：(1) hooks.py: _load_active_stage 重写为 _load_stage_for_adr(adr_dir, adr_id)——active 匹配（同时校验 ADR 字段）则用 active.stage；不匹配 fallback 到 plans/ADR-{adr_id}-plan-*.md 取编号最大读 Stage 字段；无 plan 返回 None。_check_plan_stage 调用更新。run_post_tool_use 加 description 空判断（含 strip）。run_commit_msg 在 check_subagent_session 之后追加 check_session_log_freshness 调用。(2) commit.py: 新增 check_session_log_freshness——commit-msg 不存在则跳过；log 末行无法解析时间戳则 fail-open；时间戳 ≤ commit-msg mtime 则抛 FileNotFoundError 含可执行指引和 SKILL.md 引用。(3) cli.py cmd_commit_prepare 输出第 1 项改为 'session log 非空且时间戳新鲜'。(4) SKILL.md 同步：6c 节加描述、6b 校验链增 freshness 步骤、6e bypass 范围更新。测试：新增 10 个测试覆盖 _load_stage_for_adr 4 场景、freshness 4 场景、PostToolUse 空 description 2 场景。pytest 88/88 全过（之前 78）。pyright 仅遗留与本次改动无关的 cmd_change_start/cmd_skill_load 中 dict.get 返回 object 的类型推断警告。


## Closure Summary

待补充

## References

- **Commits**: 待补充
- **Plan**: 待补充

## Risks and Rollback

待补充

## Checkpoints

- [ ] 澄清完成
- [ ] 前置验证完成
- [ ] 实施完成
- [ ] 后置验证完成
- [ ] ADR 回填完成
