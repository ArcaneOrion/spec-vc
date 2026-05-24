# Spec-019: spec-vc review 升级为审查助手：context 报告输出契约

- **ADR**: ADR-019
- **Status**: Draft
- **Author**: arcaneorion
- **Date**: 2026-05-24
- **Version**: 0.1.0

---

## 概述

### 1.1 问题陈述

AI 在执行 `spec-vc review` 时，需要 [staged diff 摘要 / 关联 ADR plan 的 design+verification 段 / 关联 Spec 的形式化契约 / 轻量静态检查结果] 作为 review 命令的免费副产品输出到 stderr，因为 ADR-017/018 的 sticks 设计只能强制 AI 看一眼 anchor 指纹但不能强制看懂 diff，邻近项目实践显示 subagent 模式仍是 honor system 而 simple 模式诚实成本（手抄 sha12 + 写一句结论）远低于真审查所需的 Read 多文件 + 理解 ADR/Spec 上下文。

### 1.2 解决方案概述

新增 `src/spec_vc/review_assistance.py` 模块含 5 个 fail-open 函数：`summarize_staged_diff` / `summarize_plan_context` / `summarize_spec_context` / `run_static_checks` / `assemble_review_report`。`spec-vc review` 命令在写 review.json 之前先调 `assemble_review_report` 把审查所需信息组装成结构化报告输出到 stderr（五段：Staged Diff / Plan Context / Spec Context / Static Checks / Your Response），并把报告摘要写入 `review.json.context_summary` 字段作为事后审计凭证。设计哲学从 sticks（提高作弊成本）转 carrots（降低遵守成本）——让审查所需信息成为 review 命令的免费副产品，AI 读取这份报告本身就是审查发生。

### 1.3 范围边界

**包含**:
- 新模块 `review_assistance.py`（5 函数 + fail-open）
- `ReviewAssistanceConfig` 配置项（6 字段：4 开关 + 2 上限）
- `ReviewRecord.context_summary` 字段（新增；ADR-018 schema 向后兼容）
- `cmd_review` 流程改动（assemble → print stderr → 写入 review.json.context_summary）
- 输出格式契约（五段固定段头 + Your Response 指引）
- SKILL.md / CLAUDE.md 同步新心智模型

**不包含**:
- 自动跑 pytest / 自动建议修复 / 解析 diff 语义
- commit-msg hook 校验链改动（保留 ADR-018）
- 校验 `context_summary` 非空（carrots 不加 sticks）
- subagent/simple 模式语义变化
- 强制 AI 真读 stderr（仍 honor system，但成本曲线翻转）

---

## 接口契约

