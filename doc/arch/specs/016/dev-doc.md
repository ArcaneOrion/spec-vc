# Spec-016: PostToolUse hook stdin JSON 输入契约修正

- **ADR**: ADR-016
- **Status**: Draft
- **Author**: arcaneorion
- **Date**: 2026-05-14
- **Version**: 0.1.0

---

## 概述

Spec-004 在描述 PostToolUse hook 的接口契约时，把 `tool_name` / `description` 写成了 query parameters，并未对照 Claude Code harness 的真实接口——harness 不导出 `tool_input` 字段为环境变量，而是通过 **stdin JSON payload** 传递。spec-vc 安装的 `.claude/settings.json` 命令行采用 `--description "${CLAUDE_TOOL_DESCRIPTION}"` 这一不存在的环境变量插值，shell 展开为空串。ADR-013 收紧"空 description 跳过写日志"后问题彻底显形：session log 停止增长 → `[ADR-NNN]` commit 因 `check_subagent_session` 失败被阻塞 → 时间戳新鲜度检查无新行可比。

本 Spec 修正 PostToolUse hook 的输入契约：CLI 优先从 stdin JSON 读取 `tool_name` 和 `tool_input.description`；命令行参数仅在 stdin 不可用时作为 fallback；JSON 解析失败 fail-open（不阻塞 commit）。同时把 `_init_claude_hook` 写入的命令简化为 `spec-vc hook post-tool-use`（不再带参数），让 hook 100% 走 stdin 通路。Spec-004 不改动，作为 ADR-009 时期设计的历史记录保留。

**包含**:
- `run_post_tool_use(repo_root, tool_name, description)` 行为升级：stdin JSON 优先 + CLI 参数 fallback + fail-open
- `cli._init_claude_hook` 写入的 PostToolUse command 字符串简化（去掉 `--tool-name` / `--description`）
- argparse 中 `--tool-name` / `--description` 改 `default=""` 可选（兼容旧 settings.json）
- ADR-013 的"空 description 跳过"规则不变

**不包含**:
- 不修改 Spec-004（其历史记录的契约仍属 ADR-009 范畴）
- 不引入 `jq` 等外部依赖
- 不改 commit-msg / prepare-commit-msg hook
- 不变更其他 commit 校验链项（plan stage / Spec 完整性等）
- 不解析 stdin JSON 中除 `tool_name` 与 `tool_input.description` 之外的字段

---

## 接口契约

```yaml
openapi: "3.0.3"
info:
  title: spec-vc PostToolUse hook v2 (stdin JSON contract)
  version: "0.1.0"
  description: |
    修正 Spec-004 中 PostToolUse hook 输入契约的错误（query parameters → stdin JSON）。
    与 Claude Code harness 实际行为对齐：harness 通过 stdin 传 JSON payload，
    不导出 tool_input 字段为环境变量。
    本契约不对外暴露 HTTP，由函数副作用 + 退出码表达。
paths:
  /internal/hook/post-tool-use:
    post:
      summary: 记录 Agent 工具调用到 .git/spec-vc-subagent-sessions.log
      description: |
        参数解析优先级（自上而下）：
        1. CLI 显式传入的 --tool-name / --description（非空则使用）
        2. stdin 非 tty 且包含 JSON 时，从 payload 解析 tool_name 与 tool_input.description
        3. 二者皆无 → 不写日志，return 0（不抛错）
        ADR-013 规则保留：解析后 description 仍为空（含纯空白）→ 跳过写日志。
      requestBody:
        required: false
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/PostToolUseHookPayload"
        description: |
          Claude Code harness 触发时通过 stdin 注入的 JSON payload。
          手工 CLI 调用时可省略（走 args fallback 或不写日志）。
      responses:
        "0":
          description: |
            正常退出。可能的副作用：
            - 写入日志一行 `ISO时间戳 | <tool_name> | <description>\n`
            - 或跳过写入（参数/payload 缺失 / description 空 / JSON 解析失败）
components:
  schemas:
    PostToolUseHookPayload:
      type: object
      description: |
        Claude Code PostToolUse hook 通过 stdin 传入的 JSON 结构。
        本 Spec 仅依赖 tool_name 与 tool_input.description 两个字段，
        其余字段（hook_event_name / tool_response 等）允许存在但不消费。
      properties:
        tool_name:
          type: string
          description: 被调用的工具名，本 hook 在 settings.json 中以 matcher="Agent" 注册
        tool_input:
          type: object
          properties:
            description:
              type: string
              description: Agent 调用时填入的 description 字段；可能为空或缺失
      required: []
```

