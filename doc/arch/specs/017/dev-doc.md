# Spec-017: 审计证据由间接代理升级为 anchor 内容绑定

- **ADR**: ADR-017
- **Status**: Draft
- **Author**: arcaneorion
- **Date**: 2026-05-17
- **Version**: 0.1.0

---

## 概述

ADR-013 用「description 非空」做 audit 真实发生的代理证据；ADR-016 修复 stdin 传值后该假设的脆弱性显形为两个漏洞：

- **H1（间接证据脆弱）**：`description` 来自 `tool_input.description`（主 AI 写的入参），不是 `tool_response`。Agent 内部业务失败时 Claude Code 仍触发 `PostToolUse`（非 `PostToolUseFailure`），hook 仍写日志。
- **H2（一次审计跨多 commit 复用）**：commit-msg 校验只查「session log 末行时间戳 > commit-msg mtime」，不查内容；prepare 一次后第二个 commit 不重 prepare 就能复用同一 audit 行。

本 Spec 把代理证据升级为**内容绑定**：

- `spec-vc commit prepare` 计算 anchor = `ADR-XXX@<sha12>`（`sha12` = `sha256(git diff --cached --no-renames --no-color)` 前 12 字符），写入 `.git/spec-vc-audit-anchor` + stdout 提示 AI 复述。
- `commit-msg` hook 新增 `check_anchor_binding`：要求 session log 末行 `description` 包含 anchor 子串。
- `PostToolUse` hook 新增 `hook_event_name == "PostToolUseFailure"` 守卫（hygiene；Agent 业务失败大多仍走 PostToolUse 不命中此分支，但 harness 中断 / 显式失败场景下命中）。

设计哲学：spec-vc 不是"防作弊"工具——AI 可以伪造任何内容。Spec-017 的目标是让通过门禁的最小成本至少**等于读一次 staged diff**，从而把"作弊比诚实更便宜"的成本曲线翻过来。

**包含**:
- `commit.compute_audit_anchor(repo_root, adr_token) -> str`
- `commit.write_audit_anchor(repo_root, anchor) -> Path`
- `commit.check_anchor_binding(repo_root, adr_token) -> None`（hook 子检查）
- `hooks.run_post_tool_use` 新增 `hook_event_name == "PostToolUseFailure"` 守卫
- `hooks.run_commit_msg` 在 freshness 检查后调用 `check_anchor_binding`
- `cli.cmd_commit_prepare` 在写 commit-msg 后写 anchor 文件 + stdout 提示
- `SPEC_VC_BYPASS` 跳过 anchor 检查（与现有逃生口语义一致）

**不包含**:
- 不改 ADR-013 的"空 description 跳过写日志"逻辑
- 不改 `[ADR-none]` 豁免路径（其量化卡控已足够）
- 不改 `SPEC_VC_BYPASS` 行为或日志
- 不尝试从 `tool_response` 内容解析业务成功 / 失败（Claude Code 不提供契约级字段）
- 不引入服务端 / 远端校验
- 不限制 anchor 算法可变（未来如发现 `git diff --cached` 稳定性问题，可改为 `git write-tree` 而契约不变）

---

## 接口契约

```yaml
openapi: "3.0.3"
info:
  title: spec-vc audit anchor binding (ADR-017)
  version: "0.1.0"
  description: |
    commit prepare 生成 anchor + commit-msg hook 校验 anchor 子串绑定 session log 末行。
    不对外暴露 HTTP，以函数副作用 + 退出码表达。
paths:
  /internal/commit-prepare/anchor:
    post:
      summary: 计算并写入 .git/spec-vc-audit-anchor
      description: |
        commit prepare 在写 commit-msg 之后调用：
        1. 从 commit message subject 提取 ADR token（[ADR-NNN] 或 [ADR-none]）
        2. 计算 staged 内容指纹 sha12 = sha256(git diff --cached --no-renames --no-color)[:12]
        3. 拼接 anchor = "<adr_token>@<sha12>"（去除括号；如 "ADR-017@a3f7c891b2d4"）
        4. 写入 .git/spec-vc-audit-anchor（单行，无 trailing newline）
        5. stdout 输出 "audit-anchor: <anchor>" 提示 AI 复述
      responses:
        "0":
          description: anchor 已写入；调用方 stdout 含 anchor
  /internal/hook/post-tool-use/with-failure-guard:
    post:
      summary: PostToolUse hook + PostToolUseFailure 守卫
      description: |
        在 ADR-016 stdin JSON 优先逻辑之前增加：
        若 payload.hook_event_name == "PostToolUseFailure" → return 0 直接跳过
        其他事件按 ADR-016 路径处理。
        注：Claude Code 中 Agent 业务失败通常仍触发 PostToolUse，本守卫仅命中 harness 显式失败场景（如调用被中断）。
      responses:
        "0":
          description: 已跳过或已写日志
  /internal/commit-msg/anchor-binding:
    post:
      summary: 校验 session log 末行 description 含 anchor 子串
      description: |
        commit-msg hook 在 check_session_log_freshness 通过后调用：
        - SPEC_VC_BYPASS 非空 → 跳过本检查
        - [ADR-none] → 跳过（豁免规则已量化卡控）
        - [ADR-NNN]:
            - 读 .git/spec-vc-audit-anchor:
                * 文件不存在 → 阻塞（"未走 commit prepare 生成 anchor"）
                * 文件存在:
                    - 读 session log 末行的 description 字段（管道分隔第三段）
                    - description 含 anchor 子串 → 放行
                    - 不含 → 阻塞（输出当前 anchor 与可执行指引）
      responses:
        "0":
          description: 放行
        "1":
          description: 阻塞（不含 anchor / 缺 anchor 文件）
```

