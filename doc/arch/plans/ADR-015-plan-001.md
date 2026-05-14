# ADR-015 执行方案 001

- **ADR**: ADR-015
- **ADR Title**: 修复 [ADR-none] 路径被 subagent session 检查误伤
- **Stage**: close
- **Created At**: 2026-05-14T19:45:33
- **Summary**: 修复 commit-msg hook 中 subagent session 检查位于 token 解析之前，导致 [ADR-none] 轻量路径被误伤

## Clarification

- 动机与上下文: ADR-013 新增的 session log 时间戳新鲜度检查位于 run_commit_msg 的 bypass 分支内、token 类型判断之前，对所有 commit 生效，导致 [ADR-none] 轻量路径（纯文档索引刷新等）被误阻塞。[ADR-none] 不需要 subagent 审计，不应受此检查约束。
- 目标与边界: 仅修改 hooks.py run_commit_msg 的校验顺序：将 check_subagent_session 和 check_session_log_freshness 从 bypass else 分支移到 [ADR-NNN] 分支内。补测试覆盖 [ADR-none] 路径在 session log 陈旧时仍能通过。不改其他文件，不改两个检查函数的内部逻辑。
- 设计与架构: run_commit_msg 当前结构：bypass? → session 检查 → token 解析 → [ADR-none] 豁免 / [ADR-NNN] 检查。修复后：bypass? → token 解析 → [ADR-none] 直接豁免返回 / [ADR-NNN] → session 检查 → plan stage → Spec 完整性。即把 session 检查从 token 无关位置移到 [ADR-NNN] 专属路径。
- 实现路径: 1. 修改 hooks.py:191-198——删除 check_subagent_session + check_session_log_freshness 调用。2. 在 hooks.py:225 行后（_check_plan_stage 调用前）插入相同的 session 检查逻辑。3. 在 tests/python/test_hooks.py 中新增测试：session log 存在但时间戳陈旧时，[ADR-none] commit 仍能通过。4. 运行全量测试确认无回归。
- 验证与测试: 1. 补测试用例：模拟 [ADR-none] commit，session log 存在但末行时间戳早于 commit-msg mtime，断言 hook 返回 0。2. 现有 [ADR-NNN] 测试继续通过（session 检查在正确位置仍然生效）。3. 手动验证：创建一个 [ADR-none] 的文档提交，确认不被阻塞。
- 风险与回滚: 极低风险，仅影响 [ADR-none] 路径的校验链。如果出现问题，git revert 本次 commit 即可恢复。不影响 [ADR-NNN] 正常流程。


## Clarification History

- 动机与上下文: ADR-013 新增的 session log 时间戳新鲜度检查位于 run_commit_msg 的 bypass 分支内、token 类型判断之前，对所有 commit 生效，导致 [ADR-none] 轻量路径（纯文档索引刷新等）被误阻塞。[ADR-none] 不需要 subagent 审计，不应受此检查约束。
- 目标与边界: 仅修改 hooks.py run_commit_msg 的校验顺序：将 check_subagent_session 和 check_session_log_freshness 从 bypass else 分支移到 [ADR-NNN] 分支内。补测试覆盖 [ADR-none] 路径在 session log 陈旧时仍能通过。不改其他文件，不改两个检查函数的内部逻辑。
- 设计与架构: run_commit_msg 当前结构：bypass? → session 检查 → token 解析 → [ADR-none] 豁免 / [ADR-NNN] 检查。修复后：bypass? → token 解析 → [ADR-none] 直接豁免返回 / [ADR-NNN] → session 检查 → plan stage → Spec 完整性。即把 session 检查从 token 无关位置移到 [ADR-NNN] 专属路径。
- 实现路径: 1. 修改 hooks.py:191-198——删除 check_subagent_session + check_session_log_freshness 调用。2. 在 hooks.py:225 行后（_check_plan_stage 调用前）插入相同的 session 检查逻辑。3. 在 tests/python/test_hooks.py 中新增测试：session log 存在但时间戳陈旧时，[ADR-none] commit 仍能通过。4. 运行全量测试确认无回归。
- 验证与测试: 1. 补测试用例：模拟 [ADR-none] commit，session log 存在但末行时间戳早于 commit-msg mtime，断言 hook 返回 0。2. 现有 [ADR-NNN] 测试继续通过（session 检查在正确位置仍然生效）。3. 手动验证：创建一个 [ADR-none] 的文档提交，确认不被阻塞。
- 风险与回滚: 极低风险，仅影响 [ADR-none] 路径的校验链。如果出现问题，git revert 本次 commit 即可恢复。不影响 [ADR-NNN] 正常流程。


