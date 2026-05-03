# Spec-003: TTY-bound commit prepare/submit 两阶段提交流程

- **ADR**: ADR-008
- **Status**: Draft
- **Author**: arcaneorion
- **Date**: 2026-05-03
- **Version**: 0.1.0

---

## 概述

### 1.1 问题陈述
spec-vc 维护者需要**提交通路与权限边界对齐**，因为当前 ADR-006 token 在 `spec-vc commit` 调用时即写入（早于 manifest 输出），token 仅证明"命令被调用过"，不证明审计子流程完成——AI 可在无审计时拿 token 直接 `git commit`，机制边界与权限边界错位。

### 1.2 解决方案概述
将 `spec-vc commit` 拆分为 `prepare`（AI 域，生成 manifest 不写 token）和 `submit`（用户 TTY 域，交叉比对 + verify + 写含 hash chain 的 token + 执行 git commit）。commit-msg hook 升级为校验 token 内 hash chain，确保 token 与 manifest/audit/test 报告的一致性。`SPEC_VC_BYPASS` 保留为 raw escape。

### 1.3 范围边界
**包含**:
- `spec-vc commit prepare` 命令（Spec check + manifest + commit message 草稿，不写 token）
- `spec-vc commit submit` 命令（TTY 检测 + 交叉比对 + verify + hash chain token + git commit）
- `write_commit_token` 升级为 hash chain token 格式
- commit-msg hook hash chain 校验分支
- CLI help 和错误提示更新

**不包含**:
- OOB 人类确认通道（桌面通知/手机 push）
- spec-vc 内置 Anthropic API 调用的 subagent 执行
- termios 加密 TTY 确认
- 双触发通道（git config 通路）
- 跨克隆审计同步

---

## 接口契约
<!-- 本区块内容将同步到 contract.openapi.yaml；用 OpenAPI 3.0 描述 CLI 命令等价调用契约 -->

openapi: 3.0.3
info:
  title: spec-vc commit prepare/submit (TTY-bound two-phase commit)
  version: "0.4.0"
  description: |
    spec-vc commit 的两阶段 CLI 命令契约。prepare 供 AI 调用生成 manifest，
    submit 仅由用户在真实 TTY 终端运行以完成提交。OpenAPI 在此用作 CLI 行为契约的形式化载体。
paths:
  /commit/prepare:
    post:
      summary: 生成提交 manifest 与 commit message 草稿
      description: |
        Spec 就绪检查通过后，收集 staged files 与 spec 信息，生成 manifest 写入
        .git/spec-vc-manifest.json，生成 commit message 写入 .git/spec-vc-commit-msg。
        不写入 token——本命令不产生提交权限。
      parameters:
        - in: query
          name: message
          description: commit message 完整内容（含 subject + body），可选
          required: false
          schema:
            type: string
      responses:
        "0":
          description: manifest 已生成，stdout 输出 manifest JSON
        "1":
          description: Spec 未就绪或无 staged changes，原因经 stderr 输出

  /commit/submit:
    post:
      summary: TTY-bound 终审提交
      description: |
        仅在真实 TTY 终端可执行（os.isatty 检测）。流程：
        1) 重新生成 manifest 与 .git/spec-vc-manifest.json 交叉比对
        2) 读 audit-report.json + test-report.json 跑机械化 verify
        3) 交互确认（stdin 读 Enter）
        4) 写含 hash chain 的 token 到 .git/spec-vc-commit-token
        5) 执行 git commit -F .git/spec-vc-commit-msg
        6) 删除 .git/spec-vc-commit-msg
      responses:
        "0":
          description: 提交成功，commit 已创建
        "1":
          description: 阻塞原因经 stderr 输出（非 TTY / manifest 不匹配 / verify 失败 / 无 staged changes）

  /commit-msg-hook:
    post:
      summary: commit-msg hook（hash chain 升级）
      description: |
        git commit-msg hook 的升级版校验逻辑：
        1) 检查 SPEC_VC_BYPASS 环境变量——非空时跳过 token 校验直接放行
        2) 校验 token 存在且未过期
        3) 从 token 读出 manifest_hash, audit_hash, test_hash
        4) 重新计算 .git/spec-vc-manifest.json, .git/spec-vc-audit-report.json, .git/spec-vc-test-report.json 的哈希并比对
        5) ADR 引用校验（不变）
        6) 全部通过后消费 token（删除）并放行
      parameters:
        - in: query
          name: SPEC_VC_BYPASS
          description: 非空字符串触发 emergency bypass，完全跳过 token 校验（hash chain 也不比对）
          required: false
          schema:
            type: string
            minLength: 1
      responses:
        "0":
          description: 放行 commit
        "1":
          description: 阻塞 commit，原因经 stderr 输出

