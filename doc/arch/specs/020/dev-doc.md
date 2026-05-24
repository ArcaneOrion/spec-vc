# Spec-020: spec-vc 减法后契约：commit-msg hook 4 步校验链 + review.json 移除 require_user_verified

- **ADR**: ADR-020
- **Status**: Draft
- **Author**: arcaneorion
- **Date**: 2026-05-24
- **Version**: 0.1.0

---

## 概述

### 1.1 问题陈述

AI 在执行 `git commit` 时，需要 [一个 4 步而非 6 步的 commit-msg hook 校验链] 才能避免被 reasoning scaffolding 拖累，因为 ADR-018 的 6 步链中有 3 步（plan stage / simple 模式 note 含 anchor / [ADR-none] 量化判定）属于"教 AI 走流程"的 scaffolding，按 VILA-Lab 判别法应删除（详见 ADR-020 Context）。

### 1.2 解决方案概述

`hooks.py:run_commit_msg` 校验链从 6 步压到 4 步：仅保留 SPEC_VC_BYPASS audit / ADR 引用格式 / Spec 完整性 / review.json (anchor 匹配 + mtime 新鲜)；删除 `_check_plan_stage` / `_check_lightweight` / simple 模式 note anchor 子句 / require_user_verified 升级开关。`src/spec_vc/lightweight.py` 整个文件删除。`LightweightConfig` 配置类从 `config.py` 删除。`review.py:cmd_review` 简化（删除 simple 模式 note anchor 强制校验，--note 参数保留作记录）。`ReviewRecord.verified` 字段保留作记录字段，但不再被 hook 校验。

### 1.3 范围边界

**包含**:
- `commit-msg` hook 校验链 6→4 步
- `lightweight.py` 文件删除
- `LightweightConfig` 配置删除
- `cmd_review` simple 模式 note anchor 校验删除
- `_check_plan_stage` / `_check_lightweight` / `_load_stage_for_adr` 等函数删除
- 测试集减 ~15 项（reasoning scaffolding 相关）
- CLAUDE.md 新增 ADR 写作规范段

**不包含**:
- 删除 BYPASS audit / ADR 引用 / Spec 完整性 / review.json anchor+mtime 任一项
- 修改 ADR/Spec 创作协议
- 修改 ADR-019 的 review 助手报告
- 修改 BlockingError 结构
- review.json schema 字段移除（`verified` 字段保留作记录，不再被强制）

---

## 接口契约

