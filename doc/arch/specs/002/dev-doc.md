# Spec-002: commit-msg hook emergency bypass 行为规则

- **ADR**: ADR-007
- **Status**: Draft
- **Author**: arcaneorion
- **Date**: 2026-04-30
- **Version**: 0.1.0

---

## 概述

### 1.1 问题陈述
spec-vc 维护者需要一个**显式、临时、留痕**的逃生口，让 ADR-006 token 门禁在 spec-vc binary 损坏 / skill 路径变更 / venv 错乱等单点故障时，仍允许 commit 通过——避免治理机制本身成为生产力阻断。

### 1.2 解决方案概述
在 `commit-msg` hook 的 token 校验之前增加一个分支：检查环境变量 `SPEC_VC_BYPASS`，非空时跳过 token 校验并向 `.git/spec-vc-bypass.log` 追加一行审计记录（fail-open，写入失败仅 stderr 警告但仍放行）。ADR 引用与豁免规则照常生效。

### 1.3 范围边界
**包含**:
- `commit-msg` hook 中的 bypass 分支与日志写入逻辑
- 错误提示信息中显式列出 bypass 用法
- pytest 三个新测试用例覆盖 bypass 路径
- README 紧急绕过段说明用法与最终兜底

**不包含**:
- 双触发通道（git config）、commit message 标记、配置项 / CLI flag、原因白名单、跨克隆审计同步——见 ADR-007 Alternatives Considered

---

## 接口契约
<!-- 本区块内容将同步到 contract.openapi.yaml；本变更非 HTTP 接口，用 OpenAPI 3.0 描述 hook 的等价调用契约 -->

openapi: 3.0.3
info:
  title: spec-vc commit-msg hook (emergency bypass extension)
  version: "0.3.1"
  description: |
    git commit-msg hook 的调用契约。本契约描述 ADR-007 引入的 bypass 行为，
    并不实际暴露 HTTP 端点——OpenAPI 在此用作行为契约的形式化载体。
paths:
  /commit-msg:
    post:
      summary: 校验 commit message 与提交通路
      description: |
        git 在 commit-msg 阶段调用本 hook。hook 以 commit message 文件路径
        为参数，环境变量 SPEC_VC_BYPASS 影响校验路径。
      parameters:
        - in: query
          name: SPEC_VC_BYPASS
          description: 非空字符串触发 emergency bypass，跳过 token 校验
          required: false
          schema:
            type: string
            minLength: 1
        - in: query
          name: message_file_path
          description: git 传入的 commit message 临时文件路径
          required: true
          schema:
            type: string
      responses:
        "0":
          description: 放行 commit（exit code 0）
        "1":
          description: 阻塞 commit（exit code 非 0），原因经 stderr 输出

---

## 数据形状
<!-- 本区块内容将同步到 schema.json；定义 bypass 输入与日志记录形状 -->

{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ADR-007 emergency bypass data shapes",
  "type": "object",
  "properties": {
    "BypassEnvironment": {
      "type": "object",
      "description": "触发 bypass 的环境变量约束",
      "properties": {
        "SPEC_VC_BYPASS": {
          "type": "string",
          "minLength": 1,
          "description": "非空字符串触发 bypass。推荐值：hotfix / ci / bisect / migration / repair。空字符串等同未设置。"
        }
      },
      "required": ["SPEC_VC_BYPASS"]
    },
    "BypassLogLine": {
      "type": "object",
      "description": ".git/spec-vc-bypass.log 单行格式（管道分隔）",
      "properties": {
        "timestamp": {
          "type": "string",
          "format": "date-time",
          "description": "ISO 8601 时间戳"
        },
        "reason": {
          "type": "string",
          "minLength": 1,
          "description": "SPEC_VC_BYPASS 环境变量原值"
        },
        "subject": {
          "type": "string",
          "description": "commit subject 行原文"
        }
      },
      "required": ["timestamp", "reason", "subject"]
    }
  }
}

---

## 行为规则
<!-- 本区块内容将同步到 behavior.feature -->

