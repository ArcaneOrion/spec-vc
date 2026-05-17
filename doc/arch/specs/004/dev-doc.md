# Spec-004: PostToolUse hook subagent 调用追踪与 commit 门禁

- **ADR**: ADR-009
- **Status**: Superseded (部分区块被后续 ADR 修正)
- **Author**: arcaneorion
- **Date**: 2026-05-03
- **Version**: 0.1.0

---

> ⚠️ **本 Spec 多个区块已被后续变更修正，保留作 ADR-009 时期的设计历史记录**：
>
> - **PostToolUse hook 输入契约**（接口契约 `/hook/post-tool-use` 节用 query parameters 描述 `tool_name`/`description`）→ 错误，正确契约为 stdin JSON payload，见 [Spec-016](../016/dev-doc.md) / [ADR-016](../../adr-016.md)
> - **commit-msg 校验链中的 token + manifest + prepare-ts + TTY-bound submit** → 已被 [ADR-011](../../adr-011.md) 完全移除，简化为 prepare + hook 校验循环
> - **`/commit/prepare` 与 `/commit/submit` 两阶段端点** → 已被 [ADR-011](../../adr-011.md) 合并为单一 prepare 端点
>
> 阅读本 Spec 时请同时查阅上述 ADR / Spec 以了解当前真实状态。

---

## 概述

### 1.1 问题陈述
spec-vc 维护者需要**机制级保证 subagent 审计流程被执行**，因为 AI 主 agent 同时控制 report 写入和提交校验两端，hash chain token 是安全戏剧——AI 可同步伪造报告和哈希。

### 1.2 解决方案概述
利用 Claude Code harness 层的 PostToolUse hook（AI agent 的 Bash 工具无法干预），全量记录 Agent 工具调用到 `.git/spec-vc-subagent-sessions.log`。commit-msg hook 在 token 校验之后增加 subagent session 存在性检查。配合 ADR-008 的 TTY-bound submit，形成三层防线：用户手动触发提交 + hook 层证据 + 机制级 token 门禁。

### 1.3 范围边界
**包含**:
- `spec-vc hook post-tool-use` 命令
- `.claude/settings.json` PostToolUse hook 注册
- commit-msg hook subagent session 检查
- basic token（2 行，uuid+timestamp）
- prepare-ts 写入
- SPEC_VC_BYPASS 保留

**不包含**:
- hash chain token（SHA-256、5 行格式、哈希比对）
- 双触发通道、OOB 确认、termios TTY 加密

---

## 接口契约
<!-- 本区块内容将同步到 contract.openapi.yaml -->

openapi: 3.0.3
info:
  title: spec-vc commit hooks (PostToolUse + commit-msg)
  version: "0.5.0"
  description: |
    spec-vc 的 hook 层契约。prepare/submit 拆分保留自 ADR-008，
    新增 post-tool-use hook 记录 subagent 调用。
paths:
  /hook/post-tool-use:
    post:
      summary: 记录 Agent 工具调用到 subagent sessions log
      description: |
        由 Claude Code PostToolUse hook 触发，全量记录 Agent 工具调用。
        AI agent 的 Bash 工具无法调用此端点——它只在 Claude Code harness 层执行。
      parameters:
        - in: query
          name: tool_name
          description: 被调用的工具名称
          required: true
          schema:
            type: string
        - in: query
          name: description
          description: agent description 字段
          required: false
          schema:
            type: string
      responses:
        "0":
          description: 日志行已追加到 .git/spec-vc-subagent-sessions.log

  /commit/prepare:
    post:
      summary: 生成 manifest + 写入 prepare 时间戳
      description: |
        Spec 检查 → manifest → .git/spec-vc-manifest.json + .git/spec-vc-prepare-ts
        不写 token。
      responses:
        "0":
          description: manifest 和 prepare-ts 已写入
        "1":
          description: Spec 未就绪或无 staged changes

  /commit/submit:
    post:
      summary: TTY-bound 终审提交
      description: |
        TTY 检测 → manifest 交叉比对 → verify → 交互确认 → basic token → git commit
      responses:
        "0":
          description: 提交成功
        "1":
          description: 阻塞原因经 stderr 输出

  /commit-msg-hook:
    post:
      summary: 校验提交通路
      description: |
        校验链: SPEC_VC_BYPASS? → token 存在+未过期 → subagent-sessions.log 存在+非空 → ADR 引用
      responses:
        "0":
          description: 放行
        "1":
          description: 阻塞原因经 stderr 输出

---

## 数据形状
<!-- 本区块内容将同步到 schema.json -->

