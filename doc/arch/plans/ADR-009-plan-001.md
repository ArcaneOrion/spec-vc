# ADR-009 执行方案 001

- **ADR**: ADR-009
- **ADR Title**: 引入 PostToolUse hook subagent 调用追踪机制，确保 commit 前必须经过 subagent 审计
- **Stage**: validate
- **Created At**: 2026-05-03T17:20:47
- **Summary**: 引入 PostToolUse hook subagent 调用追踪，确保 commit 前必须经过 subagent 审计

## Clarification

- 动机与上下文: ADR-008 的 hash chain token 机制存在哲学缺陷：AI 主 agent 同时控制 report 写入端（写 audit-report.json + test-report.json）和 submit 校验端（write_commit_token 计算哈希），两端在同一权限域内，hash chain 是安全戏剧——AI 想伪造时可以同步更新哈希。真正确保 subagent 审计被执行的方法是利用 Claude Code harness 层的 PostToolUse hook——它在 Claude Code 进程内执行 shell 命令，AI agent 的 Bash 工具无法干预，是真正不可伪造的证据来源。
- 目标与边界: 保留 ADR-008 的 prepare/submit 拆分 + TTY gate。砍掉 hash chain token（还原为 uuid+timestamp 两行 basic token）。新增 PostToolUse hook 记录 Agent 工具调用到 .git/spec-vc-subagent-sessions.log。commit-msg hook 校验链升级为：token 存在且未过期 → subagent-sessions.log 存在且非空 → ADR 引用校验。prepare 命令写入 .git/spec-vc-prepare-ts 作为会话起点。SPEC_VC_BYPASS 保留为 raw escape（跳过 token + subagent session 检查）。不含 hash chain、不含双触发通道、不含 OOB 确认。
- 设计与架构: 三层变更：(1) 新增 spec-vc hook post-tool-use 命令——shell 脚本接收 tool_name/description 参数，全量记录 Agent 调用行到 .git/spec-vc-subagent-sessions.log（格式：ISO时间戳 | tool_name | description）。(2) commit.py write_commit_token 还原为两行格式，validate_and_consume_token 砍掉 hash chain 校验，改为检查 subagent-sessions.log 存在且非空。(3) 配置层——.claude/settings.json 注册 PostToolUse hook，matcher 匹配 Agent 工具，command 调用 spec-vc hook post-tool-use。cli.py cmd_commit_prepare 写入 prepare-ts，cmd_commit_submit 移除 hash chain 相关代码。
- 实现路径: (1) cli.py: cmd_commit_prepare 新增写入 .git/spec-vc-prepare-ts（ISO 时间戳）。cmd_commit_submit 移除 manifest_hash/audit_hash/test_hash 计算和 write_commit_token 的哈希参数，简化 write_commit_token 调用为无参。(2) commit.py: write_commit_token 还原为仅 uuid+timestamp 两行。validate_and_consume_token 移除 hash chain 校验分支（文件存在性检查、SHA-256 计算、哈希比对），新增 subagent-sessions.log 存在性+非空检查，错误信息更新为'请先通过 spec-vc commit prepare + subagent 审计 + submit 流程提交代码'。(3) hooks.py: 新增 run_post_tool_use 函数——接收 tool_name/description，全量追加到 .git/spec-vc-subagent-sessions.log。cli.py 新增 cmd_hook_post_tool_use 入口。build_parser 注册 hook post-tool-use 子命令。(4) Config/Settings: .claude/settings.json 注册 PostToolUse hook，matcher 匹配 Agent 工具调用，command 为 spec-vc hook post-tool-use --tool-name '' --description ''。(5) SKILL.md: commit 段更新——移除 hash chain 描述，增加 PostToolUse hook 说明。(6) Spec-003: 更新 dev-doc.md 移除 hash chain 数据形状和行为规则，保留 prepare/submit 契约。重新 formalize。(7) tests: 更新 test_cli.py 移除 hash chain 测试，新增 subagent session 检查测试；更新 test_commit.py token 格式测试；确保现有测试适配。
- 验证与测试: (1) 改前基线：运行全量 pytest，记录通过数。(2) 改后验证：prepare 写入 prepare-ts 但不写 token；submit 检查 subagent-sessions.log 存在且非空后写 basic token；无 subagent session 记录时 git commit 被 hook 阻塞（'未找到 subagent 审计记录'）；PostToolUse hook 自动记录 Agent 调用到日志文件，格式正确（ISO 时间戳 | Agent | description）；SPEC_VC_BYPASS 设置后跳过 token + subagent session 检查直接放行；hash chain token 相关代码完全移除（SHA-256 计算、5 行 token 格式、哈希比对），token 回到 2 行格式。(3) 全量测试通过。
- 风险与回滚: (1) PostToolUse hook 依赖 settings.json 配置——如果用户未初始化或 settings.json 损坏，hook 不会触发，subagent-sessions.log 不会生成。兜底：commit-msg hook 的 subagent session 检查在 log 缺失时给出明确错误信息（'请确保 .claude/settings.json 中已配置 PostToolUse hook，运行 spec-vc init 重新初始化'）。(2) PostToolUse hook 对每次 Agent 调用都写日志，频繁对话可能导致日志文件膨胀——低风险（纯文本 append，单人项目不会很大），未来可按需加 rotation。(3) 回滚路径：git revert 后 token 门禁回到 ADR-008 状态（hash chain 机制），spec-vc init --seed 可重新部署 PostToolUse hook 配置。(4) SPEC_VC_BYPASS 保留为最终逃生口。