Feature: commit-msg hook emergency bypass
  作为 spec-vc 维护者
  当 token 门禁因 spec-vc binary 故障锁死时
  我希望通过显式环境变量绕过 token 校验
  以便在记录审计的前提下完成 commit

  Scenario: 设置非空 SPEC_VC_BYPASS 时跳过 token 校验
    Given commit message 含合法 [ADR-NNN] 引用
      And .git/spec-vc-commit-token 不存在或已过期
      And 环境变量 SPEC_VC_BYPASS="hotfix"
    When git commit 触发 commit-msg hook
    Then hook 跳过 token 校验
      And ADR 引用校验仍然执行
      And .git/spec-vc-bypass.log 追加一行：时间戳 | hotfix | <commit subject>
      And exit code 为 0

  Scenario: 未设置 SPEC_VC_BYPASS 时走原 token 校验
    Given commit message 含合法 [ADR-NNN] 引用
      And .git/spec-vc-commit-token 不存在
      And 环境变量 SPEC_VC_BYPASS 未设置
    When git commit 触发 commit-msg hook
    Then hook 抛出 "未找到提交 token" 错误
      And 错误信息显式列出 SPEC_VC_BYPASS=<原因> git commit 用法
      And .git/spec-vc-bypass.log 不被写入
      And exit code 非 0

  Scenario: SPEC_VC_BYPASS 为空字符串时不触发 bypass
    Given commit message 含合法 [ADR-NNN] 引用
      And .git/spec-vc-commit-token 不存在
      And 环境变量 SPEC_VC_BYPASS=""
    When git commit 触发 commit-msg hook
    Then hook 走原 token 校验路径
      And exit code 非 0

  Scenario: bypass 日志写入失败时仍放行（fail-open）
    Given 环境变量 SPEC_VC_BYPASS="repair"
      And .git/spec-vc-bypass.log 路径不可写（如 .git 只读）
    When git commit 触发 commit-msg hook
    Then hook 跳过 token 校验
      And stderr 输出 "bypass 日志写入失败" 警告
      And exit code 为 0

  Scenario: bypass 跳过 token 但不跳过 ADR 引用校验
    Given commit message 缺失 [ADR-NNN] 引用
      And 环境变量 SPEC_VC_BYPASS="hotfix"
    When git commit 触发 commit-msg hook
    Then hook 抛出 "subject 必须包含且只能包含一个 [ADR-NNN] 或 [ADR-none]" 错误
      And exit code 非 0

---

## 非目标

### 5.1 明确排除的功能
- 双触发通道（git config + 环境变量）：环境变量场景已覆盖单人 + 开源初期需求
- commit message 追加 `[BYPASS:<reason>]` 标记：审计日志已覆盖事后追溯
- 配置项 / CLI flag 永久关闭 token 门禁：违反 ADR-006 强制性
- 强制原因白名单：限制实际应急时的灵活性

### 5.2 未来可能扩展
- 团队协作场景下若需跨克隆审计，再加 commit message 标记或推送审计 log
- 若环境变量不可达场景增多，再加 git config 通路

---

## 测试策略

### 8.1 验收标准
所有 5 个 Gherkin Scenario 在 pytest 中独立通过；全量基线 91 个测试 + 新增 3 个 = 94 全部通过。

### 8.2 测试用例
| 测试类型 | 覆盖范围 | 优先级 |
|----------|----------|--------|
| 单元测试 | run_commit_msg 在 SPEC_VC_BYPASS 非空时跳过 token 校验并写日志 | P0 |
| 单元测试 | run_commit_msg 在 SPEC_VC_BYPASS 未设置时走原 token 校验 | P0 |
| 单元测试 | run_commit_msg 在日志路径不可写时仍放行（fail-open） | P0 |

### 8.3 边界条件
- SPEC_VC_BYPASS 为空字符串（视为未触发）
- SPEC_VC_BYPASS 为 1 字符（最小非空，触发）
- SPEC_VC_BYPASS 跳过 token 但 ADR 引用仍非法时仍阻塞

### 8.4 Mock 策略
不使用 mock。pytest 通过临时 git 仓库 + 真实文件系统 + 子进程调用 hook 来端到端验证。

---

## 日志实现

### 9.1 日志级别规范
本变更不引入应用级日志框架。审计日志为 hook 直接 append 的纯文本文件。

### 9.2 必须记录的事件
| 事件 | 写入位置 | 必须字段 | 说明 |
|------|----------|----------|------|
| bypass 触发 | `.git/spec-vc-bypass.log` | timestamp, reason, subject | 每次 bypass 一行 |
| bypass 日志写入失败 | stderr | 异常消息 | 不阻塞 commit |

### 9.3 日志格式
```
2026-04-30T12:34:56+08:00 | hotfix | feat(api): hotfix 401 regression [ADR-001]
```
管道符（` | `）分隔，timestamp 为 ISO 8601 含时区，reason 为 SPEC_VC_BYPASS 原值，subject 为 commit subject 行原文（不去换行外字符）。

### 9.4 敏感信息处理
不适用——commit subject 与原因字段属用户明示输入，不涉及自动采集敏感信息。

### 9.5 日志采样策略
全量记录，不采样。bypass 是低频事件。

---

## 变更历史

| 版本 | 日期 | 作者 | 变更内容 |
|------|------|------|----------|
| 0.1.0 | 2026-04-30 | arcaneorion | 初始版本：emergency bypass 行为规则 |

---

## References

- **ADR**: ADR-007
- **Related Specs**: 无（与 ADR-006 共享 commit-msg hook 行为，但 token 校验规则在 ADR-006 范围）
- **External**: git hooks 文档；ADR-006 token 门禁机制