---

## 数据形状
<!-- 本区块内容将同步到 schema.json -->

{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ADR-008 commit prepare/submit data shapes",
  "type": "object",
  "properties": {
    "CommitToken": {
      "type": "object",
      "description": ".git/spec-vc-commit-token 格式——由 submit 写入，hook 消费",
      "properties": {
        "uuid": {
          "type": "string",
          "format": "uuid",
          "description": "一次性 token 唯一标识"
        },
        "timestamp": {
          "type": "integer",
          "description": "Unix 时间戳，用于 300 秒过期校验"
        },
        "manifest_hash": {
          "type": "string",
          "description": ".git/spec-vc-manifest.json 内容的 SHA-256 哈希（hex）"
        },
        "audit_hash": {
          "type": "string",
          "description": ".git/spec-vc-audit-report.json 内容的 SHA-256 哈希（hex）"
        },
        "test_hash": {
          "type": "string",
          "description": ".git/spec-vc-test-report.json 内容的 SHA-256 哈希（hex）"
        }
      },
      "required": ["uuid", "timestamp", "manifest_hash", "audit_hash", "test_hash"]
    },
    "Manifest": {
      "type": "object",
      "description": ".git/spec-vc-manifest.json 格式——由 prepare 写入，submit 交叉比对",
      "properties": {
        "staged_files": {
          "type": "array",
          "items": { "type": "string" },
          "description": "git staged 文件路径列表（仓库根相对路径）"
        },
        "spec_dirs": {
          "type": "array",
          "items": { "type": "string" },
          "description": "相关 Spec ID 列表"
        },
        "audit_units": {
          "type": "array",
          "description": "审计单元列表，每个含 spec_id, formal_files, dev_doc_summary"
        },
        "test_units": {
          "type": "array",
          "description": "测试单元列表，每个含 formal_type, formal_content"
        },
        "timestamp": {
          "type": "string",
          "format": "date-time",
          "description": "prepare 时间戳"
        }
      },
      "required": ["staged_files", "spec_dirs", "audit_units", "test_units", "timestamp"]
    },
    "SubmitVerification": {
      "type": "object",
      "description": "submit 命令的输出——机械化验证结果",
      "properties": {
        "tty_check": {
          "type": "boolean",
          "description": "TTY 检测是否通过"
        },
        "manifest_match": {
          "type": "boolean",
          "description": "当前仓库状态与 prepare 时的 manifest 是否一致"
        },
        "verify_result": {
          "type": "object",
          "description": "commit verify 的 VerificationResult（覆盖/格式/物证）"
        },
        "token_written": {
          "type": "boolean",
          "description": "hash chain token 是否成功写入"
        }
      },
      "required": ["tty_check", "manifest_match", "verify_result", "token_written"]
    }
  }
}

---

## 行为规则
<!-- 本区块内容将同步到 behavior.feature -->

