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
