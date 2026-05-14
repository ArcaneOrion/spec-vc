```gherkin
Feature: PostToolUse hook 从 stdin JSON 读取参数

  Background:
    Given .claude/settings.json 已注册 PostToolUse matcher="Agent" 命令为 "spec-vc hook post-tool-use"
    And ADR-013 的"空 description 跳过写日志"规则保持有效

  Rule: stdin JSON 是首选输入通道
    Scenario: harness 通过 stdin 注入完整 payload
      Given stdin 非 tty 且包含 JSON `{"tool_name":"Agent","tool_input":{"description":"audit X"}}`
      And CLI 未传 --tool-name / --description
      When 执行 spec-vc hook post-tool-use
      Then .git/spec-vc-subagent-sessions.log 追加一行 "ISO时间戳 | Agent | audit X"
      And exit code 为 0

  Rule: CLI 参数有值时优先于 stdin
    Scenario: 手工调用传参且 stdin 也有 JSON
      Given stdin 非 tty 且 JSON 中 description 为 "from stdin"
      And CLI 传 --tool-name Agent --description "from cli"
      When 执行 spec-vc hook post-tool-use --tool-name Agent --description "from cli"
      Then 日志末行 description 为 "from cli"
      And exit code 为 0

  Rule: 解析后 description 为空仍跳过（ADR-013 不变）
    Scenario: stdin JSON 中 description 为空字符串
      Given stdin JSON 为 `{"tool_name":"Agent","tool_input":{"description":""}}`
      When 执行 spec-vc hook post-tool-use
      Then 日志无新增行
      And exit code 为 0

    Scenario: stdin JSON 缺少 tool_input 字段
      Given stdin JSON 为 `{"tool_name":"Agent"}`
      When 执行 spec-vc hook post-tool-use
      Then 日志无新增行
      And exit code 为 0

  Rule: JSON 解析失败 fail-open
    Scenario: stdin 非 JSON 文本
      Given stdin 非 tty 且内容为 "not a json"
      And CLI 未传 --tool-name / --description
      When 执行 spec-vc hook post-tool-use
      Then 日志无新增行
      And exit code 为 0
      And 不抛任何异常到 stderr

  Rule: 无 stdin 无参数时静默跳过
    Scenario: 终端手工调用且未传参
      Given stdin 是 tty
      And CLI 未传 --tool-name / --description
      When 执行 spec-vc hook post-tool-use
      Then 日志无新增行
      And exit code 为 0
      And 不阻塞调用方

  Rule: settings.json 模板不再带 hook 参数
    Scenario: spec-vc init 写入新模板
      Given _init_claude_hook 被调用
      When 检查写入的 .claude/settings.json
      Then PostToolUse[matcher=Agent].hooks[0].command 为 "<spec_vc_bin> hook post-tool-use"
      And command 字符串不包含 "--tool-name" 或 "--description" 或 "${CLAUDE_TOOL_DESCRIPTION}"
```

---
