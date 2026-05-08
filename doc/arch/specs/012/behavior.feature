```gherkin
Feature: 门禁消息包含可执行指引

  Rule: 所有门禁阻塞消息必须包含可执行指引
    Given 任何门禁检查失败
    When 输出阻塞消息
    Then 消息必须包含阻塞原因
    And 消息必须包含可执行的下一步操作（含具体 CLI 命令）
    And 消息末尾必须包含 "详细流程请查看 SKILL.md 检查正确流程"

  Rule: subagent session 缺失时提供审计指引
    Given .git/spec-vc-subagent-sessions.log 不存在或为空
    When commit-msg hook 阻塞提交
    Then 消息包含 "使用 Agent 工具执行代码审查/测试验证"
    And 消息包含 "PostToolUse hook 会自动记录审计过程"
    And 消息包含 "spec-vc init"

  Rule: plan stage 不满足时提供推进指引
    Given active change stage 不在 implement-ready/validate/close 中
    When commit-msg hook 阻塞提交
    Then 消息包含 "spec-vc change validate --phase pre --content"

  Rule: Spec 未完成时提供创作指引
    Given ADR 关联的 Spec dev-doc.md 有未填写区块或形式化文件仍为骨架
    When commit-msg hook 阻塞提交
    Then 消息包含 "spec-vc spec new"
    And 消息包含 "spec-vc spec formalize"

  Rule: validate --phase pre 检查 clarify 完整性
    Given active change stage 为 discover 或 clarify
    When 运行 change validate --phase pre
    Then 返回非零退出码
    And stderr 输出包含 clarify 完成指引

  Rule: validate --phase pre 检查 ADR→Spec 关联
    Given ADR 无关联 Spec
    And 变更涉及代码路径
    When 运行 change validate --phase pre
    Then stderr 输出包含 Spec 创作协议指引

  Rule: Spec 编号与 ADR 编号对齐
    Given 运行 spec new --adr ADR-012
    And Spec-012 目录不存在
    When 创建 Spec
    Then Spec 编号为 012

  Rule: Spec 编号冲突时顺延
    Given 运行 spec new --adr ADR-012
    And Spec-012 目录已存在
    When 创建 Spec
    Then Spec 编号为 next_spec_id 计算的下一个可用编号

  Rule: ADR 创建前检查编号连续性
    Given ADR 编号存在空洞
    When 运行 adr new
    Then stderr 输出警告包含 "编号存在空洞"
    And 仍然创建下一个最大编号的 ADR

  Scenario: commit prepare 输出描述新流程
    Given 存在 staged changes 且 Spec 就绪检查通过
    When 运行 commit prepare
    Then 输出包含 "subagent 审计后直接 git commit"
    And 包含 "commit-msg hook 会自动校验"
    And 包含 "SKILL.md"
```

---