```yaml
openapi: "3.0.3"
info:
  title: spec-vc 减法后契约（ADR-020）
  version: "0.1.0"
  description: |
    本 Spec 描述减法后的 commit-msg hook 校验链 + review.json schema 变化 + cmd_review 简化。
    /internal/* 路径仅用于在 OpenAPI 语法下表达 CLI / hook 行为契约。

paths:
  /internal/commit-msg-hook-v2:
    post:
      summary: commit-msg hook 4 步校验链（ADR-020）
      description: |
        从 ADR-018 的 6 步压到 4 步。校验顺序（任一阻塞即返回非 0）:

        1. SPEC_VC_BYPASS 非空 → 写 .git/spec-vc-bypass.log → 跳到第 2 步
        2. ADR 引用格式校验:
           - 无 [ADR-NNN] / [ADR-none] → BlockingError 阻塞
           - [ADR-???] 未填充 → BlockingError 阻塞
           - [ADR-none] → 直接放行（ADR-020 删除量化判定）
           - [ADR-NNN] → 继续第 3 步
        3. [ADR-NNN] Spec 完整性校验:
           - ADR 关联 Spec 的 dev-doc 与形式化文件未就绪 → BlockingError 阻塞
           - ADR 无关联 Spec → 放行
        4. [ADR-NNN] review.json 校验（SPEC_VC_BYPASS 时跳过本步全部子项）:
           a. 读 .git/spec-vc-review.json:
              - 文件不存在 → BlockingError 阻塞
              - JSON 解析失败 → BlockingError 阻塞
           b. review.json.anchor != "ADR-NNN@<当前 staged sha12>" → BlockingError 阻塞
           c. review.json.mtime ≤ .git/spec-vc-commit-msg.mtime → BlockingError 阻塞

        删除的子项（相对 ADR-018）:
        - plan stage 校验（≥ implement-ready）
        - simple 模式 note 含 anchor 子串校验
        - require_user_verified 升级开关
        - [ADR-none] 量化判定（files_max / lines_max / type_whitelist）

      responses:
        "0":
          description: 校验通过
        "1":
          description: 校验阻塞（BlockingError 写 stderr）

  /internal/cmd-review-v2:
    post:
      summary: cmd_review simple 模式简化（ADR-020）
      description: |
        参数保持 ADR-018/019:
          --message MESSAGE (必填)
          --mode {subagent|simple} (默认 subagent)
          --note NOTE (可选，记录用)
          --verified (可选，记录用)

        行为变化（相对 ADR-018）:
          - simple 模式不再强制 --note 含 anchor 子串（删除阻塞分支）
          - --note 仍写入 review.json.note 作为记录
          - --verified 仍写入 review.json.verified 作为记录
          - review.json schema 不变（向后兼容 ADR-019 写入的 review.json）

        其余行为（计算 anchor / Spec 就绪检查 / 写 commit-msg / 写 review.json / 输出 review 助手报告到 stderr）保持不变。

      responses:
        "0":
          description: review.json 已落盘 + 报告已输出
        "1":
          description: 阻塞（无 staged / 无 message / [ADR-???] 未填充 / Spec 未就绪）

  /internal/lightweight-removed:
    delete:
      summary: lightweight.py 文件删除（ADR-020）
      description: |
        删除文件: src/spec_vc/lightweight.py
        相关删除:
          - config.py:LightweightConfig dataclass
          - config.py:Config.lightweight 字段
          - config.py:load_config 中加载 [lightweight] 配置段的代码
          - tests/python/test_cli.py 中 test_lightweight_* 5 项

        语义变化:
          - .spec-vc.toml 的 [lightweight] 段被忽略（不报错，但不读取）
          - [ADR-none] commit 不再做量化判定，直接放行
      responses:
        "204":
          description: 已删除

  /internal/adr-writing-rules:
    post:
      summary: CLAUDE.md ADR 写作规范段（ADR-020）
      description: |
        在 CLAUDE.md "## 关键设计约定" 段后新增 "## ADR 写作规范"。
        硬约束清单:
          - 每条 ADR 必须自包含可读
          - Plan summary 必须含 ≥ 1 个具体 file:line 或 commit hash 引用
          - 禁用宣示句式（清单：'设计哲学转向' / '心智模型' / 'X 取代 Y' / 'sticks/carrots' 等）
          - 哲学讨论 ≤ 1 段；超过的写到独立回顾文章
          - "AI 行为假设" 必须有 bypass log 或测试数据支撑，否则不写
      responses:
        "0":
          description: 写作规范段已加入 CLAUDE.md
```

---

