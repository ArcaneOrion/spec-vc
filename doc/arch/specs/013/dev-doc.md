# Spec-013: hook 校验链补完：adr_id 路由与 session log 时间戳新鲜度

- **ADR**: ADR-013
- **Status**: Draft
- **Author**: arcaneorion
- **Date**: 2026-05-08
- **Version**: 0.1.0

---

## 概述

ADR-011/012 收尾时 hook 校验链暴露两个补完点：

1. `hooks._load_active_stage(adr_dir, adr_id)` 函数体未使用 `adr_id`——永远读 `_active.md` 的 stage，与传入 ADR 无关；commit 引用 `[ADR-X]` 而 active 是 ADR-Y 时校验对象错位。
2. `commit-msg hook` 仅以 `session log 非空` 作审计证据；今天 Agent API 500 失败仍写空 description 行（5 行中 3 行空），hook 形式上仍通过——回到 ADR-008/011 想堵的"仪式性"问题。

本 Spec 同时补完两点：(a) 函数按 `adr_id` 路由查 stage；(b) commit-msg hook 增加 session log 时间戳新鲜度检查；(c) PostToolUse hook 跳过空 description 写入。

**包含**:
- `hooks._load_active_stage` → `_load_stage_for_adr(adr_dir, adr_id)` 行为重写
- `commit.check_session_log_freshness(repo_root)` 新增
- `commit-msg hook` 在 `check_subagent_session` 之后追加 freshness 检查
- `run_post_tool_use` 当 description 为空时跳过写日志
- `cmd_commit_prepare` 输出微调（"session log 非空且时间戳新鲜"）

**不包含**:
- 并行 active change 支持（仍是单 active 约束）
- description 内容质量校验（不查具体审计内容）
- 其他校验项语义变更
- _active.md 结构变更

---

## 接口契约

```yaml
openapi: "3.0.3"
info:
  title: spec-vc hook validation chain v2
  version: "0.1.0"
  description: |
    commit-msg hook 与 PostToolUse hook 校验链的语义补完。
    不对外暴露 HTTP 接口，以函数返回值/副作用/退出码表达。
paths:
  /internal/load-stage-for-adr:
    post:
      summary: 按 adr_id 路由读取变更 stage
      description: |
        替代旧的 _load_active_stage（参数 adr_id 被忽略）。
        active 匹配 adr_id → 用 active.stage；
        active 不匹配 → 从 plans/ADR-{adr_id}-plan-*.md 取编号最大读 Stage 字段；
        ADR 无 plan 文件 → 返回 None（流程已结束，不阻塞）。
      responses:
        "200":
          description: 返回 stage 字符串或 None
  /internal/check-session-log-freshness:
    post:
      summary: 检查 session log 末行时间戳是否晚于 commit-msg 写入时间
      description: |
        commit-msg hook 在 check_subagent_session 通过后调用。
        要求 session log 末行时间戳 > .git/spec-vc-commit-msg mtime。
        commit-msg 文件不存在（用户未走 prepare）则跳过该检查（保留旁路）。
      responses:
        "200":
          description: 新鲜或文件不存在（跳过），放行
        "422":
          description: 末行时间戳早于 commit-msg mtime，阻塞
  /internal/post-tool-use-hook:
    post:
      summary: 跳过空 description 写入
      description: |
        当 CLAUDE_TOOL_DESCRIPTION 为空（典型场景：Agent 调用失败、上游 API 错误）
        时，不向 session log 追加行，避免空行污染 + 防仪式性。
      responses:
        "200":
          description: 写入成功或被跳过
```

---

