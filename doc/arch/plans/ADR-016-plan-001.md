# ADR-016 执行方案 001

- **ADR**: ADR-016
- **ADR Title**: PostToolUse hook 从 stdin 读 JSON 修复 description 取值
- **Stage**: validate
- **Created At**: 2026-05-14T20:45:33
- **Summary**: 修复 PostToolUse hook description 取值：CLI 从 stdin 读 JSON 而非环境变量

## Clarification

- 动机与上下文: PostToolUse hook 的 description 因 ${CLAUDE_TOOL_DESCRIPTION} 这个不存在的环境变量插值长期为空；ADR-013 收紧"空 description 跳过写日志"后 session log 停止增长，导致 [ADR-NNN] commit 因 check_subagent_session 失败被阻塞，时间戳新鲜度检查也失效。本质是 PostToolUse hook 与 Claude Code harness 的输入契约错误：harness 通过 stdin JSON 传 payload，不导出 tool_input 字段为环境变量。
- 目标与边界: 做：CLI 从 stdin JSON 读 tool_name 和 tool_input.description；_init_claude_hook 模板简化命令；保留 ADR-013 空 description 跳过规则。不做：不引入 jq 外部依赖；不改 commit-msg/prepare-commit-msg hook；不改 ADR-013 语义；不清理 session log 历史空行。
- 设计与架构: run_post_tool_use 升级为 stdin JSON 优先 + CLI 参数 fallback：tool_name/description 任一为空且 stdin 非 tty 时读 stdin JSON 解析 tool_name 与 tool_input.description；CLI 参数有值则优先；JSON 解析失败 fail-open（return 0 不阻塞）。_init_claude_hook 写入的命令简化为 'spec-vc hook post-tool-use' 不再带参数。argparse --tool-name/--description 改可选 default=""，兼容旧 settings.json。
- 实现路径: 1. 改 src/spec_vc/hooks.py:run_post_tool_use 增加 stdin JSON fallback 分支；2. 改 src/spec_vc/cli.py:_init_claude_hook 模板去掉 --tool-name/--description；3. 改 cli.py argparse --tool-name/--description default="" 改可选；4. 重写本仓库 .claude/settings.json（patch 现有文件）；5. 扩展 Spec-004 dev-doc.md：接口契约新增 stdin JSON schema + 行为规则补 5 条 Gherkin；6. 跑 spec formalize；7. 更新 SKILL.md 6c 段落示例。
- 验证与测试: 修改前已复现：spec-vc hook post-tool-use --tool-name Agent --description "${CLAUDE_TOOL_DESCRIPTION}" 返回 0 且 log 无新增。修改后单测：(a) stdin JSON 正常路径写入；(b) stdin JSON description 空跳过；(c) CLI 参数 fallback 写入；(d) 无 stdin 无参数不抛错；(e) JSON 解析失败 fail-open。集成验证：实际 Agent 调用后 .git/spec-vc-subagent-sessions.log 末行有新增、description 非空、时间戳当前时刻。回归：pytest tests/python/ 全过。
- 风险与回滚: 风险 A：stdin 是 tty 时避免阻塞读—— sys.stdin.isatty() 判定。风险 B：用户已存在 .claude/settings.json 没自动迁移——文档说明 + 旧命令通过 CLI 参数 fallback 仍可工作。风险 C：JSON schema 变更——用 .get() 防御，缺字段空 description 即跳过。回滚：单 commit 修改，git revert 即可恢复 ADR-013 当前状态。


## Clarification History

