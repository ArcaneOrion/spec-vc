# ADR-011 执行方案 001

- **ADR**: ADR-011
- **ADR Title**: 移除 commit submit 阶段，简化为 prepare + hook 校验循环
- **Stage**: close
- **Created At**: 2026-05-08T11:58:28
- **Summary**: 移除 commit submit 阶段和 token 机制，简化为 prepare 写 commit-msg + subagent 审计 + git commit + hook 校验循环

## Clarification

- 动机与上下文: 当前 commit 提交协议设计臃肿，脱离了确保变更质量这一初衷。commit submit 阶段（TTY 检测 + 交互确认 + token 写入）是仪式性防线——它阻止 AI 点击提交按钮，但不提供实质审查。token 机制（uuid+timestamp+300s TTL）是纯机械校验，与变更质量无关。实际上审查变更质量的应该是：(1) 是否有人审计了变更（subagent session log），(2) 变更是否走完了计划流程（plan stage），(3) Spec 是否完整而非骨架。这些都可以在 commit-msg hook 里机械检查。
- 目标与边界: 目标：移除 commit submit 命令、token 机制（write/validate/consume/TTL）、TTY 检测、交互确认、prepare_ts 时间戳文件。新增 hook 中的 plan stage 检查和 spec 完整性检查。保留 commit prepare（spec 就绪检查+写 commit-msg）、PostToolUse subagent session 记录、ADR 引用校验、豁免规则、SPEC_VC_BYPASS 逃生口。不做：不增加新的命令，不做代码层面的语义一致性检查（由 subagent 审计负责），不改变 change 状态机的其他阶段。
- 设计与架构: 提交协议简化为单路径：commit prepare（AI 域）→ AI subagent 审计 → git commit -F → commit-msg hook 校验。Hook 校验链：SPEC_VC_BYPASS→session log 非空→ADR 引用合法→[ADR-NNN 时] plan stage ≥ implement-ready + spec 完整→放行。校验失败则 git commit 被阻塞，错误信息提示 AI 修改后重试。删除 commit.py 中的 token 相关函数（write_commit_token/validate_and_consume_token/TOKEN_TTL_SECONDS/TOKEN_FILENAME）和 PREPARE_TS_FILENAME。删除 cli.py 中 cmd_commit_submit 及其 subparser。hooks.py 中 run_commit_msg 不再调用 validate_and_consume_token，改为读 session log 文件。新增 plan stage 检查：从 _active.md 读取 stage 字段，verify ≥ implement-ready。新增 spec 完整性检查：调用 check_spec_readiness。
- 实现路径: 1. commit.py: 删除 write_commit_token、validate_and_consume_token、TOKEN_TTL_SECONDS、TOKEN_FILENAME、PREPARE_TS_FILENAME、SUBAGENT_SESSIONS_FILENAME 常量。保留 COMMIT_MSG_FILENAME、gather_commit_context、CommitContext。2. cli.py: 删除 cmd_commit_submit 及其 subparser 注册，删除 prepare --write-ts 相关逻辑，删除 submit 子命令。cmd_commit_prepare 不再写 token 和时间戳。3. hooks.py: run_commit_msg 中替换 validate_and_consume_token 为直接检查 session log 文件存在且非空。新增 _check_plan_stage 函数读 active change 判断 stage ≥ implement-ready。新增 _check_spec_readiness 函数调用 check_spec_readiness（仅对 [ADR-NNN] 引用触发）。4. 删除 tests 中与 token/submit 相关的测试用例，更新与新流程不符的测试。5. SKILL.md: 更新 commit 协议描述，删除 submit 阶段相关内容。6. CLAUDE.md: 更新提交协议描述。
- 验证与测试: 1. pytest 全量测试通过。2. 手动测试：commit prepare → AI 审计 → git commit → hook 阻塞（无 session log）→ 写入 session log → git commit → hook 通过。3. SPEC_VC_BYPASS 绕过测试。4. [ADR-none] 豁免规则测试。5. plan stage < implement-ready 时 hook 阻塞测试。6. spec 未完成时 hook 阻塞测试。
- 风险与回滚: git revert 回退所有变更。核心改动集中在 commit.py/cli.py/hooks.py 三个文件，回退范围明确。原有的 token 相关代码无其他依赖方。


## Clarification History

