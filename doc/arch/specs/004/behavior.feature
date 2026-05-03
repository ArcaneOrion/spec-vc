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