## Clarification History

- 动机与上下文: ADR-008 的 hash chain token 机制存在哲学缺陷：AI 主 agent 同时控制 report 写入端（写 audit-report.json + test-report.json）和 submit 校验端（write_commit_token 计算哈希），两端在同一权限域内，hash chain 是安全戏剧——AI 想伪造时可以同步更新哈希。真正确保 subagent 审计被执行的方法是利用 Claude Code harness 层的 PostToolUse hook——它在 Claude Code 进程内执行 shell 命令，AI agent 的 Bash 工具无法干预，是真正不可伪造的证据来源。
- 目标与边界: 保留 ADR-008 的 prepare/submit 拆分 + TTY gate。砍掉 hash chain token（还原为 uuid+timestamp 两行 basic token）。新增 PostToolUse hook 记录 Agent 工具调用到 .git/spec-vc-subagent-sessions.log。commit-msg hook 校验链升级为：token 存在且未过期 → subagent-sessions.log 存在且非空 → ADR 引用校验。prepare 命令写入 .git/spec-vc-prepare-ts 作为会话起点。SPEC_VC_BYPASS 保留为 raw escape（跳过 token + subagent session 检查）。不含 hash chain、不含双触发通道、不含 OOB 确认。
- 设计与架构: 三层变更：(1) 新增 spec-vc hook post-tool-use 命令——shell 脚本接收 tool_name/description 参数，全量记录 Agent 调用行到 .git/spec-vc-subagent-sessions.log（格式：ISO时间戳 | tool_name | description）。(2) commit.py write_commit_token 还原为两行格式，validate_and_consume_token 砍掉 hash chain 校验，改为检查 subagent-sessions.log 存在且非空。(3) 配置层——.claude/settings.json 注册 PostToolUse hook，matcher 匹配 Agent 工具，command 调用 spec-vc hook post-tool-use。cli.py cmd_commit_prepare 写入 prepare-ts，cmd_commit_submit 移除 hash chain 相关代码。
- 实现路径: (1) cli.py: cmd_commit_prepare 新增写入 .git/spec-vc-prepare-ts（ISO 时间戳）。cmd_commit_submit 移除 manifest_hash/audit_hash/test_hash 计算和 write_commit_token 的哈希参数，简化 write_commit_token 调用为无参。(2) commit.py: write_commit_token 还原为仅 uuid+timestamp 两行。validate_and_consume_token 移除 hash chain 校验分支（文件存在性检查、SHA-256 计算、哈希比对），新增 subagent-sessions.log 存在性+非空检查，错误信息更新为'请先通过 spec-vc commit prepare + subagent 审计 + submit 流程提交代码'。(3) hooks.py: 新增 run_post_tool_use 函数——接收 tool_name/description，全量追加到 .git/spec-vc-subagent-sessions.log。cli.py 新增 cmd_hook_post_tool_use 入口。build_parser 注册 hook post-tool-use 子命令。(4) Config/Settings: .claude/settings.json 注册 PostToolUse hook，matcher 匹配 Agent 工具调用，command 为 spec-vc hook post-tool-use --tool-name '' --description ''。(5) SKILL.md: commit 段更新——移除 hash chain 描述，增加 PostToolUse hook 说明。(6) Spec-003: 更新 dev-doc.md 移除 hash chain 数据形状和行为规则，保留 prepare/submit 契约。重新 formalize。(7) tests: 更新 test_cli.py 移除 hash chain 测试，新增 subagent session 检查测试；更新 test_commit.py token 格式测试；确保现有测试适配。
- 验证与测试: (1) 改前基线：运行全量 pytest，记录通过数。(2) 改后验证：prepare 写入 prepare-ts 但不写 token；submit 检查 subagent-sessions.log 存在且非空后写 basic token；无 subagent session 记录时 git commit 被 hook 阻塞（'未找到 subagent 审计记录'）；PostToolUse hook 自动记录 Agent 调用到日志文件，格式正确（ISO 时间戳 | Agent | description）；SPEC_VC_BYPASS 设置后跳过 token + subagent session 检查直接放行；hash chain token 相关代码完全移除（SHA-256 计算、5 行 token 格式、哈希比对），token 回到 2 行格式。(3) 全量测试通过。
- 风险与回滚: (1) PostToolUse hook 依赖 settings.json 配置——如果用户未初始化或 settings.json 损坏，hook 不会触发，subagent-sessions.log 不会生成。兜底：commit-msg hook 的 subagent session 检查在 log 缺失时给出明确错误信息（'请确保 .claude/settings.json 中已配置 PostToolUse hook，运行 spec-vc init 重新初始化'）。(2) PostToolUse hook 对每次 Agent 调用都写日志，频繁对话可能导致日志文件膨胀——低风险（纯文本 append，单人项目不会很大），未来可按需加 rotation。(3) 回滚路径：git revert 后 token 门禁回到 ADR-008 状态（hash chain 机制），spec-vc init --seed 可重新部署 PostToolUse hook 配置。(4) SPEC_VC_BYPASS 保留为最终逃生口。