- 动机与上下文: 当前 commit 提交协议设计臃肿，脱离了确保变更质量这一初衷。commit submit 阶段（TTY 检测 + 交互确认 + token 写入）是仪式性防线——它阻止 AI 点击提交按钮，但不提供实质审查。token 机制（uuid+timestamp+300s TTL）是纯机械校验，与变更质量无关。实际上审查变更质量的应该是：(1) 是否有人审计了变更（subagent session log），(2) 变更是否走完了计划流程（plan stage），(3) Spec 是否完整而非骨架。这些都可以在 commit-msg hook 里机械检查。
- 目标与边界: 目标：移除 commit submit 命令、token 机制（write/validate/consume/TTL）、TTY 检测、交互确认、prepare_ts 时间戳文件。新增 hook 中的 plan stage 检查和 spec 完整性检查。保留 commit prepare（spec 就绪检查+写 commit-msg）、PostToolUse subagent session 记录、ADR 引用校验、豁免规则、SPEC_VC_BYPASS 逃生口。不做：不增加新的命令，不做代码层面的语义一致性检查（由 subagent 审计负责），不改变 change 状态机的其他阶段。
- 设计与架构: 提交协议简化为单路径：commit prepare（AI 域）→ AI subagent 审计 → git commit -F → commit-msg hook 校验。Hook 校验链：SPEC_VC_BYPASS→session log 非空→ADR 引用合法→[ADR-NNN 时] plan stage ≥ implement-ready + spec 完整→放行。校验失败则 git commit 被阻塞，错误信息提示 AI 修改后重试。删除 commit.py 中的 token 相关函数（write_commit_token/validate_and_consume_token/TOKEN_TTL_SECONDS/TOKEN_FILENAME）和 PREPARE_TS_FILENAME。删除 cli.py 中 cmd_commit_submit 及其 subparser。hooks.py 中 run_commit_msg 不再调用 validate_and_consume_token，改为读 session log 文件。新增 plan stage 检查：从 _active.md 读取 stage 字段，verify ≥ implement-ready。新增 spec 完整性检查：调用 check_spec_readiness。
- 实现路径: 1. commit.py: 删除 write_commit_token、validate_and_consume_token、TOKEN_TTL_SECONDS、TOKEN_FILENAME、PREPARE_TS_FILENAME、SUBAGENT_SESSIONS_FILENAME 常量。保留 COMMIT_MSG_FILENAME、gather_commit_context、CommitContext。2. cli.py: 删除 cmd_commit_submit 及其 subparser 注册，删除 prepare --write-ts 相关逻辑，删除 submit 子命令。cmd_commit_prepare 不再写 token 和时间戳。3. hooks.py: run_commit_msg 中替换 validate_and_consume_token 为直接检查 session log 文件存在且非空。新增 _check_plan_stage 函数读 active change 判断 stage ≥ implement-ready。新增 _check_spec_readiness 函数调用 check_spec_readiness（仅对 [ADR-NNN] 引用触发）。4. 删除 tests 中与 token/submit 相关的测试用例，更新与新流程不符的测试。5. SKILL.md: 更新 commit 协议描述，删除 submit 阶段相关内容。6. CLAUDE.md: 更新提交协议描述。
- 验证与测试: 1. pytest 全量测试通过。2. 手动测试：commit prepare → AI 审计 → git commit → hook 阻塞（无 session log）→ 写入 session log → git commit → hook 通过。3. SPEC_VC_BYPASS 绕过测试。4. [ADR-none] 豁免规则测试。5. plan stage < implement-ready 时 hook 阻塞测试。6. spec 未完成时 hook 阻塞测试。
- 风险与回滚: git revert 回退所有变更。核心改动集中在 commit.py/cli.py/hooks.py 三个文件，回退范围明确。原有的 token 相关代码无其他依赖方。


## Motivation and Context

当前 commit 提交协议设计臃肿，脱离了确保变更质量这一初衷。commit submit 阶段（TTY 检测 + 交互确认 + token 写入）是仪式性防线——它阻止 AI 点击提交按钮，但不提供实质审查。token 机制（uuid+timestamp+300s TTL）是纯机械校验，与变更质量无关。实际上审查变更质量的应该是：(1) 是否有人审计了变更（subagent session log），(2) 变更是否走完了计划流程（plan stage），(3) Spec 是否完整而非骨架。这些都可以在 commit-msg hook 里机械检查。


## Goals and Boundaries

目标：移除 commit submit 命令、token 机制（write/validate/consume/TTL）、TTY 检测、交互确认、prepare_ts 时间戳文件。新增 hook 中的 plan stage 检查和 spec 完整性检查。保留 commit prepare（spec 就绪检查+写 commit-msg）、PostToolUse subagent session 记录、ADR 引用校验、豁免规则、SPEC_VC_BYPASS 逃生口。不做：不增加新的命令，不做代码层面的语义一致性检查（由 subagent 审计负责），不改变 change 状态机的其他阶段。