- 动机与上下文: PostToolUse hook 的 description 因 ${CLAUDE_TOOL_DESCRIPTION} 这个不存在的环境变量插值长期为空；ADR-013 收紧"空 description 跳过写日志"后 session log 停止增长，导致 [ADR-NNN] commit 因 check_subagent_session 失败被阻塞，时间戳新鲜度检查也失效。本质是 PostToolUse hook 与 Claude Code harness 的输入契约错误：harness 通过 stdin JSON 传 payload，不导出 tool_input 字段为环境变量。
- 目标与边界: 做：CLI 从 stdin JSON 读 tool_name 和 tool_input.description；_init_claude_hook 模板简化命令；保留 ADR-013 空 description 跳过规则。不做：不引入 jq 外部依赖；不改 commit-msg/prepare-commit-msg hook；不改 ADR-013 语义；不清理 session log 历史空行。
- 设计与架构: run_post_tool_use 升级为 stdin JSON 优先 + CLI 参数 fallback：tool_name/description 任一为空且 stdin 非 tty 时读 stdin JSON 解析 tool_name 与 tool_input.description；CLI 参数有值则优先；JSON 解析失败 fail-open（return 0 不阻塞）。_init_claude_hook 写入的命令简化为 'spec-vc hook post-tool-use' 不再带参数。argparse --tool-name/--description 改可选 default=""，兼容旧 settings.json。
- 实现路径: 1. 改 src/spec_vc/hooks.py:run_post_tool_use 增加 stdin JSON fallback 分支；2. 改 src/spec_vc/cli.py:_init_claude_hook 模板去掉 --tool-name/--description；3. 改 cli.py argparse --tool-name/--description default="" 改可选；4. 重写本仓库 .claude/settings.json（patch 现有文件）；5. 扩展 Spec-004 dev-doc.md：接口契约新增 stdin JSON schema + 行为规则补 5 条 Gherkin；6. 跑 spec formalize；7. 更新 SKILL.md 6c 段落示例。
- 验证与测试: 修改前已复现：spec-vc hook post-tool-use --tool-name Agent --description "${CLAUDE_TOOL_DESCRIPTION}" 返回 0 且 log 无新增。修改后单测：(a) stdin JSON 正常路径写入；(b) stdin JSON description 空跳过；(c) CLI 参数 fallback 写入；(d) 无 stdin 无参数不抛错；(e) JSON 解析失败 fail-open。集成验证：实际 Agent 调用后 .git/spec-vc-subagent-sessions.log 末行有新增、description 非空、时间戳当前时刻。回归：pytest tests/python/ 全过。
- 风险与回滚: 风险 A：stdin 是 tty 时避免阻塞读—— sys.stdin.isatty() 判定。风险 B：用户已存在 .claude/settings.json 没自动迁移——文档说明 + 旧命令通过 CLI 参数 fallback 仍可工作。风险 C：JSON schema 变更——用 .get() 防御，缺字段空 description 即跳过。回滚：单 commit 修改，git revert 即可恢复 ADR-013 当前状态。


## Motivation and Context

PostToolUse hook 的 description 因 ${CLAUDE_TOOL_DESCRIPTION} 这个不存在的环境变量插值长期为空；ADR-013 收紧"空 description 跳过写日志"后 session log 停止增长，导致 [ADR-NNN] commit 因 check_subagent_session 失败被阻塞，时间戳新鲜度检查也失效。本质是 PostToolUse hook 与 Claude Code harness 的输入契约错误：harness 通过 stdin JSON 传 payload，不导出 tool_input 字段为环境变量。


## Goals and Boundaries

做：CLI 从 stdin JSON 读 tool_name 和 tool_input.description；_init_claude_hook 模板简化命令；保留 ADR-013 空 description 跳过规则。不做：不引入 jq 外部依赖；不改 commit-msg/prepare-commit-msg hook；不改 ADR-013 语义；不清理 session log 历史空行。


## Design and Architecture

run_post_tool_use 升级为 stdin JSON 优先 + CLI 参数 fallback：tool_name/description 任一为空且 stdin 非 tty 时读 stdin JSON 解析 tool_name 与 tool_input.description；CLI 参数有值则优先；JSON 解析失败 fail-open（return 0 不阻塞）。_init_claude_hook 写入的命令简化为 'spec-vc hook post-tool-use' 不再带参数。argparse --tool-name/--description 改可选 default=""，兼容旧 settings.json。