## Motivation and Context

ADR-013 新增的 session log 时间戳新鲜度检查位于 run_commit_msg 的 bypass 分支内、token 类型判断之前，对所有 commit 生效，导致 [ADR-none] 轻量路径（纯文档索引刷新等）被误阻塞。[ADR-none] 不需要 subagent 审计，不应受此检查约束。


## Goals and Boundaries

仅修改 hooks.py run_commit_msg 的校验顺序：将 check_subagent_session 和 check_session_log_freshness 从 bypass else 分支移到 [ADR-NNN] 分支内。补测试覆盖 [ADR-none] 路径在 session log 陈旧时仍能通过。不改其他文件，不改两个检查函数的内部逻辑。


## Design and Architecture

run_commit_msg 当前结构：bypass? → session 检查 → token 解析 → [ADR-none] 豁免 / [ADR-NNN] 检查。修复后：bypass? → token 解析 → [ADR-none] 直接豁免返回 / [ADR-NNN] → session 检查 → plan stage → Spec 完整性。即把 session 检查从 token 无关位置移到 [ADR-NNN] 专属路径。


## Implementation Path

1. 修改 hooks.py:191-198——删除 check_subagent_session + check_session_log_freshness 调用。2. 在 hooks.py:225 行后（_check_plan_stage 调用前）插入相同的 session 检查逻辑。3. 在 tests/python/test_hooks.py 中新增测试：session log 存在但时间戳陈旧时，[ADR-none] commit 仍能通过。4. 运行全量测试确认无回归。


## Verification and Testing

1. 补测试用例：模拟 [ADR-none] commit，session log 存在但末行时间戳早于 commit-msg mtime，断言 hook 返回 0。2. 现有 [ADR-NNN] 测试继续通过（session 检查在正确位置仍然生效）。3. 手动验证：创建一个 [ADR-none] 的文档提交，确认不被阻塞。


## Risks and Rollback

极低风险，仅影响 [ADR-none] 路径的校验链。如果出现问题，git revert 本次 commit 即可恢复。不影响 [ADR-NNN] 正常流程。


## Affected Areas

待补充

## Pre-Change Validation

变更前验证：现有 12 个 hook 测试全部通过；bug 已通过代码审查确认——run_commit_msg:191-198 行 session 检查在 token 类型判断之前执行，[ADR-none] 无法豁免；修复方案：将 session 检查移到 [ADR-NNN] 分支内


## Post-Change Validation

后置验证：90/90 全量测试通过，新增 test_adr_none_skips_session_freshness_check 验证 [ADR-none] 在 session log 陈旧时仍能通过；5 个受影响的测试用例已从 [ADR-none] 更正为 [ADR-000] 以保持其 session 阻塞语义


## Closure Summary

ADR-013 新增的 subagent session 时间戳新鲜度检查在 run_commit_msg 中位于 token 类型解析之前，导致 [ADR-none] 轻量路径也被强制要求 subagent 审计。修复：将 check_subagent_session + check_session_log_freshness 从 bypass else 分支移到 [ADR-NNN] 专属路径内，[ADR-none] 仅走 exemption_allows 豁免检查。补测试覆盖；5 个受影响测试从 [ADR-none] 更正为 [ADR-000] 保持语义。


## References

- **Commits**: 待从 git 自动采集
- **Plan**: doc/arch/plans/ADR-015-plan-001.md


## Checkpoints

- [ ] 澄清完成
- [ ] 前置验证完成
- [ ] 实施完成
- [ ] 后置验证完成
- [ ] ADR 回填完成