---

## 数据形状

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "post-tool-use-resolution",
  "description": "run_post_tool_use 解析输入后得到的内部状态。本 schema 仅描述输入字段；行为决策（写日志 / 跳过）完整规则见行为规则区块的 Gherkin scenario，不在此处冗余建模。",
  "type": "object",
  "required": ["source", "tool_name", "description"],
  "properties": {
    "source": {
      "type": "string",
      "enum": ["cli_args", "stdin_json", "none"],
      "description": "实际取值来源；cli_args 优先，stdin_json 在参数为空且 stdin 非 tty 且 JSON 解析成功时使用；二者皆失败为 none"
    },
    "tool_name": {
      "type": "string",
      "description": "解析后的工具名；空字符串等价于跳过写日志"
    },
    "description": {
      "type": "string",
      "description": "解析后的 description；strip() 为空则跳过写日志（ADR-013 规则）"
    }
  },
  "examples": [
    {
      "source": "stdin_json",
      "tool_name": "Agent",
      "description": "ADR-016 code audit"
    },
    {
      "source": "cli_args",
      "tool_name": "Agent",
      "description": "manual probe"
    },
    {
      "source": "stdin_json",
      "tool_name": "Agent",
      "description": ""
    },
    {
      "source": "none",
      "tool_name": "",
      "description": ""
    }
  ]
}
```

---

## 行为规则

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

## 非目标

- 不修正 Spec-004：它的接口契约仍属 ADR-009 时期的历史记录，留作溯源
- 不引入 `jq` 或其他外部解析工具
- 不解析 stdin JSON 中除 `tool_name` 与 `tool_input.description` 之外的字段（如 `prompt`、`subagent_type`、`tool_response`）
- 不变更 ADR-013 的"空 description 跳过写日志"规则
- 不变更 commit-msg hook 校验链中的其他项（plan stage / Spec 完整性 / SPEC_VC_BYPASS）
- 不为 stdin 读取设置超时（fail-open 已覆盖异常路径，且 Claude Code harness 自身有 hook 超时控制）

---

## 测试策略

```gherkin
Scenario Outline: 单元测试覆盖矩阵
  Given 输入条件 "<input>"
  When 调用 run_post_tool_use
  Then 行为为 "<expected>"

  Examples:
    | input                                            | expected                          |
    | stdin JSON 含完整 tool_input.description         | 写一行，description 来自 stdin    |
    | stdin JSON description=""                        | 不写日志                          |
    | stdin JSON 缺 tool_input                          | 不写日志                          |
    | stdin 非 JSON 文本                                | 不写日志，不抛异常                |
    | stdin 是 tty + 无 CLI 参数                       | 不写日志                          |
    | CLI 传 --description 非空，stdin 也有 JSON       | 写一行，description 来自 CLI 参数 |
    | CLI 传 --description ""，stdin 是 tty            | 不写日志                          |
```

集成验证：

- 修改前已复现：手工执行 `spec-vc hook post-tool-use --tool-name Agent --description "${CLAUDE_TOOL_DESCRIPTION}"` 返回 0 但 log 无新增。
- 修改后：在本会话或新会话内启动一个 Agent subagent，观察 `.git/spec-vc-subagent-sessions.log` 末行 description 非空、时间戳为当前时刻。
- 回归：`uv run pytest tests/python/` 全过。

---

## 日志实现

`run_post_tool_use` 不主动 log（hook 自身是日志收集端）。异常路径（stdin 读失败 / JSON 解析失败 / 文件写入失败）一律 fail-open 静默 return 0，避免污染 stderr 干扰 Claude Code harness。

---

## 变更历史

| 版本 | 日期 | 作者 | 变更内容 |
|------|------|------|----------|
| 0.1.0 | 2026-05-14 | arcaneorion | 初始版本：修正 Spec-004 的 PostToolUse hook 输入契约错误 |

---

## References

- **ADR**: ADR-016
- **Related Specs**: Spec-004（被修正的对象，保留作 ADR-009 时期的历史记录）
- **External**: [Claude Code Hooks reference](https://code.claude.com/docs/en/hooks)