Feature: spec-vc commit prepare/submit 两阶段提交流程
  作为 spec-vc 维护者
  当 AI 完成代码修改需要提交时
  我需要 AI 执行 prepare 生成 manifest 并完成审计
  然后由我在终端手动执行 submit 完成最终提交
  以确保提交权限始终在用户手中

  Scenario: prepare 生成 manifest 但不写 token
    Given 仓库中有 staged files
      And 所有 Spec 已通过就绪检查
    When AI 运行 spec-vc commit prepare --message "feat(core): ... [ADR-008]"
    Then 命令 exit code 为 0
      And .git/spec-vc-manifest.json 包含 staged_files, audit_units, test_units
      And .git/spec-vc-commit-msg 包含传入的 commit message
      And .git/spec-vc-commit-token 不存在

  Scenario: prepare 在无 staged changes 时返回 0 并提示
    Given 仓库中无 staged files
    When AI 运行 spec-vc commit prepare
    Then 命令 exit code 为 0
      And stderr 输出 "(无 staged changes，无需提交)"

  Scenario: prepare 在 Spec 未就绪时阻塞
    Given 仓库中有 staged files
      And 存在未完成 formalize 的 Spec
    When AI 运行 spec-vc commit prepare
    Then 命令 exit code 为 1
      And stderr 输出 Spec 未就绪清单

  Scenario: submit 在非 TTY 环境下拒绝
    Given .git/spec-vc-manifest.json 存在且有效
      And .git/spec-vc-audit-report.json 和 .git/spec-vc-test-report.json 存在
      And stdin 不是 TTY（如管道或 Claude Code Bash 工具调用）
    When AI 运行 spec-vc commit submit
    Then 命令 exit code 为 1
      And stderr 输出 "此命令仅在真实终端中运行"

  Scenario: submit 在 manifest 被篡改后拒绝
    Given .git/spec-vc-manifest.json 存在
      And prepare 后 staged files 发生了变化（新增/删除/修改）
    When 用户在 TTY 运行 spec-vc commit submit
    Then 命令 exit code 为 1
      And stderr 输出 manifest 不匹配信息

  Scenario: submit 成功端到端流程
    Given 用户在真实 TTY 终端
      And .git/spec-vc-manifest.json 与当前仓库状态一致
      And .git/spec-vc-audit-report.json 和 .git/spec-vc-test-report.json 存在且合法
      And verify 检查全部通过
      And 用户按 Enter 确认
    When 用户运行 spec-vc commit submit
    Then 命令 exit code 为 0
      And .git/spec-vc-commit-token 被写入，内容含 uuid + timestamp + 3 个 SHA-256 hash
      And git commit 被执行，message 来自 .git/spec-vc-commit-msg
      And .git/spec-vc-commit-msg 被删除

  Scenario: commit-msg hook 校验 hash chain 通过
    Given .git/spec-vc-commit-token 存在且未过期
      And token 内 manifest_hash 与 .git/spec-vc-manifest.json 的 SHA-256 一致
      And token 内 audit_hash 与 .git/spec-vc-audit-report.json 的 SHA-256 一致
      And token 内 test_hash 与 .git/spec-vc-test-report.json 的 SHA-256 一致
      And commit message 含合法 [ADR-NNN] 引用
    When git commit 触发 commit-msg hook
    Then hook 消费 token（删除）
      And exit code 为 0

  Scenario: commit-msg hook 在报告被篡改后阻塞
    Given .git/spec-vc-commit-token 存在且未过期
      And .git/spec-vc-audit-report.json 在 token 写入后被修改
      And token 内 audit_hash 与当前 audit-report.json 的 SHA-256 不一致
    When git commit 触发 commit-msg hook
    Then hook 输出 "审计报告与 token 不匹配"
      And exit code 为 1
      And token 未被消费

  Scenario: SPEC_VC_BYPASS 跳过全部 token 校验（raw escape）
    Given .git/spec-vc-commit-token 不存在
      And 环境变量 SPEC_VC_BYPASS="hotfix"
      And commit message 含合法 [ADR-NNN] 引用
    When git commit 触发 commit-msg hook
    Then hook 跳过 token 存在性校验和 hash chain 校验
      And ADR 引用校验仍然执行
      And .git/spec-vc-bypass.log 追加一行
      And exit code 为 0

  Scenario: SPEC_VC_BYPASS 不跳过 ADR 引用校验
    Given commit message 缺失 [ADR-NNN] 引用
      And 环境变量 SPEC_VC_BYPASS="hotfix"
    When git commit 触发 commit-msg hook
    Then hook 输出 ADR 引用格式错误
      And exit code 为 1