{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ADR-009 subagent session tracking data shapes",
  "type": "object",
  "properties": {
    "CommitToken": {
      "type": "object",
      "description": ".git/spec-vc-commit-token——basic 2-line 格式",
      "properties": {
        "uuid": {
          "type": "string",
          "description": "一次性 token 唯一标识（32 字符 hex）"
        },
        "timestamp": {
          "type": "integer",
          "description": "Unix 时间戳，300 秒过期"
        }
      },
      "required": ["uuid", "timestamp"]
    },
    "SubagentSessionEntry": {
      "type": "object",
      "description": ".git/spec-vc-subagent-sessions.log 单行格式",
      "properties": {
        "timestamp": {
          "type": "string",
          "format": "date-time",
          "description": "ISO 8601 时间戳"
        },
        "tool_name": {
          "type": "string",
          "description": "被调用的工具名称，如 Agent"
        },
        "description": {
          "type": "string",
          "description": "agent 描述文本"
        }
      },
      "required": ["timestamp", "tool_name"]
    },
    "PrepareTimestamp": {
      "type": "object",
      "description": ".git/spec-vc-prepare-ts 格式",
      "properties": {
        "timestamp": {
          "type": "string",
          "format": "date-time",
          "description": "prepare 命令执行时的 ISO 8601 时间戳"
        }
      },
      "required": ["timestamp"]
    }
  }
}

---

## 行为规则
<!-- 本区块内容将同步到 behavior.feature -->

Feature: PostToolUse hook subagent 调用追踪与 commit 门禁
  作为 spec-vc 维护者
  当 AI 完成代码修改和 subagent 审计后
  我需要 commit-msg hook 验证 subagent 审计确实发生过
  以确保每次提交都经过了审计流程

  Scenario: 有 subagent session 记录时提交通过
    Given .git/spec-vc-commit-token 存在且未过期
      And .git/spec-vc-subagent-sessions.log 存在且非空
      And commit message 含合法 [ADR-NNN] 引用
    When git commit 触发 commit-msg hook
    Then hook 消费 token
      And exit code 为 0

  Scenario: 无 subagent session 记录时提交阻塞
    Given .git/spec-vc-commit-token 存在且未过期
      And .git/spec-vc-subagent-sessions.log 不存在或为空
      And commit message 含合法 [ADR-NNN] 引用
    When git commit 触发 commit-msg hook
    Then hook 输出 "未找到 subagent 审计记录"
      And exit code 为 1
      And token 未被消费

  Scenario: PostToolUse hook 记录 Agent 调用
    Given Claude Code 触发 PostToolUse hook
      And 被调用的工具为 Agent
    When hook 执行 spec-vc hook post-tool-use --tool-name "Agent" --description "..."
    Then .git/spec-vc-subagent-sessions.log 追加一行
      And 行格式为 "ISO时间戳 | Agent | description"

  Scenario: SPEC_VC_BYPASS 跳过 subagent session 检查
    Given .git/spec-vc-commit-token 不存在
      And .git/spec-vc-subagent-sessions.log 不存在
      And 环境变量 SPEC_VC_BYPASS="hotfix"
      And commit message 含合法 [ADR-NNN] 引用
    When git commit 触发 commit-msg hook
    Then hook 跳过 token 校验和 subagent session 检查
      And ADR 引用校验仍然执行
      And exit code 为 0

  Scenario: prepare 写入时间戳
    Given 仓库中有 staged files
      And 所有 Spec 已就绪
    When AI 运行 spec-vc commit prepare
    Then .git/spec-vc-prepare-ts 被写入当前 ISO 时间戳
      And .git/spec-vc-commit-token 不存在

  Scenario: submit 检查 subagent session 后写 token
    Given 用户在真实 TTY 终端
      And .git/spec-vc-manifest.json 与当前状态一致
      And verify 全部通过
      And .git/spec-vc-subagent-sessions.log 存在且非空
    When 用户运行 spec-vc commit submit
    Then basic token（uuid+timestamp 两行）被写入
      And git commit 被执行

---

## 非目标

### 5.1 明确排除的功能
- hash chain token（SHA-256 计算、5 行格式、哈希比对）
- OOB 人类确认通道
- termios 加密 TTY 确认
- 双触发通道
- subagent session log rotation
- 关键词过滤（全量记录所有 Agent 调用）

### 5.2 未来可能扩展
- subagent session log 按日期 rotation
- session log 与 prepare-ts 时间戳交叉比对（仅接受 prepare 之后的记录）

---

## 测试策略

### 8.1 验收标准
所有 6 个 Gherkin Scenario 在 pytest 中通过。

### 8.2 测试用例
| 测试类型 | 覆盖范围 | 优先级 |
|----------|----------|--------|
| 单元测试 | post-tool-use 命令记录日志 | P0 |
| 单元测试 | commit-msg hook subagent session 检查 | P0 |
| 单元测试 | SPEC_VC_BYPASS 跳过 session 检查 | P0 |

---

## 日志实现

### 9.1 日志级别规范
纯文本 append，不引入日志框架。

### 9.2 必须记录的事件
| 事件 | 写入位置 | 必须字段 | 说明 |
|------|----------|----------|------|
| Agent 调用 | `.git/spec-vc-subagent-sessions.log` | timestamp, tool_name, description | 每次 Agent 工具调用追加一行 |

### 9.3 日志格式
```
2026-05-03T17:20:47+08:00 | Agent | 审计 subagent
```
管道符分隔，timestamp 为 ISO 8601 含时区。
