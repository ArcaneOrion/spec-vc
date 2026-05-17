```gherkin
Feature: audit 证据通过 anchor 与 staged 内容绑定

  Background:
    Given ADR-013 的'空 description 跳过写日志'规则保持有效
    And ADR-016 的'CLI 参数优先 + stdin JSON fallback'规则保持有效

  Rule: commit prepare 生成并写入 anchor
    Scenario: [ADR-NNN] 场景
      Given staged 区有变更
      And commit message subject 含 [ADR-017]
      When 执行 spec-vc commit prepare --message "...[ADR-017]"
      Then .git/spec-vc-audit-anchor 存在
      And 内容匹配正则 ^ADR-017@[0-9a-f]{12}$
      And stdout 包含 "audit-anchor: ADR-017@..."
      And exit code 为 0

    Scenario: [ADR-none] 场景
      Given staged 区有变更
      And commit message subject 含 [ADR-none]
      When 执行 spec-vc commit prepare --message "...[ADR-none]"
      Then .git/spec-vc-audit-anchor 存在
      And 内容匹配正则 ^ADR-none@[0-9a-f]{12}$
      And exit code 为 0

  Rule: anchor 对 staged 内容变化敏感
    Scenario: 同 staged 内容生成相同 anchor
      Given staged 状态 S
      When 两次执行 commit prepare 不修改 staged
      Then 两次生成的 anchor 相同

    Scenario: staged 内容变化时 anchor 变化
      Given commit prepare 生成 anchor A
      When AI 修改文件后 git add 该文件
      And 再次执行 commit prepare
      Then 新 anchor B != A

  Rule: PostToolUse hook 对 PostToolUseFailure 事件守卫
    Scenario: harness 触发 PostToolUseFailure
      Given stdin JSON 中 hook_event_name 为 "PostToolUseFailure"
      When 执行 spec-vc hook post-tool-use
      Then 日志无新增
      And exit code 为 0

    Scenario: harness 触发常规 PostToolUse
      Given stdin JSON 中 hook_event_name 为 "PostToolUse"
      And tool_name 为 "Agent"
      And tool_input.description 为 "audit ADR-017@a3f7c891b2d4"
      When 执行 spec-vc hook post-tool-use
      Then 日志追加一行包含 description 内容
      And exit code 为 0

  Rule: commit-msg hook 校验 anchor 绑定（[ADR-NNN]）
    Scenario: 末行 description 含 anchor → 放行
      Given .git/spec-vc-audit-anchor 内容为 "ADR-017@a3f7c891b2d4"
      And session log 末行 description 为 "audit ADR-017@a3f7c891b2d4 ..."
      And commit message subject 含 [ADR-017]
      When git commit 触发 commit-msg hook
      Then exit code 为 0

    Scenario: 末行 description 不含 anchor → 阻塞
      Given .git/spec-vc-audit-anchor 内容为 "ADR-017@a3f7c891b2d4"
      And session log 末行 description 为 "audit something else"
      And commit message subject 含 [ADR-017]
      When git commit 触发 commit-msg hook
      Then exit code 非 0
      And stderr 输出当前 anchor 与"audit description 必须包含 anchor"

    Scenario: anchor 文件缺失 + [ADR-NNN] → 阻塞
      Given .git/spec-vc-audit-anchor 不存在
      And commit message subject 含 [ADR-017]
      When git commit 触发 commit-msg hook
      Then exit code 非 0
      And stderr 提示"未走 commit prepare 生成 anchor"

  Rule: [ADR-none] 路径跳过 anchor 检查
    Scenario: [ADR-none] 即使 anchor 文件不存在也放行
      Given .git/spec-vc-audit-anchor 不存在
      And commit message subject 含 [ADR-none] 且符合豁免规则
      When git commit 触发 commit-msg hook
      Then exit code 为 0（豁免规则已量化卡控，无需 anchor 二次保护）

  Rule: SPEC_VC_BYPASS 跳过 anchor 检查
    Scenario: 设置 BYPASS 后即使无 anchor 也放行
      Given .git/spec-vc-audit-anchor 不存在
      And 环境变量 SPEC_VC_BYPASS="hotfix"
      And commit message subject 含 [ADR-017]
      When git commit 触发 commit-msg hook
      Then exit code 为 0
      And bypass 日志已写入
```

---