## 数据形状

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "session-log-freshness-contract",
  "type": "object",
  "required": ["commit_msg_mtime", "log_last_line_ts", "decision"],
  "properties": {
    "commit_msg_mtime": {
      "type": ["string", "null"],
      "format": "date-time",
      "description": ".git/spec-vc-commit-msg 文件的 mtime；不存在时为 null（freshness 检查跳过）"
    },
    "log_last_line_ts": {
      "type": ["string", "null"],
      "format": "date-time",
      "description": ".git/spec-vc-subagent-sessions.log 末行时间戳；解析失败时为 null"
    },
    "decision": {
      "type": "string",
      "enum": ["pass", "block", "skip"],
      "description": "pass=末行 > mtime；block=末行 ≤ mtime；skip=commit-msg 不存在"
    }
  },
  "examples": [
    {
      "commit_msg_mtime": "2026-05-08T13:00:00+08:00",
      "log_last_line_ts": "2026-05-08T13:05:00+08:00",
      "decision": "pass"
    },
    {
      "commit_msg_mtime": "2026-05-08T13:00:00+08:00",
      "log_last_line_ts": "2026-05-08T11:30:00+08:00",
      "decision": "block"
    },
    {
      "commit_msg_mtime": null,
      "log_last_line_ts": "2026-05-08T11:30:00+08:00",
      "decision": "skip"
    }
  ]
}
```

---

## 行为规则

```gherkin
Feature: hook 校验链补完

  Rule: _load_stage_for_adr 在 active 匹配时使用 active.stage
    Given _active.md 的 ADR 字段为 ADR-013
    And _active.md 的 Stage 字段为 implement-ready
    When 调用 _load_stage_for_adr(adr_dir, "013")
    Then 返回 "implement-ready"

  Rule: _load_stage_for_adr 在 active 不匹配时回退到 plan 文件
    Given _active.md 的 ADR 字段为 ADR-013
    And plans/ADR-011-plan-001.md 中 Stage 字段为 close
    When 调用 _load_stage_for_adr(adr_dir, "011")
    Then 返回 "close"

  Rule: _load_stage_for_adr 在 ADR 无 plan 时返回 None
    Given ADR-099 不存在 plans/ADR-099-plan-*.md
    And active 是其他 ADR
    When 调用 _load_stage_for_adr(adr_dir, "099")
    Then 返回 None

  Rule: _load_stage_for_adr 在多个 plan 时取编号最大
    Given plans/ADR-013-plan-001.md Stage=close
    And plans/ADR-013-plan-002.md Stage=plan
    And active 不匹配 ADR-013
    When 调用 _load_stage_for_adr(adr_dir, "013")
    Then 返回 "plan"

  Rule: freshness 检查放行新鲜审计
    Given .git/spec-vc-commit-msg mtime 为 T0
    And .git/spec-vc-subagent-sessions.log 末行时间戳为 T1
    And T1 > T0
    When commit-msg hook 调用 check_session_log_freshness
    Then 不抛异常，放行

  Rule: freshness 检查阻塞陈旧审计
    Given .git/spec-vc-commit-msg mtime 为 T0
    And .git/spec-vc-subagent-sessions.log 末行时间戳为 T1
    And T1 ≤ T0
    When commit-msg hook 调用 check_session_log_freshness
    Then 抛 ValidationError
    And 错误消息包含可执行指引和 SKILL.md 引用

  Rule: freshness 检查在无 commit-msg 时跳过
    Given .git/spec-vc-commit-msg 不存在
    When commit-msg hook 调用 check_session_log_freshness
    Then 不抛异常（用户未走 prepare 直接 commit，保留旁路）

  Rule: PostToolUse hook 跳过空 description
    Given Agent 工具调用 description 参数为空字符串
    When 调用 run_post_tool_use(tool_name="Agent", description="")
    Then .git/spec-vc-subagent-sessions.log 不被追加新行

  Rule: PostToolUse hook 仍写入有效 description
    Given Agent 工具调用 description 为非空字符串
    When 调用 run_post_tool_use(tool_name="Agent", description="audit X")
    Then .git/spec-vc-subagent-sessions.log 末行包含 "audit X"

  Rule: SPEC_VC_BYPASS 旁路 freshness 检查
    Given SPEC_VC_BYPASS 环境变量非空
    When 触发 commit-msg hook
    Then check_subagent_session 和 check_session_log_freshness 都被跳过

  Scenario: 完整提交链路 - 真实 Agent 调用通过
    Given 用户运行 spec-vc commit prepare
    And Agent 工具被调用并成功（description 非空）
    When 用户运行 git commit
    Then commit-msg hook 通过 freshness 检查
    And commit 完成

  Scenario: 完整提交链路 - 仪式性调用被阻塞
    Given 用户运行 spec-vc commit prepare（写入 commit-msg）
    And session log 仅含历史行（时间戳早于 commit-msg mtime）
    And 用户未触发新的 Agent 调用
    When 用户运行 git commit
    Then commit-msg hook 被 freshness 检查阻塞
    And 错误消息提示需要执行新的 subagent 审计
```

---

## 非目标

- 不做并行 active change（仍是单 active 约束）
- 不查 description 内容质量
- 不改其他校验项语义（ADR 引用、Spec 完整性等不变）
- 不引入 PreToolUse hook
- 不改 _active.md 结构

---

## 测试策略

验收标准:
- `_load_stage_for_adr` 三场景全覆盖（active 匹配 / fallback / 无 plan）
- `check_session_log_freshness` 三场景全覆盖（新鲜 / 陈旧 / 无 commit-msg）
- `run_post_tool_use` 两场景（空 description 跳过 / 非空写入）
- `SPEC_VC_BYPASS` 同时旁路 session 检查与 freshness 检查
- 新增约 6 个 pytest 用例；现有 78 个测试不回退（合计 ≥ 84 通过）

测试用例覆盖:
| 测试 | 验证规则 |
|------|---------|
| `test_load_stage_for_adr_uses_active_when_match` | active 匹配 |
| `test_load_stage_for_adr_falls_back_to_plan` | active 不匹配 fallback |
| `test_load_stage_for_adr_returns_none_when_no_plan` | 无 plan |
| `test_freshness_passes_when_log_newer_than_commit_msg` | 新鲜放行 |
| `test_freshness_blocks_when_log_older_than_commit_msg` | 陈旧阻塞 |
| `test_freshness_skips_when_no_commit_msg` | 无 commit-msg 跳过 |
| `test_post_tool_use_skips_empty_description` | 空 description 跳过 |
| `test_bypass_skips_freshness_check` | bypass 旁路 |

---

## 日志实现

- session log（`.git/spec-vc-subagent-sessions.log`）：仅记录非空 description 的 Agent 调用，行格式 `{ISO时间戳} | Agent | {description}` 不变
- bypass log（`.git/spec-vc-bypass.log`）：行为不变
- 阻塞消息输出到 stderr，不写日志文件
- freshness 检查不产生新日志事件，仅做读取与比较

---

## References

- **ADR**: ADR-013
- **Related Specs**: Spec-012（门禁消息可执行指引）
- **External**: 无