## 数据形状

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "ReviewRecord_v020": {
      "title": "ReviewRecord (ADR-020)",
      "description": "ADR-019 schema 不变；ADR-020 仅改变 hook 对 verified 字段的处理（不再校验，只作记录）。",
      "type": "object",
      "required": ["anchor", "adr_token", "staged_sha12", "mode", "verified", "created_at"],
      "properties": {
        "anchor": { "type": "string", "pattern": "^ADR-(\\d{3,}|none)@[0-9a-f]{12}$" },
        "adr_token": { "type": "string", "pattern": "^ADR-(\\d{3,}|none)$" },
        "staged_sha12": { "type": "string", "pattern": "^[0-9a-f]{12}$" },
        "mode": { "type": "string", "enum": ["subagent", "simple"] },
        "verified": {
          "type": "boolean",
          "description": "ADR-020 后仅作记录，hook 不再校验"
        },
        "note": {
          "type": "string",
          "description": "ADR-020 后 simple 模式不再强制含 anchor 子串"
        },
        "subagent_log_tail": { "type": ["string", "null"] },
        "created_at": { "type": "string", "format": "date-time" },
        "context_summary": {
          "type": "string",
          "default": "",
          "description": "ADR-019 字段保留不变"
        }
      }
    },
    "CommitMsgHookValidationChain_v020": {
      "title": "commit-msg hook 4 步校验链",
      "type": "object",
      "required": ["steps"],
      "properties": {
        "steps": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["order", "name", "kind"],
            "properties": {
              "order": { "type": "integer" },
              "name": { "type": "string" },
              "kind": {
                "type": "string",
                "enum": ["operational_harness"],
                "description": "ADR-020 后保留的全部校验项均属 operational harness"
              }
            }
          },
          "minItems": 4,
          "maxItems": 4
        }
      },
      "examples": [
        {
          "steps": [
            { "order": 1, "name": "SPEC_VC_BYPASS audit log", "kind": "operational_harness" },
            { "order": 2, "name": "ADR 引用格式校验", "kind": "operational_harness" },
            { "order": 3, "name": "[ADR-NNN] Spec 完整性校验", "kind": "operational_harness" },
            { "order": 4, "name": "[ADR-NNN] review.json anchor+mtime 校验", "kind": "operational_harness" }
          ]
        }
      ]
    },
    "RemovedMechanisms": {
      "title": "ADR-020 删除清单（参照）",
      "type": "object",
      "required": ["hook_checks", "files", "config_fields", "tests"],
      "properties": {
        "hook_checks": {
          "type": "array",
          "items": { "type": "string" },
          "description": "删除的 hook 校验项",
          "examples": [[
            "_check_plan_stage (plan stage ≥ implement-ready)",
            "simple 模式 note 含 anchor 子串校验",
            "[ADR-none] 量化判定 (_check_lightweight)",
            "require_user_verified 升级开关"
          ]]
        },
        "files": {
          "type": "array",
          "items": { "type": "string" },
          "examples": [["src/spec_vc/lightweight.py"]]
        },
        "config_fields": {
          "type": "array",
          "items": { "type": "string" },
          "examples": [[
            "Config.lightweight",
            "LightweightConfig (全删 dataclass)"
          ]]
        },
        "tests": {
          "type": "array",
          "items": { "type": "string" },
          "examples": [[
            "test_lightweight_* (5 项)",
            "test_commit_msg_rejects_adr_none_for_code_change",
            "test_review_simple_mode_note_must_contain_anchor",
            "test_require_user_verified_blocks_when_verified_false",
            "test_freshness_passes_when_review_newer_than_commit_msg (plan stage 相关 setup)"
          ]]
        }
      }
    }
  }
}
```

---

## 行为规则

```gherkin
Feature: spec-vc 减法后的 commit-msg hook + cmd_review（ADR-020）

  Background:
    Given spec-vc 仓库已初始化
    And ADR-020 plan stage 为 implement-ready 或更高（注：本字段为 spec 上下文，hook 已不再校验 plan stage）
    And Spec-020 已就绪

  Rule: commit-msg hook 4 步校验链
    Scenario: 全部通过 → 放行
      Given .git/spec-vc-review.json 存在
      And review.json.anchor 匹配当前 staged sha12
      And review.json mtime > commit-msg mtime
      And Spec 完整性通过
      When git commit 触发 commit-msg hook
      Then exit code == 0

    Scenario: [ADR-NNN] + 缺 review.json → 阻塞
      Given .git/spec-vc-review.json 不存在
      And commit message subject 含 [ADR-020]
      When git commit 触发 commit-msg hook
      Then exit code != 0
      And stderr 含 BlockingError 四段
      And stderr 含 "spec-vc review"

    Scenario: [ADR-NNN] + anchor 不匹配 → 阻塞
      Given .git/spec-vc-review.json.anchor != 当前 staged sha12
      When git commit 触发 commit-msg hook
      Then exit code != 0
      And stderr 含 "expected:" 与 "actual:"

    Scenario: [ADR-none] 直接放行（删除量化判定）
      Given staged 区有任意改动（含代码文件）
      And commit message subject 含 [ADR-none]
      When git commit 触发 commit-msg hook
      Then exit code == 0
      And 不检查 lightweight 阈值

    Scenario: simple 模式 note 不含 anchor → 仍放行（ADR-020 删除强制）
      Given review.json.mode == "simple"
      And review.json.note 不含 review.json.anchor 子串
      And anchor 匹配 + mtime 新鲜 + Spec 就绪
      When git commit 触发 commit-msg hook
      Then exit code == 0

    Scenario: review.json.verified == false → 仍放行（ADR-020 删除 require_user_verified）
      Given review.json.verified == false
      And anchor 匹配 + mtime 新鲜 + Spec 就绪
      When git commit 触发 commit-msg hook
      Then exit code == 0

    Scenario: plan stage == clarify → 仍放行（ADR-020 删除 plan stage 校验）
      Given active.stage == "clarify"
      And anchor 匹配 + mtime 新鲜 + Spec 就绪
      When git commit 触发 commit-msg hook
      Then exit code == 0

  Rule: cmd_review simple 模式 note 不再强制含 anchor
    Scenario: simple 模式 + --note 不含 anchor → 不阻塞
      Given staged 区有变更
      When 执行 spec-vc review --mode simple --message "feat: x [ADR-020]" --note "审查完毕"
      Then exit code == 0
      And review.json.mode == "simple"
      And review.json.note == "审查完毕"
      And stderr 仍输出 ADR-019 的 5 段审查报告

    Scenario: simple 模式 + 无 --note → 不阻塞（ADR-020 进一步放宽）
      Given staged 区有变更
      When 执行 spec-vc review --mode simple --message "feat: x [ADR-020]"
      Then exit code == 0
      And review.json.mode == "simple"
      And review.json.note == ""

  Rule: lightweight.py 删除 + 配置忽略
    Scenario: .spec-vc.toml 含 [lightweight] 段 → 不报错但不读取
      Given .spec-vc.toml 含 [lightweight] files_max = 100
      When 加载配置
      Then config 对象无 lightweight 字段
      And 不抛 ValidationError

    Scenario: 导入 spec_vc.lightweight → ImportError
      When import spec_vc.lightweight
      Then 抛 ImportError（模块已删除）

  Rule: review.json verified 字段保留作记录但不校验
    Scenario: --verified 仍可写入 review.json
      When 执行 spec-vc review --message "..." --verified
      Then review.json.verified == true
      And hook 不读取该字段做阻塞决策

  Rule: ADR 写作规范进入 CLAUDE.md
    Scenario: CLAUDE.md 含 ADR-020 写作规范段
      When 读 CLAUDE.md
      Then 含 "## ADR 写作规范"
      And 段内含 5 条硬约束（自包含可读 / file:line 锚点 / 禁宣示句式 / 哲学 ≤ 1 段 / 行为假设需数据）

  Rule: 自举端到端
    Scenario: 本 ADR-020 自身 commit 走简化流程
      Given ADR-020 代码实现完成
      And pytest 全过
      When 执行 spec-vc review --mode simple --message "feat: [ADR-020]" --note "审查完毕" --verified
      And 执行 spec-vc commit
      Then commit 成功
      And .git/spec-vc-bypass.log 无新增条目
      And review.json.note 不含 anchor（验证 simple 模式 anchor 校验已删）