---

## 数据形状

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "audit-anchor",
  "description": "spec-vc commit prepare 写入 .git/spec-vc-audit-anchor 的内容契约。单行明文，无 trailing newline，便于直接读取与字符串包含比较。",
  "type": "object",
  "required": ["adr_token", "diff_sha12", "anchor_string"],
  "properties": {
    "adr_token": {
      "type": "string",
      "pattern": "^ADR-(\\d{3,}|none)$",
      "description": "本次 commit subject 提取的 ADR token，不含方括号"
    },
    "diff_sha12": {
      "type": "string",
      "pattern": "^[0-9a-f]{12}$",
      "description": "sha256(git diff --cached --no-renames --no-color) 前 12 个十六进制字符；staged 内容变化时随之变化"
    },
    "anchor_string": {
      "type": "string",
      "pattern": "^ADR-(\\d{3,}|none)@[0-9a-f]{12}$",
      "description": "实际写入文件的字符串：'<adr_token>@<diff_sha12>'"
    }
  },
  "examples": [
    {
      "adr_token": "ADR-017",
      "diff_sha12": "a3f7c891b2d4",
      "anchor_string": "ADR-017@a3f7c891b2d4"
    },
    {
      "adr_token": "ADR-none",
      "diff_sha12": "0000abcd1234",
      "anchor_string": "ADR-none@0000abcd1234"
    }
  ]
}
```

---

## 行为规则

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

## 非目标

- 不修复 ADR-013 时未发现的更深层「AI 既是运动员又是裁判」哲学问题——所有内容仍由 AI 写，spec-vc 只能提高作弊成本不能防作弊
- 不在 Claude Code 层面区分 Agent 业务失败 vs 真实成功（契约不允许）
- 不要求 anchor 算法跨 git 版本完全确定——只要同一仓库同一 staged 同一 git 版本生成稳定即可
- 不引入 `subagent_type` / `prompt` 等额外字段的解析（仅 `tool_name` / `tool_input.description` / `hook_event_name`）
- 不向 session log 写入除 hook 原有格式外的字段（保持向后兼容旧脚本）

---

## 测试策略

```gherkin
Scenario Outline: 单元测试覆盖矩阵
  Given 输入条件 "<input>"
  When 调用相关函数
  Then 行为为 "<expected>"

  Examples:
    | input                                                       | expected                                                     |
    | compute_audit_anchor 两次同 staged                          | 返回相同 anchor                                              |
    | compute_audit_anchor staged 变化                            | 返回不同 anchor                                              |
    | compute_audit_anchor token=ADR-017                          | anchor 形如 ADR-017@<sha12>                                  |
    | compute_audit_anchor token=ADR-none                         | anchor 形如 ADR-none@<sha12>                                 |
    | write_audit_anchor                                          | 文件存在且内容是单行 anchor                                  |
    | hook stdin hook_event_name=PostToolUseFailure               | 日志无新增                                                   |
    | hook stdin hook_event_name=PostToolUse + 含 anchor 的 desc  | 日志追加一行                                                 |
    | commit-msg 末行 desc 含 anchor                              | exit 0                                                       |
    | commit-msg 末行 desc 不含 anchor                            | exit 1，stderr 含 anchor                                     |
    | commit-msg anchor 文件缺 + [ADR-NNN]                        | exit 1，stderr 提示走 prepare                                |
    | commit-msg anchor 文件缺 + [ADR-none] 符合豁免              | exit 0                                                       |
    | commit-msg BYPASS=hotfix + anchor 文件缺 + [ADR-NNN]        | exit 0，bypass 日志已写                                      |
```

集成验证：

- 本 ADR-017 的实施 commit 自身就是集成验证——必须走完整新流程才能 commit 成功。
- commit prepare 必须输出 anchor；audit subagent description 必须复述 anchor；commit 通过 = 端到端工作。

回归：`uv run pytest tests/python/` 维持全过（含 ADR-016 已有的 98 用例 + 新增 ADR-017 用例）。

---

## 日志实现

- 阻塞场景的 stderr 输出**必须包含当前 anchor**——AI 看到错误后能直接复制到下次 audit description
- bypass 日志保持现有格式（`.git/spec-vc-bypass.log`）
- session log 格式不变

---

## 变更历史

| 版本 | 日期 | 作者 | 变更内容 |
|------|------|------|----------|
| 0.1.0 | 2026-05-17 | arcaneorion | 初始版本：审计代理证据升级为 anchor 内容绑定 |

---

## References

- **ADR**: ADR-017
- **Related Specs**:
  - Spec-004（已 Superseded；本 Spec 进一步推进 ADR-009 的"机制级证据"哲学）
  - Spec-013（freshness 检查与本 Spec anchor 检查共同构成内容 + 时间双绑定）
  - Spec-016（stdin JSON 输入契约——anchor 检查依赖该路径正确工作）
- **External**: [Claude Code Hooks reference - PostToolUse / PostToolUseFailure](https://code.claude.com/docs/en/hooks)