## Motivation and Context

ADR-008 的 hash chain token 机制存在哲学缺陷：AI 主 agent 同时控制 report 写入端（写 audit-report.json + test-report.json）和 submit 校验端（write_commit_token 计算哈希），两端在同一权限域内，hash chain 是安全戏剧——AI 想伪造时可以同步更新哈希。真正确保 subagent 审计被执行的方法是利用 Claude Code harness 层的 PostToolUse hook——它在 Claude Code 进程内执行 shell 命令，AI agent 的 Bash 工具无法干预，是真正不可伪造的证据来源。


## Goals and Boundaries

保留 ADR-008 的 prepare/submit 拆分 + TTY gate。砍掉 hash chain token（还原为 uuid+timestamp 两行 basic token）。新增 PostToolUse hook 记录 Agent 工具调用到 .git/spec-vc-subagent-sessions.log。commit-msg hook 校验链升级为：token 存在且未过期 → subagent-sessions.log 存在且非空 → ADR 引用校验。prepare 命令写入 .git/spec-vc-prepare-ts 作为会话起点。SPEC_VC_BYPASS 保留为 raw escape（跳过 token + subagent session 检查）。不含 hash chain、不含双触发通道、不含 OOB 确认。


## Design and Architecture

三层变更：(1) 新增 spec-vc hook post-tool-use 命令——shell 脚本接收 tool_name/description 参数，全量记录 Agent 调用行到 .git/spec-vc-subagent-sessions.log（格式：ISO时间戳 | tool_name | description）。(2) commit.py write_commit_token 还原为两行格式，validate_and_consume_token 砍掉 hash chain 校验，改为检查 subagent-sessions.log 存在且非空。(3) 配置层——.claude/settings.json 注册 PostToolUse hook，matcher 匹配 Agent 工具，command 调用 spec-vc hook post-tool-use。cli.py cmd_commit_prepare 写入 prepare-ts，cmd_commit_submit 移除 hash chain 相关代码。


## Implementation Path