---

## 非目标

### 5.1 明确排除的功能
- OOB 人类确认通道（桌面通知/手机 push/TTY 外通道）
- spec-vc 内置 Anthropic API key 持有和 subagent 执行
- termios 加密 TTY 确认（初始用 os.isatty）
- 双触发通道（git config 通路）
- commit message 追加 `[BYPASS:<reason>]` 标记
- 配置项永久关闭 token 门禁
- SPEC_VC_BYPASS 原因白名单

### 5.2 未来可能扩展
- 若 os.isatty 绕过实测可行，升级为 termios 加密确认
- 团队协作场景若需跨克隆审计，再加 commit message 标记
- 若 AI 自主提交需求真实出现（非本次范围），可考虑双因素确认

---

## 测试策略

### 8.1 验收标准
所有 9 个 Gherkin Scenario 在 pytest 中独立通过；新增测试 + 基线 94 = 101 全部通过。

### 8.2 测试用例
| 测试类型 | 覆盖范围 | 优先级 |
|----------|----------|--------|
| 单元测试 | cmd_commit_prepare 在 staged/空 staged/Spec 未就绪三种场景 | P0 |
| 单元测试 | cmd_commit_submit 在非 TTY 拒绝 | P0 |
| 单元测试 | cmd_commit_submit manifest 不匹配拒绝 | P0 |
| 单元测试 | cmd_commit_submit 缺 report 拒绝 | P0 |
| 单元测试 | cmd_commit_submit 端到端成功（含 TTY 模拟） | P0 |
| 单元测试 | commit-msg hook hash chain 校验通过 | P0 |
| 单元测试 | commit-msg hook 篡改报告后 hash chain 校验阻塞 | P0 |

### 8.3 边界条件
- prepare 时无 staged files（返回 0 不报错）
- submit 在 prepare 之前运行（无 .git/spec-vc-manifest.json 阻塞）
- submit 在 TTY 但 .git/spec-vc-commit-msg 缺失（阻塞）
- token 内 hash 数量不对（旧格式兼容检测）
- SPEC_VC_BYPASS 为空字符串时不触发 bypass

### 8.4 Mock 策略
不 mock。pytest 通过临时 git 仓库 + 真实文件系统 + 子进程调用验证。TTY 检测通过 monkeypatch `sys.stdin.isatty` 或 pty 模拟覆盖。

---

## 日志实现

### 9.1 日志级别规范
本变更不引入应用级日志框架。审计相关写入沿用 ADR-007 的 .git/spec-vc-bypass.log。

### 9.2 必须记录的事件
| 事件 | 写入位置 | 必须字段 | 说明 |
|------|----------|----------|------|
| bypass 触发 | `.git/spec-vc-bypass.log` | timestamp, reason, subject | 每次 bypass 一行（继承 ADR-007）|
| submit 阻塞 | stderr | 阻塞原因 | manifest 不匹配/verify 失败/非 TTY |

---

## 变更历史

| 版本 | 日期 | 作者 | 变更内容 |
|------|------|------|----------|
| 0.1.0 | 2026-05-03 | arcaneorion | 初始版本：TTY-bound prepare/submit 两阶段流程 |

---

## References

- **ADR**: ADR-008
- **Related Specs**: Spec-002（commit-msg hook emergency bypass 行为规则，本 Spec 在 token 升级后对其进行窄化修订）
- **External**: git hooks 文档；ADR-006 token 门禁机制；ADR-007 emergency bypass 机制
