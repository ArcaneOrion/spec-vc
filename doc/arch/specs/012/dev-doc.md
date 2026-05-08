# Spec-012: 门禁消息增强：失败时返回可执行指引

- **ADR**: ADR-012
- **Status**: Draft
- **Author**: arcaneorion
- **Date**: 2026-05-08
- **Version**: 0.1.0

---

## 概述

门禁阻塞消息从功能性描述改为可执行指引：每条阻塞消息附带"下一步"操作步骤和 SKILL.md 引用。增加 `change validate --phase pre` 的 clarify 完整性检查和 ADR→Spec 关联检查。Spec 编号与 ADR 编号对齐。ADR 创建前检查编号连续性。

**包含**:
- commit-msg hook 错误消息增强（5 处）
- `change validate --phase pre` 增强（clarify 检查 + Spec 关联检查）
- `commit prepare` 输出消息改写
- Spec 编号与 ADR 编号对齐（`spec new --adr ADR-012` → Spec-012）
- ADR 创建前编号连续性检查

**不包含**:
- PreToolUse hook（不变）
- _active.md 结构变更（不变）
- SKILL.md 流程本身变更（不变）

---

## 接口契约

```yaml
openapi: "3.0.3"
info:
  title: spec-vc gate messages
  version: "0.1.0"
  description: |
    commit-msg hook 和 change validate --phase pre 的阻塞/放行契约。
    不对外暴露 HTTP 接口，以退出码和 stderr 输出表达。
paths:
  /internal/commit-msg-hook:
    post:
      summary: commit-msg hook 校验
      description: |
        git commit 时调用，校验链：bypass → session log → ADR 引用 → plan stage → Spec 完整性。
        退出码 0=放行，1=阻塞（stderr 输出原因+指引）。
      responses:
        "200":
          description: 放行
        "422":
          description: 阻塞，stderr 包含原因和可执行指引
  /internal/validate-pre:
    post:
      summary: change validate --phase pre 检查
      description: |
        检查 clarify 完整性、ADR→Spec 关联、Spec 就绪。
        返回非零时 stderr 包含分步指引。
      responses:
        "200":
          description: 检查通过
        "422":
          description: 检查未通过
```

---

## 数据形状

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "gate-block-message",
  "type": "object",
  "required": ["reason", "next_steps", "reference"],
  "properties": {
    "reason": {
      "type": "string",
      "description": "阻塞原因的功能性描述"
    },
    "next_steps": {
      "type": "array",
      "items": {"type": "string"},
      "description": "可执行的下一步操作列表，包含具体 CLI 命令"
    },
    "reference": {
      "type": "string",
      "const": "详细流程请查看 SKILL.md 检查正确流程",
      "description": "所有门禁消息必须包含此引用"
    }
  },
  "examples": [
    {
      "reason": "未找到 subagent 审计记录",
      "next_steps": ["使用 Agent 工具执行代码审查/测试验证", "PostToolUse hook 会自动记录到 .git/spec-vc-subagent-sessions.log", "如未配置 hook，运行 spec-vc init 重新初始化"],
      "reference": "详细流程请查看 SKILL.md 检查正确流程"
    }
  ]
}
```

---

## 行为规则

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

## 非目标

- 不做代码级语义一致性检查
- 不做 PreToolUse hook 拦截
- 不改变 SKILL.md 流程本身

---

## 测试策略

验收标准:
- 所有门禁阻塞消息包含"下一步"指引和 SKILL.md 引用
- `change validate --phase pre` 在 clarify 未完成时阻塞
- Spec 编号随 ADR 编号对齐，冲突时顺延
- ADR 创建前输出编号空洞警告

---

## 日志实现

门禁阻塞消息输出到 stderr，不写日志文件。bypass 事件写入 .git/spec-vc-bypass.log（已有）。

---

## References

- **ADR**: ADR-012
- **Related Specs**: 无