(1) cli.py: cmd_commit_prepare 新增写入 .git/spec-vc-prepare-ts（ISO 时间戳）。cmd_commit_submit 移除 manifest_hash/audit_hash/test_hash 计算和 write_commit_token 的哈希参数，简化 write_commit_token 调用为无参。(2) commit.py: write_commit_token 还原为仅 uuid+timestamp 两行。validate_and_consume_token 移除 hash chain 校验分支（文件存在性检查、SHA-256 计算、哈希比对），新增 subagent-sessions.log 存在性+非空检查，错误信息更新为'请先通过 spec-vc commit prepare + subagent 审计 + submit 流程提交代码'。(3) hooks.py: 新增 run_post_tool_use 函数——接收 tool_name/description，全量追加到 .git/spec-vc-subagent-sessions.log。cli.py 新增 cmd_hook_post_tool_use 入口。build_parser 注册 hook post-tool-use 子命令。(4) Config/Settings: .claude/settings.json 注册 PostToolUse hook，matcher 匹配 Agent 工具调用，command 为 spec-vc hook post-tool-use --tool-name '' --description ''。(5) SKILL.md: commit 段更新——移除 hash chain 描述，增加 PostToolUse hook 说明。(6) Spec-003: 更新 dev-doc.md 移除 hash chain 数据形状和行为规则，保留 prepare/submit 契约。重新 formalize。(7) tests: 更新 test_cli.py 移除 hash chain 测试，新增 subagent session 检查测试；更新 test_commit.py token 格式测试；确保现有测试适配。


## Verification and Testing

(1) 改前基线：运行全量 pytest，记录通过数。(2) 改后验证：prepare 写入 prepare-ts 但不写 token；submit 检查 subagent-sessions.log 存在且非空后写 basic token；无 subagent session 记录时 git commit 被 hook 阻塞（'未找到 subagent 审计记录'）；PostToolUse hook 自动记录 Agent 调用到日志文件，格式正确（ISO 时间戳 | Agent | description）；SPEC_VC_BYPASS 设置后跳过 token + subagent session 检查直接放行；hash chain token 相关代码完全移除（SHA-256 计算、5 行 token 格式、哈希比对），token 回到 2 行格式。(3) 全量测试通过。


## Risks and Rollback

(1) PostToolUse hook 依赖 settings.json 配置——如果用户未初始化或 settings.json 损坏，hook 不会触发，subagent-sessions.log 不会生成。兜底：commit-msg hook 的 subagent session 检查在 log 缺失时给出明确错误信息（'请确保 .claude/settings.json 中已配置 PostToolUse hook，运行 spec-vc init 重新初始化'）。(2) PostToolUse hook 对每次 Agent 调用都写日志，频繁对话可能导致日志文件膨胀——低风险（纯文本 append，单人项目不会很大），未来可按需加 rotation。(3) 回滚路径：git revert 后 token 门禁回到 ADR-008 状态（hash chain 机制），spec-vc init --seed 可重新部署 PostToolUse hook 配置。(4) SPEC_VC_BYPASS 保留为最终逃生口。


## Affected Areas

待补充

## Pre-Change Validation

基线 107 pytest 全部通过。当前状态：ADR-008 hash chain token 机制已实现但存在哲学缺陷——AI 主 agent 同时控制 report 写入端和 submit 校验端。ADR-009 将用 PostToolUse hook (harness 层，AI Bash 工具无法干预) 替代 hash chain 作为 subagent 审计的证据来源。Spec-004 已创建并就绪。待修改文件：commit.py (移除 hash chain，还原 basic token，新增 subagent session 检查)、cli.py (移除 hash chain 代码，新增 post-tool-use 和 prepare-ts)、hooks.py (新增 run_post_tool_use)、settings.json (注册 PostToolUse hook)、SKILL.md (更新 commit 段)。


## Post-Change Validation

修改后验证：(1) 全量 107 pytest 通过。(2) write_commit_token 还原为 2 行 basic token 格式（uuid+timestamp），hash chain（5 行、SHA-256、哈希比对）完全移除。(3) validate_and_consume_token 新增 subagent session 检查：.git/spec-vc-subagent-sessions.log 缺失时阻塞输出'未找到 subagent 审计记录'。(4) spec-vc hook post-tool-use --tool-name Agent --description '...' 正确追加日志行到 .git/spec-vc-subagent-sessions.log，格式为 ISO 时间戳 | Agent | description。(5) SPEC_VC_BYPASS 设置后跳过 token + subagent session 检查直接放行。(6) cmd_commit_prepare 新增写入 .git/spec-vc-prepare-ts，cmd_commit_submit 移除哈希计算和 hash chain 相关代码。(7) SKILL.md commit 段已更新为 subagent session 检查 + PostToolUse hook 配置说明。(8) test_cli.py hash chain 测试替换为 subagent session 测试（含 session 检查通过、无 session 阻塞、bypass 跳过）。


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
