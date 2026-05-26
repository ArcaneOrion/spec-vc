# Spec-022: 审计模式冻结对齐文档基线

- **ADR**: ADR-022
- **Status**: Draft
- **Author**: arcaneorion
- **Date**: 2026-05-25
- **Version**: 0.1.0

---

## 概述

spec-vc 的审计模式需要冻结本次审计所依赖的对齐文档基线。现有 `review.json.anchor` 只绑定 staged diff，不能证明审计开始后 ADR、Plan 或 Spec 没有被改写。本 Spec 定义 `review.json.document_baseline` 数据契约与 commit-msg hook 的复算校验行为：review 写入基线，commit 前比较基线，若基线漂移则阻塞并要求重新 review。

范围包含：

- `spec-vc review` 生成 ADR/Plan/Spec 基线摘要。
- `.git/spec-vc-review.json` 增加向后兼容的 `document_baseline` 字段。
- `[ADR-NNN]` commit-msg hook 在非 bypass 时复算并校验基线。
- 旧 review.json 不含 `document_baseline` 时不解析失败。

范围不包含：

- 全仓库文档锁。
- 禁止用户修改 ADR/Plan/Spec；修改后必须重新 review。
- `[ADR-none]` 分支的文档基线冻结。
- 对 `context_summary` 做 hook 校验。

## 接口契约

openapi: 3.1.0
info:
  title: Spec-022 document baseline freeze
  version: 0.1.0
paths:
  /internal/review:
    post:
      summary: spec-vc review writes document_baseline into review.json
      operationId: writeReviewWithDocumentBaseline
      requestBody:
        required: true
        content:
          text/plain:
            schema:
              type: string
              description: Full commit message containing [ADR-NNN] or [ADR-none].
      responses:
        "0":
          description: review.json and commit message are written.
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ReviewRecord"
        "1":
          description: BlockingError or validation error printed to stderr.
  /internal/hook/commit-msg:
    post:
      summary: commit-msg hook verifies document_baseline for [ADR-NNN]
      operationId: verifyDocumentBaseline
      requestBody:
        required: true
        content:
          text/plain:
            schema:
              type: string
              description: Path to the git commit message file.
      responses:
        "0":
          description: Commit message and audit evidence are valid.
        "1":
          description: Baseline drift or another hook violation blocks the commit.
components:
  schemas:
    ReviewRecord:
      type: object
      required:
        - anchor
        - adr_token
        - staged_sha12
        - mode
        - verified
        - created_at
      properties:
        anchor:
          type: string
          pattern: "^(ADR-none|ADR-[0-9]{3,})@[0-9a-f]{12}$"
        adr_token:
          type: string
        staged_sha12:
          type: string
          pattern: "^[0-9a-f]{12}$"
        mode:
          type: string
          enum: [subagent, simple]
        verified:
          type: boolean
        note:
          type: string
        subagent_log_tail:
          type: [string, "null"]
        created_at:
          type: string
        context_summary:
          type: string
        document_baseline:
          $ref: "#/components/schemas/DocumentBaseline"
    DocumentBaseline:
      type: object
      required:
        - version
        - adr_token
        - files
      properties:
        version:
          type: integer
          const: 1
        adr_token:
          type: string
          pattern: "^ADR-[0-9]{3,}$"
        files:
          type: array
          items:
            $ref: "#/components/schemas/BaselineFile"
    BaselineFile:
      type: object
      required:
        - path
        - kind
        - exists
        - sha256
      properties:
        path:
          type: string
          description: Repository-relative path using forward slashes.
        kind:
          type: string
          enum: [adr, plan, spec-dev-doc, spec-formal]
        exists:
          type: boolean
        sha256:
          type: [string, "null"]
          pattern: "^[0-9a-f]{64}$"

## 数据形状