## Design and Architecture

提交协议简化为单路径：commit prepare（AI 域）→ AI subagent 审计 → git commit -F → commit-msg hook 校验。Hook 校验链：SPEC_VC_BYPASS→session log 非空→ADR 引用合法→[ADR-NNN 时] plan stage ≥ implement-ready + spec 完整→放行。校验失败则 git commit 被阻塞，错误信息提示 AI 修改后重试。删除 commit.py 中的 token 相关函数（write_commit_token/validate_and_consume_token/TOKEN_TTL_SECONDS/TOKEN_FILENAME）和 PREPARE_TS_FILENAME。删除 cli.py 中 cmd_commit_submit 及其 subparser。hooks.py 中 run_commit_msg 不再调用 validate_and_consume_token，改为读 session log 文件。新增 plan stage 检查：从 _active.md 读取 stage 字段，verify ≥ implement-ready。新增 spec 完整性检查：调用 check_spec_readiness。


## Implementation Path

1. commit.py: 删除 write_commit_token、validate_and_consume_token、TOKEN_TTL_SECONDS、TOKEN_FILENAME、PREPARE_TS_FILENAME、SUBAGENT_SESSIONS_FILENAME 常量。保留 COMMIT_MSG_FILENAME、gather_commit_context、CommitContext。2. cli.py: 删除 cmd_commit_submit 及其 subparser 注册，删除 prepare --write-ts 相关逻辑，删除 submit 子命令。cmd_commit_prepare 不再写 token 和时间戳。3. hooks.py: run_commit_msg 中替换 validate_and_consume_token 为直接检查 session log 文件存在且非空。新增 _check_plan_stage 函数读 active change 判断 stage ≥ implement-ready。新增 _check_spec_readiness 函数调用 check_spec_readiness（仅对 [ADR-NNN] 引用触发）。4. 删除 tests 中与 token/submit 相关的测试用例，更新与新流程不符的测试。5. SKILL.md: 更新 commit 协议描述，删除 submit 阶段相关内容。6. CLAUDE.md: 更新提交协议描述。


## Verification and Testing

1. pytest 全量测试通过。2. 手动测试：commit prepare → AI 审计 → git commit → hook 阻塞（无 session log）→ 写入 session log → git commit → hook 通过。3. SPEC_VC_BYPASS 绕过测试。4. [ADR-none] 豁免规则测试。5. plan stage < implement-ready 时 hook 阻塞测试。6. spec 未完成时 hook 阻塞测试。


## Risks and Rollback

git revert 回退所有变更。核心改动集中在 commit.py/cli.py/hooks.py 三个文件，回退范围明确。原有的 token 相关代码无其他依赖方。


## Affected Areas

待补充

## Pre-Change Validation

当前代码结构清晰，目标明确：从 commit.py 删除 token 机制，从 cli.py 删除 submit 命令，从 hooks.py 重构校验链。三个模块的改动边界清楚，没有横切关注点需要额外处理。新逻辑（plan stage 检查、spec 完整性检查）都有现成的函数可以直接复用。风险可控。


## Post-Change Validation

所有 69 个测试通过。代码改动包括：(1) commit.py 删除 write_commit_token/validate_and_consume_token/TOKEN_TTL_SECONDS/TOKEN_FILENAME/PREPARE_TS_FILENAME，新增 check_subagent_session。(2) hooks.py 用 check_subagent_session 替换 validate_and_consume_token，新增 _check_plan_stage 和 _check_spec_readiness_for_adr。(3) cli.py 删除 cmd_commit_submit、submit subparser、prepare-ts 写入逻辑，清理 import。(4) 测试更新：4 个旧测试更新错误消息和断言，删除 test_commit_prepare_writes_prepare_ts，新增 3 个 plan stage 测试。(5) SKILL.md 和 CLAUDE.md 更新提交流程描述。


## Closure Summary

移除 commit submit 阶段和 token 机制，简化提交流程为 prepare + hook 校验循环。commit-msg hook 新增 plan stage 和 Spec 完整性检查。


## References

- **Commits**: 待从 git 自动采集
- **Plan**: doc/arch/plans/ADR-011-plan-001.md


## Risks and Rollback

待补充

## Checkpoints

- [ ] 澄清完成
- [ ] 前置验证完成
- [ ] 实施完成
- [ ] 后置验证完成
- [ ] ADR 回填完成