## Implementation Path

1. 改 src/spec_vc/hooks.py:run_post_tool_use 增加 stdin JSON fallback 分支；2. 改 src/spec_vc/cli.py:_init_claude_hook 模板去掉 --tool-name/--description；3. 改 cli.py argparse --tool-name/--description default="" 改可选；4. 重写本仓库 .claude/settings.json（patch 现有文件）；5. 扩展 Spec-004 dev-doc.md：接口契约新增 stdin JSON schema + 行为规则补 5 条 Gherkin；6. 跑 spec formalize；7. 更新 SKILL.md 6c 段落示例。


## Verification and Testing

修改前已复现：spec-vc hook post-tool-use --tool-name Agent --description "${CLAUDE_TOOL_DESCRIPTION}" 返回 0 且 log 无新增。修改后单测：(a) stdin JSON 正常路径写入；(b) stdin JSON description 空跳过；(c) CLI 参数 fallback 写入；(d) 无 stdin 无参数不抛错；(e) JSON 解析失败 fail-open。集成验证：实际 Agent 调用后 .git/spec-vc-subagent-sessions.log 末行有新增、description 非空、时间戳当前时刻。回归：pytest tests/python/ 全过。


## Risks and Rollback

风险 A：stdin 是 tty 时避免阻塞读—— sys.stdin.isatty() 判定。风险 B：用户已存在 .claude/settings.json 没自动迁移——文档说明 + 旧命令通过 CLI 参数 fallback 仍可工作。风险 C：JSON schema 变更——用 .get() 防御，缺字段空 description 即跳过。回滚：单 commit 修改，git revert 即可恢复 ADR-013 当前状态。


## Affected Areas

待补充

## Pre-Change Validation

已复现 bug：spec-vc hook post-tool-use --tool-name Agent --description "${CLAUDE_TOOL_DESCRIPTION}" 返回 0 但 .git/spec-vc-subagent-sessions.log 无新增。回归 baseline：uv run pytest tests/python/ 90/90 全过。覆盖盲区：现有 4 个 PostToolUse hook 测试全部走 CLI args 路径（--tool-name/--description），stdin JSON 路径无任何单元测试覆盖——这正是本次 bug 的根因域。Spec-016 已就绪（spec check exit=0），形式化文件已生成（contract.openapi.yaml + schema.json + behavior.feature）。clarify 6 字段补齐，stage=plan。


## Post-Change Validation

三层验证全过：(1) 单测 uv run pytest tests/python/ 98/98 全过，含 8 个新加测试（test_post_tool_use_hook_reads_stdin_json / cli_args_override_stdin / skips_empty_description_in_stdin / skips_when_tool_input_missing / fail_open_on_invalid_json / skips_when_stdin_empty_and_no_args / test_init_writes_post_tool_use_hook_without_args / test_init_migrates_legacy_post_tool_use_hook）。(2) skill venv 手工 stdin JSON 模拟：echo '{"tool_name":"Agent","tool_input":{"description":"integration probe via skill venv"}}' | spec-vc hook post-tool-use 写入 21:49:41 行。(3) 真实 Claude Code harness 集成验证：启动 audit subagent 触发 PostToolUse hook，自动写入 21:56:10 行 'ADR-016 code audit + Spec coverage check'，description 由 hook 从 stdin JSON 正确解析，无 CLI 参数。独立 audit subagent 总体结论 PASS：边界条件守卫完备（非 dict/str 类型 fail-open）、迁移逻辑可重入、6 条 Gherkin Rule 全覆盖、向后兼容旧 settings.json。回归 baseline 90 测试 0 失败。


## Closure Summary

待补充

## References

- **Commits**: 待补充
- **Plan**: 待补充

## Checkpoints

- [ ] 澄清完成
- [ ] 前置验证完成
- [ ] 实施完成
- [ ] 后置验证完成
- [ ] ADR 回填完成