```yaml
openapi: "3.0.3"
info:
  title: spec-vc review 审查助手输出契约（ADR-019）
  version: "0.1.0"
  description: |
    本 Spec 的接口不对外暴露 HTTP，全部以 Python 函数 + CLI stderr 输出 + JSON 文件字段表达。

paths:
  /internal/review-assistance/summarize-staged-diff:
    get:
      summary: summarize_staged_diff —— staged 内容摘要
      description: |
        签名: summarize_staged_diff(repo_root: Path, max_files: int = 20, max_hunks_per_file: int = 3) -> str

        行为:
          1. 调 git diff --cached --stat 获取 staged file 列表 + 增删行数
          2. 对每个 staged 文件，调 git diff --cached <file>，提取前 max_hunks_per_file 个 hunk 首行（@@ ... @@ 行）
          3. 拼接输出，前缀段头 "=== Staged Diff Summary ==="
          4. staged 区为空 → 返回 "(无 staged changes)"
          5. fail-open: 任何异常 → 返回 "(本段获取失败: <错误摘要>)"，不抛异常
      responses:
        "0": { description: 已返回摘要文本 }

  /internal/review-assistance/summarize-plan-context:
    get:
      summary: summarize_plan_context —— 关联 ADR plan 摘要
      description: |
        签名: summarize_plan_context(repo_root: Path, adr_token: str, max_chars_per_section: int = 600) -> str

        行为:
          1. 解析 adr_token 得 adr_id
          2. 查 doc/arch/plans/ADR-{adr_id}-plan-*.md，取编号最大的文件
          3. 用 _sections.extract_section 提取 "Design and Architecture" + "Verification and Testing"
          4. 每段截断到 max_chars_per_section 字符（末尾加 "... (truncated)"）
          5. 拼接输出，前缀段头 "=== Plan Context (Design + Verification) ==="
          6. ADR 无 plan 文件 → 返回 "(ADR-{adr_id} 无活跃 plan，已 close 或未启动)"
          7. fail-open
      responses:
        "0": { description: 已返回摘要文本 }

  /internal/review-assistance/summarize-spec-context:
    get:
      summary: summarize_spec_context —— 关联 Spec 形式化契约摘要
      description: |
        签名: summarize_spec_context(repo_root: Path, adr_token: str, max_lines_per_file: int = 30) -> str

        行为:
          1. 通过 spec.has_associated_spec / relevant_spec_issues 找到关联 Spec
          2. 读取每个关联 Spec 的 contract.openapi.yaml / schema.json / behavior.feature 前 max_lines_per_file 行
          3. 拼接输出，前缀段头 "=== Spec Context ==="，子段标题 "--- Spec-NNN/<filename> ---"
          4. ADR 无关联 Spec → 返回 "(ADR-{adr_id} 无关联 Spec)"
          5. fail-open
      responses:
        "0": { description: 已返回摘要文本 }

  /internal/review-assistance/run-static-checks:
    get:
      summary: run_static_checks —— 可选轻量静态检查
      description: |
        签名: run_static_checks(repo_root: Path, timeout: float = 5.0) -> str

        行为:
          1. shutil.which("ruff") 探测
          2. 存在 → subprocess.run ["ruff", "check", "src/"] with timeout
             - 成功 → "ruff: 0 errors"
             - 有 errors → "ruff: N errors\n<前 10 行>"
             - 超时 → "ruff: 超时（>{timeout}s）跳过"
          3. 不存在 → "(未检测到 ruff，跳过静态检查)"
          4. 拼接输出，前缀段头 "=== Static Checks ==="
          5. fail-open

        非目标: 不跑 pytest（耗时）；不解析 ruff 输出语义；不强制项目装 ruff
      responses:
        "0": { description: 已返回摘要文本 }

  /internal/review-assistance/assemble-review-report:
    get:
      summary: assemble_review_report —— 拼接完整审查报告
      description: |
        签名: assemble_review_report(repo_root: Path, adr_token: str, anchor: str, config: ReviewAssistanceConfig) -> str

        行为:
          1. 按 config 开关逐段调用 4 个 summarize/run 函数
          2. 末尾追加 "=== Your Response ===" 段，固定内容:
             "看完上述信息后:
                ✓ 无问题 → spec-vc commit
                ✗ 有问题 → 改代码后重跑 spec-vc review
              audit-anchor: <anchor>"
          3. 段间空行分隔
          4. fail-open: 单段抛异常 → 该段插入 "(本段获取失败: ...)"
      responses:
        "0": { description: 已返回完整报告 }

  /internal/cmd-review-flow:
    post:
      summary: cmd_review 流程改动（ADR-019）
      description: |
        在 ADR-018 流程基础上插入审查报告输出：

        既有流程 (ADR-018):
          1. _repo_root + load_config + gather_commit_context
          2. 校验 staged / Spec 就绪 / --message / ADR token / mode/note
          3. build_review_record
          4. simple 模式校验 note 含 anchor
          5. write_review_and_msg
          6. _print_staged_and_specs + 提示

        新增 (ADR-019，第 4 步后第 5 步前):
          4a. report = assemble_review_report(repo_root, adr_token, record.anchor, config.review_assistance)
          4b. print(report, file=sys.stderr)
          4c. record.context_summary = report[:config.review_assistance.context_summary_max_bytes]
      responses:
        "0": { description: review.json 与 commit-msg 已落盘 + 报告已输出 }
        "1": { description: 阻塞（既有 BlockingError 路径不变） }
```