{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://spec-vc.local/specs/022/review-document-baseline.schema.json",
  "title": "ReviewRecord document_baseline extension",
  "type": "object",
  "properties": {
    "document_baseline": {
      "type": "object",
      "required": ["version", "adr_token", "files"],
      "properties": {
        "version": { "type": "integer", "const": 1 },
        "adr_token": { "type": "string", "pattern": "^ADR-[0-9]{3,}$" },
        "files": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["path", "kind", "exists", "sha256"],
            "properties": {
              "path": {
                "type": "string",
                "description": "Repository-relative path."
              },
              "kind": {
                "type": "string",
                "enum": ["adr", "plan", "spec-dev-doc", "spec-formal"]
              },
              "exists": { "type": "boolean" },
              "sha256": {
                "type": ["string", "null"],
                "pattern": "^[0-9a-f]{64}$"
              }
            },
            "additionalProperties": false
          }
        }
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": true
}

## 行为规则

Feature: 审计模式冻结对齐文档基线

  Rule: review records the alignment document baseline

    Scenario: [ADR-NNN] review writes baseline files
      Given staged code changes exist
      And the commit message contains "[ADR-022]"
      When `spec-vc review --message "feat: x [ADR-022]"` runs
      Then `.git/spec-vc-review.json` contains `document_baseline`
      And the baseline contains the ADR file
      And the baseline contains the selected Plan file when it exists
      And the baseline contains associated Spec dev-doc and formal files when they exist

  Rule: commit-msg hook blocks baseline drift

    Scenario: ADR file changes after review
      Given `spec-vc review` has written review.json for "[ADR-022]"
      When `doc/arch/adr-022.md` changes before commit
      And the commit-msg hook runs
      Then the hook exits non-zero
      And stderr explains that the document baseline changed
      And stderr suggests rerunning `spec-vc review`

    Scenario: Plan file changes after review
      Given `spec-vc review` has written review.json for "[ADR-022]"
      When `doc/arch/plans/ADR-022-plan-001.md` changes before commit
      And the commit-msg hook runs
      Then the hook exits non-zero
      And stderr explains that the document baseline changed

    Scenario: Spec formal file changes after review
      Given `spec-vc review` has written review.json for "[ADR-022]"
      When `doc/arch/specs/022/schema.json` changes before commit
      And the commit-msg hook runs
      Then the hook exits non-zero
      And stderr explains that the document baseline changed

  Rule: compatibility remains stable

    Scenario: legacy review.json has no document_baseline
      Given `.git/spec-vc-review.json` was written by an older spec-vc version
      And the anchor still matches the current staged diff
      When the commit-msg hook runs
      Then the hook does not fail only because `document_baseline` is absent

    Scenario: SPEC_VC_BYPASS is set
      Given document baseline drift exists
      And `SPEC_VC_BYPASS` is non-empty
      When the commit-msg hook runs
      Then bypass logging occurs
      And document baseline verification is skipped

## 非目标

- 不把 ADR/Plan/Spec 变成不可编辑文件。
- 不校验 review assistant 的 `context_summary` 文本。
- 不恢复 ADR-020 删除的 plan stage 校验、simple note anchor 校验或 `[ADR-none]` 量化判定。
- 不阻塞 review 后的代码修正；代码修正仍由 staged diff anchor 要求重新 review。

## 测试策略

验收标准：

```gherkin
Given spec-vc review has recorded a document baseline
When an ADR, Plan, or associated Spec file changes before commit
Then commit-msg blocks the commit with a BlockingError
```

测试用例：

| 测试类型 | 覆盖范围 | 优先级 |
|----------|----------|--------|
| 单元测试 | 基线文件发现、sha256 计算、缺失文件表示、差异比较 | P0 |
| 集成测试 | `spec-vc review` 写入 `document_baseline` | P0 |
| 集成测试 | review 后修改 ADR/Plan/Spec 时 commit-msg 阻塞 | P0 |
| 回归测试 | 旧 review.json 无 `document_baseline` 时兼容放行 | P0 |
| 回归测试 | `SPEC_VC_BYPASS` 仍跳过 review.json 校验并写 bypass log | P1 |

边界条件：

- ADR 有多个 plan 时选择与 active change 对应的 plan；无 active change 时选择编号最大的关联 plan。
- ADR 没有关联 Spec 时只记录 ADR 与 Plan。
- 形式化文件不存在时记录 `exists=false` 与 `sha256=null`，后续新增文件视为基线漂移。
- 路径必须是仓库相对路径，不能越出仓库。

## 日志实现

本变更不新增持久运行日志。阻塞信息继续使用 `BlockingError` 四段结构输出到 stderr：

| 事件 | 输出级别 | 必须字段 | 说明 |
|------|----------|----------|------|
| document_baseline drift | stderr | expected path/sha256, actual path/sha256, fix command, docs ref | commit-msg hook 阻塞提交 |
| bypass | audit log | timestamp, reason, subject | 沿用 `.git/spec-vc-bypass.log` |

敏感信息处理：基线只记录仓库相对路径与 sha256，不记录文件正文。

---

## 变更历史

| 版本 | 日期 | 作者 | 变更内容 |
|------|------|------|----------|
| 0.1.0 | 2026-05-25 | arcaneorion | 初始版本 |

## References

- **ADR**: ADR-022
- **Related Specs**: Spec-018, Spec-019, Spec-020, Spec-021
- **External**: 无