```

---

## 非目标

### 5.1 明确排除的功能

- 不删除 BYPASS audit / ADR 引用格式 / Spec 完整性 / review.json anchor+mtime 任一项（这些是 operational harness）
- 不修改 ADR/Spec 创作协议（语义载体的生产线，初心核心）
- 不修改 ADR-019 的 review 助手报告（这是 environment design 的实现）
- 不删除 BlockingError 结构化输出（错误恢复 = operational harness）
- 不删除 review.json 中 `verified` / `note` / `mode` 字段（保留作记录，schema 向后兼容）
- 不删除 `spec-vc commit prepare` deprecation alias（ADR-018 兼容性）

### 5.2 未来可能扩展

- ADR-021 输入：跨项目部署后观察到的 bypass log 或滥用模式
- 若观察到 AI 大量误用 [ADR-none]：可考虑增加 review 助手对 [ADR-none] 给出"建议升级 ADR-NNN"提示（仍是 carrots 不是 sticks）
- 若 simple 模式滥用严重：考虑让 review 助手报告中 anchor 行更显眼，但不重新引入强制

---

## 非功能性需求

### 6.1 性能
| 指标 | 目标 |
|------|------|
| commit-msg hook 校验链耗时 | < 150ms（少 2 步） |
| 测试套件耗时 | < 15s（少 ~15 项测试） |

### 6.2 可用性
- 减法后 hook 失败可能性下降（少 2 个可能误判分支）

### 6.3 安全
- 不引入新执行路径
- operational harness 完整保留

---

## 错误处理

### 7.1 异常分类
| 类别 | 处理 |
|------|------|
| review.json 缺失 / 解析失败 | BlockingError 阻塞（保留） |
| anchor 不匹配 | BlockingError 阻塞（保留） |
| mtime 不新鲜 | BlockingError 阻塞（保留） |
| Spec 未就绪 | BlockingError 阻塞（保留） |
| ADR 引用缺失 / [ADR-???] | BlockingError 阻塞（保留） |
| 旧 plan stage < implement-ready | 不再阻塞（ADR-020 删除） |
| 旧 simple 模式 note 不含 anchor | 不再阻塞（ADR-020 删除） |
| 旧 [ADR-none] 量化未命中 | 不再阻塞（ADR-020 删除） |
| 旧 require_user_verified=true + verified=false | 不再阻塞（ADR-020 删除配置项） |

### 7.2 降级策略
SPEC_VC_BYPASS 逃生口语义保持不变

---

## 测试策略

### 8.1 验收标准
```gherkin
Given ADR-020 代码实现完成
When 本 ADR 自身 commit 走 simple 模式 + --note "审查完毕"（不含 anchor）+ --verified
Then commit-msg hook 4 步全过（plan stage 已无校验 / simple anchor 已无校验 / [ADR-none] 已无量化）
And .git/spec-vc-bypass.log 无新增条目
And pytest 全部通过（少 ~15 项 reasoning scaffolding 测试）
```

### 8.2 测试用例
| 测试类型 | 范围 | 优先级 |
|----------|------|--------|
| 单元 | 删除 _check_plan_stage / _check_lightweight 后 run_commit_msg 路径 | P0 |
| 单元 | simple 模式 note 不含 anchor → 不阻塞 | P0 |
| 单元 | [ADR-none] + 代码文件 → 不阻塞 | P0 |
| 单元 | lightweight.py 删除后 import 失败 | P0 |
| 回归 | 保留的 operational harness 校验项全部仍工作 | P0 |
| 自举 | 本 ADR-020 自身 commit | P0 |

### 8.3 删除测试清单（实施时确认）
- `test_lightweight_*`（5 项，单元）
- `test_commit_msg_rejects_adr_none_for_code_change`（量化判定）
- `test_review_simple_mode_note_must_contain_anchor`
- `test_review_simple_mode_requires_note`（simple 模式 --note 必填校验，ADR-020 进一步放宽）
- `test_require_user_verified_blocks_when_verified_false`
- `test_hook_allows_adr_at_implement_ready_stage` / 相关 plan stage 测试
- `test_freshness_passes_when_review_newer_than_commit_msg` 等可能间接依赖 plan stage 的测试需逐项审视

### 8.4 保留测试清单
- `test_hook_accepts_review_json_with_context_summary`
- `test_hook_accepts_legacy_review_json_without_context_summary`
- `test_blocking_error_output_contains_four_sections`
- `test_anchor_binding_*`（review.json anchor 匹配）
- ADR-019 review 助手报告相关全部测试
- ADR 引用格式 / [ADR-???] / [ADR-none] 基础校验

---

## 日志实现

### 9.1 日志级别
保持 ADR-019 状态不变（INFO / BLOCK / DEPRECATION）

### 9.2 必须记录的事件
保持 ADR-019 状态不变。`bypass.log` 增量为 ADR-020 实施过程的核心 KPI（应为 0）

### 9.3 日志格式
不变

### 9.4 敏感信息
不涉及

---

## 部署与集成

### 10.1 部署要求
- 依赖：无新增
- 配置：`.spec-vc.toml` 的 `[lightweight]` 段（如存在）将被忽略；新部署无需配置该段

### 10.2 向后兼容
- review.json schema 向后兼容（新增字段无、删除字段无、`verified` / `note` / `subagent_log_tail` / `context_summary` 字段保留）
- 旧 review.json（ADR-018/019 写入）hook 校验照常通过
- 旧 `.spec-vc.toml` 含 `[lightweight]` 段不会报错（被静默忽略）

---

## 变更历史

| 版本 | 日期 | 作者 | 变更内容 |
|------|------|------|----------|
| 0.1.0 | 2026-05-24 | arcaneorion | 初始版本 |

---

## References

- **ADR**: ADR-020
- **Related Specs**:
  - Spec-018（review.json schema 基线 + commit-msg hook 校验链；本 Spec partial supersede）
  - Spec-019（review 助手输出契约；本 Spec 不动 ADR-019 部分）
- **External**: 见 ADR-020 References 段（VILA-Lab / Anthropic / Cognition）