---

## 数据形状

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "ReviewAssistanceConfig": {
      "title": "ReviewAssistanceConfig",
      "description": ".spec-vc.toml 中 [review_assistance] 段，控制 spec-vc review 报告输出。",
      "type": "object",
      "properties": {
        "show_diff_summary": { "type": "boolean", "default": true },
        "show_plan_context": { "type": "boolean", "default": true },
        "show_spec_context": { "type": "boolean", "default": true },
        "run_static_checks": { "type": "boolean", "default": true },
        "static_check_timeout_seconds": { "type": "number", "minimum": 0.5, "default": 5.0 },
        "context_summary_max_bytes": { "type": "integer", "minimum": 256, "default": 4096 }
      }
    },
    "ReviewRecord_v019": {
      "title": "ReviewRecord (ADR-019)",
      "description": "ADR-018 的 ReviewRecord 新增 context_summary 字段；旧字段语义不变。",
      "type": "object",
      "required": ["anchor", "adr_token", "staged_sha12", "mode", "verified", "created_at"],
      "properties": {
        "anchor": { "type": "string", "pattern": "^ADR-(\\d{3,}|none)@[0-9a-f]{12}$" },
        "adr_token": { "type": "string", "pattern": "^ADR-(\\d{3,}|none)$" },
        "staged_sha12": { "type": "string", "pattern": "^[0-9a-f]{12}$" },
        "mode": { "type": "string", "enum": ["subagent", "simple"] },
        "verified": { "type": "boolean" },
        "note": { "type": "string" },
        "subagent_log_tail": { "type": ["string", "null"] },
        "created_at": { "type": "string", "format": "date-time" },
        "context_summary": {
          "type": "string",
          "default": "",
          "description": "ADR-019 新增：本次 review 输出的报告文本摘要，截断到 context_summary_max_bytes。"
        }
      },
      "examples": [
        {
          "anchor": "ADR-019@abcdef012345",
          "adr_token": "ADR-019",
          "staged_sha12": "abcdef012345",
          "mode": "simple",
          "verified": true,
          "note": "已读 review 报告，无问题。ADR-019@abcdef012345",
          "subagent_log_tail": null,
          "created_at": "2026-05-24T14:00:00+08:00",
          "context_summary": "=== Staged Diff Summary ===\nsrc/spec_vc/review_assistance.py | +95 (new)\n...\n=== Your Response ===\nspec-vc commit\naudit-anchor: ADR-019@abcdef012345"
        }
      ]
    },
    "ReviewReport": {
      "title": "ReviewReport 段结构",
      "type": "object",
      "required": ["sections"],
      "properties": {
        "sections": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["header", "body"],
            "properties": {
              "header": {
                "type": "string",
                "enum": [
                  "=== Staged Diff Summary ===",
                  "=== Plan Context (Design + Verification) ===",
                  "=== Spec Context ===",
                  "=== Static Checks ===",
                  "=== Your Response ==="
                ]
              },
              "body": { "type": "string" }
            }
          },
          "minItems": 1,
          "maxItems": 5
        }
      }
    }
  }
}
```

---

## 行为规则

```gherkin
Feature: spec-vc review 升级为审查助手（ADR-019）

  Background:
    Given spec-vc 仓库已初始化
    And ADR-019 plan stage 为 implement-ready 或更高
    And Spec-019 已就绪
    And .spec-vc.toml 的 [review_assistance] 全部开关默认 true

  Rule: summarize_staged_diff 正确输出
    Scenario: 有 staged 文件时输出 stat + 关键 hunk
      Given staged 区有 2 个文件变更
      When 调 summarize_staged_diff(repo)
      Then 输出含 "=== Staged Diff Summary ==="
      And 输出含 git diff --cached --stat 的结果
      And 输出含至少一行 "@@ ... @@" 形式的 hunk header

    Scenario: 空 staged 区返回 fallback
      Given staged 区为空
      When 调 summarize_staged_diff(repo)
      Then 输出含 "(无 staged changes)"

    Scenario: git 命令失败时 fail-open
      Given git diff 子进程抛异常
      When 调 summarize_staged_diff(repo)
      Then 输出含 "(本段获取失败:"
      And 不抛异常

  Rule: summarize_plan_context 正确提取
    Scenario: 存在 plan 文件时提取 design + verification 段
      Given plans/ADR-019-plan-001.md 存在且含 Design 和 Verification 段
      When 调 summarize_plan_context(repo, "ADR-019")
      Then 输出含 "=== Plan Context (Design + Verification) ==="
      And 输出含 plan 文件 Design and Architecture 段的前 600 字符
      And 输出含 plan 文件 Verification and Testing 段的前 600 字符

    Scenario: ADR 无 plan 文件时返回 fallback
      Given doc/arch/plans/ADR-999-plan-*.md 不存在
      When 调 summarize_plan_context(repo, "ADR-999")
      Then 输出含 "(ADR-999 无活跃 plan"

    Scenario: 段超长时截断
      Given Design 段长度 > 600 字符
      When 调 summarize_plan_context(repo, "ADR-019", max_chars_per_section=600)
      Then 该段输出末尾含 "... (truncated)"

  Rule: summarize_spec_context 正确提取
    Scenario: 存在关联 Spec 时输出三个形式化文件前 N 行
      Given Spec-019 存在且关联 ADR-019
      When 调 summarize_spec_context(repo, "ADR-019")
      Then 输出含 "=== Spec Context ==="
      And 输出含 "--- Spec-019/contract.openapi.yaml ---"
      And 输出含 "--- Spec-019/schema.json ---"
      And 输出含 "--- Spec-019/behavior.feature ---"
      And 每个文件输出不超过 30 行

    Scenario: ADR 无关联 Spec 时返回 fallback
      Given ADR-019 无关联 Spec
      When 调 summarize_spec_context(repo, "ADR-019")
      Then 输出含 "(ADR-019 无关联 Spec)"

  Rule: run_static_checks 可选执行 + fail-open
    Scenario: ruff 存在时执行检查
      Given PATH 中存在 ruff 二进制
      When 调 run_static_checks(repo, timeout=5)
      Then 输出含 "=== Static Checks ==="
      And 输出含 "ruff:" 字样

    Scenario: ruff 不存在时静默跳过
      Given PATH 中不存在 ruff
      When 调 run_static_checks(repo, timeout=5)
      Then 输出含 "(未检测到 ruff，跳过静态检查)"
      And 不抛异常

    Scenario: 超时时跳过
      Given ruff 子进程运行超过 timeout
      When 调 run_static_checks(repo, timeout=0.001)
      Then 输出含 "超时" 或 "跳过"
      And 不抛异常

  Rule: assemble_review_report 按配置开关拼接
    Scenario: 全部开关 true 时输出 5 段
      Given config 各 show_* 与 run_static_checks 全为 true
      When 调 assemble_review_report(repo, "ADR-019", "ADR-019@abcdef012345", config)
      Then 输出依次含 "=== Staged Diff Summary ===" / "=== Plan Context (Design + Verification) ===" / "=== Spec Context ===" / "=== Static Checks ===" / "=== Your Response ==="
      And "=== Your Response ===" 段含 "audit-anchor: ADR-019@abcdef012345"
      And "=== Your Response ===" 段含 "spec-vc commit"

    Scenario: 单个开关关闭时该段不输出
      Given config.run_static_checks = false
      When 调 assemble_review_report(...)
      Then 输出不含 "=== Static Checks ==="
      And 其他段仍输出

    Scenario: 单段函数抛异常时 fail-open
      Given summarize_plan_context mock 抛异常
      When 调 assemble_review_report(...)
      Then 输出含 "Plan Context" 段标题
      And 该段 body 含 "(本段获取失败:"
      And 其他段仍正常输出

  Rule: cmd_review 在写 review.json 前输出报告并写入 context_summary
    Scenario: simple 模式 + note 含 anchor + 全段开 → 成功
      Given staged 区有变更
      And ADR-019 plan 与 Spec-019 已就绪
      When 执行 spec-vc review --message "feat: x [ADR-019]" --mode simple --note "ok ADR-019@<sha12>"
      Then stderr 含 5 个段头
      And exit code == 0
      And .git/spec-vc-review.json 存在
      And review.json.context_summary 非空
      And review.json.context_summary 含 "=== Your Response ==="

    Scenario: context_summary 截断到 max_bytes
      Given config.review_assistance.context_summary_max_bytes = 200
      When 执行 spec-vc review --message "..." 且实际报告长度 > 200
      Then len(review.json.context_summary) == 200

  Rule: commit-msg hook 行为不变（carrots 不加 sticks）
    Scenario: review.json 含 context_summary 时 hook 正常放行
      Given review.json 含 context_summary 字段
      And anchor 匹配 + mtime 新鲜
      When git commit 触发 commit-msg hook
      Then exit code == 0
      And hook 未校验 context_summary 内容

    Scenario: review.json 不含 context_summary 时 hook 仍放行（向后兼容 ADR-018）
      Given review.json 缺少 context_summary 字段
      And anchor 匹配 + mtime 新鲜
      When git commit 触发 commit-msg hook
      Then exit code == 0
