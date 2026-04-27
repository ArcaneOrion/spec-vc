# ADR-006 执行方案 001

- **ADR**: ADR-006
- **ADR Title**: 引入 commit token 门禁机制，强制通过 spec-vc commit 提交
- **Stage**: implement-ready
- **Created At**: 2026-04-27T16:03:23
- **Summary**: 在 commit-msg hook 中增加 token 校验：spec-vc commit 写入一次性 token，hook 验 token 无则阻塞，阻断绕过 spec-vc 直接 git commit 的路径

## Clarification

- 动机与上下文: AI 绕过 spec-vc commit 直接执行 git commit 成功提交，现有 commit-msg hook 只校验 [ADR-NNN] 格式不校验提交通路，需从机制层堵漏
- 目标与边界: 做: spec-vc commit 写入一次性 token，commit-msg hook 验 token，无则阻塞。不做: SKILL.md 禁令规则、pre-commit 阶段校验
- 设计与架构: spec-vc commit 在 .git/spec-vc-commit-token 写入一次性 token(含过期时间); commit-msg hook(bash+hooks.py)校验 token 存在且未过期; 提交成功后 token 被消费清理
- 实现路径: 1) commit.py cmd_commit 写入 token→输出 subagent 提示词 2) hooks.py run_commit_msg 增加 token 校验 3) .git/hooks/commit-msg 调用更新逻辑 4) 添加 token 清理 5) pytest 测试
- 验证与测试: pytest 隔离测试仓库: 无 token 阻塞、有 token 放行、过期 token 阻塞、提交后 token 清理
- 风险与回滚: token 残留风险(过期时间+一次性消费); 最坏情况手动删除 .git/spec-vc-commit-token


## Clarification History

- 动机与上下文: AI 绕过 spec-vc commit 直接执行 git commit 成功提交，现有 commit-msg hook 只校验 [ADR-NNN] 格式不校验提交通路，需从机制层堵漏
- 目标与边界: 做: spec-vc commit 写入一次性 token，commit-msg hook 验 token，无则阻塞。不做: SKILL.md 禁令规则、pre-commit 阶段校验
- 设计与架构: spec-vc commit 在 .git/spec-vc-commit-token 写入一次性 token(含过期时间); commit-msg hook(bash+hooks.py)校验 token 存在且未过期; 提交成功后 token 被消费清理
- 实现路径: 1) commit.py cmd_commit 写入 token→输出 subagent 提示词 2) hooks.py run_commit_msg 增加 token 校验 3) .git/hooks/commit-msg 调用更新逻辑 4) 添加 token 清理 5) pytest 测试
- 验证与测试: pytest 隔离测试仓库: 无 token 阻塞、有 token 放行、过期 token 阻塞、提交后 token 清理
- 风险与回滚: token 残留风险(过期时间+一次性消费); 最坏情况手动删除 .git/spec-vc-commit-token


## Motivation and Context

AI 绕过 spec-vc commit 直接执行 git commit 成功提交，现有 commit-msg hook 只校验 [ADR-NNN] 格式不校验提交通路，需从机制层堵漏


## Goals and Boundaries

做: spec-vc commit 写入一次性 token，commit-msg hook 验 token，无则阻塞。不做: SKILL.md 禁令规则、pre-commit 阶段校验


## Design and Architecture

spec-vc commit 在 .git/spec-vc-commit-token 写入一次性 token(含过期时间); commit-msg hook(bash+hooks.py)校验 token 存在且未过期; 提交成功后 token 被消费清理


## Implementation Path

1) commit.py cmd_commit 写入 token→输出 subagent 提示词 2) hooks.py run_commit_msg 增加 token 校验 3) .git/hooks/commit-msg 调用更新逻辑 4) 添加 token 清理 5) pytest 测试


## Verification and Testing

pytest 隔离测试仓库: 无 token 阻塞、有 token 放行、过期 token 阻塞、提交后 token 清理


## Risks and Rollback

token 残留风险(过期时间+一次性消费); 最坏情况手动删除 .git/spec-vc-commit-token


## Affected Areas

待补充

## Pre-Change Validation

变更前验证：1) 当前 commit-msg hook 只校验 [ADR-NNN] 格式，不校验提交通路，git commit 可直接执行 2) SKILL.md plan 阶段无'展示计划内容到前台'要求，AI 只输出文件路径 3) 现有测试覆盖 hooks 格式校验场景但无 token 门禁测试


## Post-Change Validation

待补充

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