```

---

## 非目标

### 5.1 明确排除的功能
- 不自动跑 pytest（耗时不可控）
- 不解析 diff 语义、不自动建议修复（超出 spec-vc 职责，依赖 LLM）
- 不修改 commit-msg hook 校验链（保留 ADR-018 设计）
- 不在 hook 中校验 `context_summary` 非空（carrots 设计不该再加 sticks，否则破坏哲学纯粹性）
- 不动 subagent / simple 模式语义
- 不解析 ruff 输出语义建议修复
- 不强制 AI 真读 stderr（仍 honor system，但成本曲线翻转）

### 5.2 未来可能扩展
- 增加更多静态检查工具（mypy / pyright / 项目自定义脚本）
- 报告输出格式支持 JSON（供 IDE / 编辑器解析）
- 关联 Spec 按变更文件智能选择最相关的（当前是 ADR 关联的全部 Spec）
- staged diff 摘要按文件类型聚类
- 增量缓存（同一 staged sha12 下复用上次报告）

---

## 非功能性需求

### 6.1 性能
| 指标 | 目标值 |
|------|--------|
| assemble_review_report 总耗时（全段开 + ruff 可用） | < 6 秒（含 ruff 5s 超时） |
| 单个 summarize_* 函数耗时（ruff 除外） | < 200ms |

### 6.2 可用性
- 单段失败不阻塞其他段，单段失败不阻塞 review 命令
- 无网络依赖

### 6.3 安全
- 不引入新的用户输入执行路径
- run_static_checks 仅调 `ruff check` 不接受任意命令

---

## 错误处理

### 7.1 异常分类
| 类别 | 示例 | 处理策略 |
|------|------|----------|
| 工具缺失 | ruff 不在 PATH | 静默跳过，输出 fallback 文字 |
| 子进程超时 | ruff 运行 > timeout | 输出"超时跳过"，不阻塞 |
| 文件缺失 | plan 文件不存在 | 输出"无活跃 plan"，不阻塞 |
| 解析失败 | extract_section 抛异常 | 该段 "(本段获取失败: ...)"，不阻塞 |
| 配置非法 | toml 字段类型错误 | ValidationError 抛出（既有路径） |

### 7.2 fail-open 原则

review_assistance.py 所有函数捕获 `Exception`，转为段内文本，不向调用方抛异常。理由：review 命令是审查助手，自身不应该因为辅助信息获取失败而阻塞 review 流程。BlockingError 仅在既有 ADR-018 路径触发。

---

## 测试策略

### 8.1 验收标准
```gherkin
Given ADR-019 代码实现完成
When 本 ADR 自身的 commit 走新流程 simple 模式 + --verified
Then spec-vc review stderr 含 5 个段头
And review.json.context_summary 非空且含 "Your Response"
And spec-vc commit 通过 commit-msg hook（沿用 ADR-018 校验链）
And .git/spec-vc-bypass.log 无新增条目
And pytest 全部通过
```

### 8.2 测试用例
| 测试类型 | 覆盖范围 | 优先级 |
|----------|----------|--------|
| 单元测试 | summarize_staged_diff 各分支 | P0 |
| 单元测试 | summarize_plan_context 各分支 | P0 |
| 单元测试 | summarize_spec_context 各分支 | P0 |
| 单元测试 | run_static_checks ruff 存在/缺失/超时 | P0 |
| 单元测试 | assemble_review_report 配置开关组合 | P0 |
| 单元测试 | assemble_review_report fail-open | P0 |
| 集成测试 | cmd_review stderr 含 5 段头 + context_summary 写入 | P0 |
| 集成测试 | context_summary 截断到 max_bytes | P0 |
| 回归 | hook 对含/不含 context_summary 的 review.json 都放行 | P0 |
| 自举 | 本 ADR-019 自身 commit 走 simple 模式 | P0 |

### 8.3 边界条件
- staged files 数量 = 0 / 1 / 20 / >20
- plan 文件缺失 / 段缺失 / 段长度边界
- Spec 文件缺失 / 关联 Spec 数 > 1
- ruff 二进制损坏（subprocess 返回非 0 但非超时）
- context_summary_max_bytes < 实际报告长度 / > 实际报告长度
- 单段开关全关 → 仅输出 "=== Your Response ==="

### 8.4 Mock 策略
- subprocess.run 用 monkeypatch mock（不真跑 ruff）
- git diff 子进程用 monkeypatch mock（确定性输出）
- 单段函数用 monkeypatch 替换为 raise Exception 验证 fail-open

---

## 日志实现

### 9.1 日志级别
| 级别 | 使用场景 |
|------|----------|
| INFO | stdout 输出 audit-anchor（既有） |
| INFO | stderr 输出 review 报告（ADR-019 新增） |
| BLOCK | stderr 输出 BlockingError（既有 ADR-018） |

### 9.2 必须记录的事件
| 事件 | 位置 | 内容 |
|------|------|------|
| review 报告生成 | stderr | 5 段结构化文本 |
| context_summary 落盘 | review.json | 报告摘要（截断） |
| 单段 fail-open | 报告对应段 body | "(本段获取失败: ...)" |

### 9.3 日志格式
- stderr：纯文本，段头 `=== <name> ===` 分隔
- review.json：JSON，context_summary 是字符串字段

### 9.4 敏感信息
不涉及（不输出秘密 / token / 凭证）。

---

## 部署与集成

### 10.1 部署要求
- 依赖：无新增 Python 依赖（subprocess 标准库；ruff 可选外部工具）
- 配置：`.spec-vc.toml` 新增 `[review_assistance]` 段（可选，有默认值）

### 10.2 向后兼容
- ADR-018 的 ReviewRecord 增加 context_summary 字段（default ""）
- 旧 review.json（无 context_summary 字段）：read_review 用 `data.get("context_summary", "")` 兼容
- commit-msg hook 不读 context_summary，旧 review.json 校验逻辑不变

---

## 变更历史

| 版本 | 日期 | 作者 | 变更内容 |
|------|------|------|----------|
| 0.1.0 | 2026-05-24 | arcaneorion | 初始版本 |

---

## References

- **ADR**: ADR-019
- **Related Specs**: Spec-018（review.json schema 基线，ADR-019 仅追加 context_summary 字段）
- **External**: 无

---

<!--
质量检查清单（提交前确认）:
[x] 所有"待补充"标记已移除
[x] 接口契约区块已填写完整的 API 定义
[x] 数据形状区块已定义所有实体和枚举
[x] 行为规则区块已描述所有业务规则
[x] 测试策略区块已包含验收标准和测试用例
[x] 日志实现区块已定义日志级别、格式和敏感信息处理
[x] 非功能性需求已明确量化指标
[x] 错误处理已覆盖所有异常场景
-->
