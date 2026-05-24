# Spec-018: 审查/提交解耦：spec-vc review 与 commit-msg hook 新校验链契约

- **ADR**: ADR-018
- **Status**: Draft
- **Author**: arcaneorion
- **Date**: 2026-05-24
- **Version**: 0.1.0

---

## 概述

### 1.1 问题陈述

AI 在 spec-vc 中提交变更时，需要"审查代码逻辑 / 用户实际验证使用 / 提交动作"三件事各自独立、证据可信、错误信息可操作，因为当前 `spec-vc commit prepare` + commit-msg hook 把三件事耦合在一起，且审计证据搭在 PostToolUse hook 的间接通道上（matcher → harness stdin JSON → AI 在 Agent description 复述 anchor），任一环节静默失败 → AI 不知道 → SPEC_VC_BYPASS 兜底；邻近项目实践显示 bypass 已变成 2/3 commit 常态，门禁形同虚设。

### 1.2 解决方案概述

把审查独立为 `spec-vc review` 命令（含 `subagent` / `simple` 两种模式），审计证据直接写到 `.git/spec-vc-review.json` 这个对 hook 可见的直接文件；commit-msg hook 重构校验链：审计证据源从 PostToolUse session log 切换到 review.json；`spec-vc commit` 退化为薄包装提交入口（Spec 就绪检查 + 应用 commit-msg + 调 git commit + hook 失败转译指引）；所有阻塞错误统一为含 `reason / current_state / fix_commands / docs_ref` 的 BlockingError 结构化输出；新增 `[ADR-none]` 量化判定规则（staged files ≤ 5 + 文件类型白名单 + 净变更 ≤ 50 行）让轻量改动自动走简化路径。

### 1.3 范围边界

**包含**:
- `spec-vc review` 命令（新增）：anchor 计算、两种模式证据落盘、写 commit-msg
- `spec-vc commit` 命令（重构）：Spec 就绪 + git commit 调用 + hook 失败转译
- commit-msg hook 校验链（重构）：审计证据源切换为 review.json
- `.git/spec-vc-review.json` 数据契约（新增）
- `LightweightConfig` 配置项 + `require_user_verified` 字段（新增）
- `BlockingError` 结构化错误输出（新增）
- `[ADR-none]` 量化判定规则（新增）
- 历史 `commit prepare` 命令保留为 alias 并打 deprecation warning

**不包含**:
- clarify / plan / Spec 创作协议本身（不改）
- change 状态机节点（不增减状态）
- ADR / Spec / Change 持久化数据模型（不改）
- PostToolUse hook 行为（保留写 session log，但 commit-msg hook 不再读）
- "用户实际验证"作为默认硬门禁（保 honor system，仅 `require_user_verified=true` 时升级）
- 兼容旧的 `.git/spec-vc-audit-anchor` 文件（弃用，由 review.json 完全替代）

---

## 接口契约

```yaml
openapi: "3.0.3"
info:
  title: spec-vc review/commit 解耦 + 结构化错误输出（ADR-018）
  version: "0.1.0"
  description: |
    本 Spec 描述的接口不对外暴露 HTTP，全部以 CLI 命令、git hook、配置文件、stdout/stderr 文本与
    退出码组合表达。/internal/* 路径仅用于在 OpenAPI 语法下结构化描述这些命令与 hook 的契约。

paths:
  /internal/review:
    post:
      summary: spec-vc review —— 独立审查命令，写 review.json 与 commit-msg
      description: |
        参数（argparse）:
          --message MESSAGE     完整 commit message（必填，含 [ADR-NNN] 或 [ADR-none]）
          --mode {subagent|simple}  审查模式，默认 subagent
          --note NOTE           simple 模式下必填；subagent 模式可选
          --verified            标记"用户已实际验证使用"，写入 review.json.verified=true

        行为:
          1. 检查 staged changes 非空；为空 → 阻塞 + BlockingError
          2. 从 --message subject 提取 ADR token（[ADR-NNN] / [ADR-none] / [ADR-???]）
             - [ADR-???] 未填充 → 阻塞 + BlockingError 提示 sed 替换命令
          3. Spec 就绪检查：若 ADR-NNN 关联 Spec 未就绪 → 阻塞 + BlockingError 列出缺失项 + fix 命令
          4. [ADR-NNN] 分支：plan stage 检查（按 adr_id 路由）
             - 不存在 plan 或 stage < implement-ready → 阻塞 + BlockingError
             - 已 close（无 plan 文件）→ 放行（追加提交场景）
          5. 计算 anchor = "<adr_token>@<sha12>"，sha12 = sha256(git diff --cached --no-renames --no-color)[:12]
          6. 按 mode 处理：
             - subagent: 不要求 --note；review.json.subagent_log_tail = "(待 PostToolUse 写入)" 占位
             - simple: 校验 --note 文本含 anchor 子串；不含 → 阻塞 + BlockingError 输出当前 anchor + 含 anchor 的 --note 模板
          7. 写 .git/spec-vc-review.json
          8. 写 .git/spec-vc-commit-msg（commit message 文本）
          9. stdout 输出 "audit-anchor: <anchor>" 与下一步指引（subagent 模式提示启动 audit subagent；simple 模式提示直接 spec-vc commit）

        退出码:
          0 = 已写 review.json + commit-msg，可进入 commit
          非 0 = BlockingError 输出至 stderr

      responses:
        "0":
          description: review 记录已落盘
        "1":
          description: 阻塞（BlockingError）

  /internal/commit:
    post:
      summary: spec-vc commit —— 薄包装提交入口
      description: |
        参数:
          （无；如需 amend / --no-verify 等，AI 直接用 git commit）

        行为:
          1. 检查 .git/spec-vc-commit-msg 存在；不存在 → 阻塞 + BlockingError 提示先跑 spec-vc review
          2. Spec 就绪检查（防御性二次检查）
          3. 调用 git commit -F .git/spec-vc-commit-msg
             - hook 失败 → 捕获 stderr，包装为 BlockingError 转译输出
             - 成功 → exit 0
          注意：commit 不再做 anchor 计算、不再做 audit 校验，这些已在 review 阶段完成；
          commit-msg hook 在 git commit 时独立校验 review.json 与其他规则。

        退出码:
          0 = git commit 成功
          非 0 = BlockingError（git commit 被 hook 阻塞或环境问题）

      responses:
        "0":
          description: 提交成功
        "1":
          description: 阻塞或 git 错误

  /internal/commit-prepare-alias:
    post:
      summary: spec-vc commit prepare —— 保留为 review 的别名（deprecation 期）
      description: |
        在 deprecation 期保留 commit prepare 命令，行为等价于 `spec-vc review --mode subagent --message ...`。
        stderr 打印 deprecation warning：
          "[spec-vc] DEPRECATION: 'spec-vc commit prepare' 将在 ADR-XXX 后移除，请改用 'spec-vc review --mode subagent --message ...'"
        退出码与 review 一致。
      responses:
        "0":
          description: 行为同 review

  /internal/commit-msg-hook:
    post:
      summary: commit-msg hook —— 校验链入口（重构）
      description: |
        Claude Code git hook 触发；commit message 文件路径作为 $1 传入。
        校验链顺序（任一阻塞即返回非 0）:

        1. SPEC_VC_BYPASS 环境变量非空 → 写 .git/spec-vc-bypass.log → 跳到第 2 步（仍校验 ADR 引用格式）
        2. ADR 引用格式校验:
           - 无 [ADR-NNN] / [ADR-none] → BlockingError 阻塞
           - [ADR-???] 未填充 → BlockingError 阻塞 + 提示 sed 命令
           - [ADR-none] → 跳到第 5 步（量化判定）
           - [ADR-NNN] → 继续第 3 步
        3. [ADR-NNN] plan stage 检查（按 adr_id 路由）:
           - active 匹配 → 用 active.stage
           - 不匹配 → fallback 取 plans/ADR-{adr_id}-plan-*.md 编号最大
           - stage < implement-ready → BlockingError 阻塞
           - 无 plan 文件 → 放行（已 close 追加提交场景）
        4. [ADR-NNN] 校验链（SPEC_VC_BYPASS 非空则跳过本步全部子项）:
           a. Spec 完整性: ADR 关联 Spec 的 dev-doc 与形式化文件就绪 → 否则 BlockingError
           b. 读 .git/spec-vc-review.json:
              - 文件不存在 → BlockingError 阻塞 + fix=spec-vc review ...
              - JSON 解析失败 → BlockingError 阻塞
              - review.json.anchor != "ADR-NNN@<当前 staged sha12>" → BlockingError 阻塞输出 expected/actual
              - review.json.mtime ≤ .git/spec-vc-commit-msg 的 mtime → BlockingError（证据不新鲜）
              - mode==simple 且 review.json.note 不含 anchor 子串 → BlockingError 阻塞
              - require_user_verified 配置为 true 且 review.json.verified != true → BlockingError 阻塞
           c. 全过 → 放行
        5. [ADR-none] 路径（SPEC_VC_BYPASS 非空则跳过本步）:
           - 调用 lightweight detection
           - 命中 → 放行
           - 未命中 → BlockingError 阻塞，输出未命中规则与"升级 ADR 或解释豁免理由"指引

        全部通过 → exit 0；任一阻塞 → BlockingError 写 stderr + exit 1。

      responses:
        "0":
          description: 校验通过
        "1":
          description: 校验阻塞，BlockingError 已写 stderr

  /internal/lightweight-detect:
    get:
      summary: [ADR-none] 量化判定
      description: |
        输入: repo_root, LightweightConfig
        输出: (is_lightweight: bool, reasons: list[str])

        规则（全部命中才 True）:
          - len(staged_files) <= config.files_max（默认 5）
          - 所有 staged_files 路径 全部命中 config.type_whitelist 模式（默认: *.md, *.txt, doc/**, .gitignore, .editorconfig, *.json）
          - sum(|added| + |deleted|) <= config.lines_max（默认 50）

        任一条件不满足 → False，reasons 列出未命中规则与实际数值，供 BlockingError 引用。

      responses:
        "200":
          description: 已完成判定

  /internal/blocking-error/format:
    post:
      summary: BlockingError 输出格式
      description: |
        所有 hook 阻塞与 CLI 错误统一通过本结构输出到 stderr：

          [spec-vc] BLOCKED: <reason>

          Current state:
            <current_state 多行文本>

          How to fix:
            $ <fix_command_1>
            $ <fix_command_2>
            ...

          Docs:
            - <docs_ref_1>
            - <docs_ref_2>

        字段约束：
          reason: 一行可读的阻塞原因（不超过 80 字符建议）
          current_state: 多行事实摘要，必须含相关文件存在性、mtime、anchor 实际值等"可观察事实"
          fix_commands: 至少一条可粘贴执行的 shell 命令
          docs_ref: 至少一条文档锚点（SKILL.md 章节 / ADR 编号 / Spec 编号）

      responses:
        "0":
          description: 已格式化
```

---

## 数据形状

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "ReviewRecord": {
      "title": "ReviewRecord",
      "description": ".git/spec-vc-review.json 文件内容契约。spec-vc review 写入，commit-msg hook 读取校验。",
      "type": "object",
      "required": ["anchor", "adr_token", "staged_sha12", "mode", "verified", "created_at"],
      "properties": {
        "anchor": {
          "type": "string",
          "pattern": "^ADR-(\\d{3,}|none)@[0-9a-f]{12}$",
          "description": "完整 anchor 字符串：<adr_token>@<staged_sha12>"
        },
        "adr_token": {
          "type": "string",
          "pattern": "^ADR-(\\d{3,}|none)$"
        },
        "staged_sha12": {
          "type": "string",
          "pattern": "^[0-9a-f]{12}$",
          "description": "sha256(git diff --cached --no-renames --no-color)[:12]"
        },
        "mode": {
          "type": "string",
          "enum": ["subagent", "simple"]
        },
        "verified": {
          "type": "boolean",
          "description": "用户是否标记 --verified（实际跑过代码验证）。默认 false。"
        },
        "note": {
          "type": "string",
          "description": "审查结论或验证说明。simple 模式必填且必须含 anchor 子串；subagent 模式可选。"
        },
        "subagent_log_tail": {
          "type": ["string", "null"],
          "description": "subagent 模式下，可选记录 PostToolUse session log 末行作为辅助证据；null 表示未启用辅助绑定。"
        },
        "created_at": {
          "type": "string",
          "format": "date-time",
          "description": "ISO 8601 with timezone。写文件时同时设置 mtime；hook 校验 mtime 而非该字段（mtime 不可伪造）。"
        }
      },
      "examples": [
        {
          "anchor": "ADR-018@a3f7c891b2d4",
          "adr_token": "ADR-018",
          "staged_sha12": "a3f7c891b2d4",
          "mode": "subagent",
          "verified": true,
          "note": "subagent 审计通过，无 P0/P1 问题",
          "subagent_log_tail": "2026-05-24T12:40:00+08:00 | Agent | audit ADR-018@a3f7c891b2d4 ...",
          "created_at": "2026-05-24T12:40:05+08:00"
        },
        {
          "anchor": "ADR-018@a3f7c891b2d4",
          "adr_token": "ADR-018",
          "staged_sha12": "a3f7c891b2d4",
          "mode": "simple",
          "verified": false,
          "note": "已读 staged diff，anchor ADR-018@a3f7c891b2d4；主要改动是 cli.py 注册命令 + 单测",
          "subagent_log_tail": null,
          "created_at": "2026-05-24T12:42:10+08:00"
        }
      ]
    },
    "LightweightConfig": {
      "title": "LightweightConfig",
      "description": ".spec-vc.toml 中 [lightweight] 段；控制 [ADR-none] 量化判定阈值。",
      "type": "object",
      "properties": {
        "files_max": {
          "type": "integer",
          "minimum": 1,
          "default": 5
        },
        "lines_max": {
          "type": "integer",
          "minimum": 1,
          "default": 50,
          "description": "净变更行数（增 + 删）上限"
        },
        "type_whitelist": {
          "type": "array",
          "items": { "type": "string" },
          "default": ["*.md", "*.txt", "doc/**", ".gitignore", ".editorconfig", "*.json"],
          "description": "glob 模式列表；所有 staged files 路径必须全部命中至少一个模式才视为轻量"
        },
        "require_user_verified": {
          "type": "boolean",
          "default": false,
          "description": "升级开关：commit-msg hook 是否要求 review.json.verified=true 才放行"
        }
      }
    },
    "BlockingError": {
      "title": "BlockingError",
      "description": "所有 spec-vc 阻塞输出的统一结构。CLI 与 hook 共用。",
      "type": "object",
      "required": ["reason", "current_state", "fix_commands", "docs_ref"],
      "properties": {
        "reason": {
          "type": "string",
          "minLength": 1,
          "maxLength": 200,
          "description": "一行可读阻塞原因"
        },
        "current_state": {
          "type": "string",
          "minLength": 1,
          "description": "多行事实摘要：相关文件存在性、mtime、anchor 实际值等可观察事实"
        },
        "fix_commands": {
          "type": "array",
          "minItems": 1,
          "items": { "type": "string" },
          "description": "至少一条可粘贴执行的 shell 命令"
        },
        "docs_ref": {
          "type": "array",
          "minItems": 1,
          "items": { "type": "string" },
          "description": "至少一条文档锚点：SKILL.md 章节 / ADR-XXX / Spec-XXX"
        }
      },
      "examples": [
        {
          "reason": "review.json 不存在，commit-msg hook 无法验证审计证据",
          "current_state": "expected: .git/spec-vc-review.json\nactual: 文件不存在\nstaged sha12: a3f7c891b2d4",
          "fix_commands": [
            "spec-vc review --mode subagent --message \"<完整 commit message>\"",
            "git commit -F .git/spec-vc-commit-msg"
          ],
          "docs_ref": ["SKILL.md#6a-review", "ADR-018"]
        }
      ]
    },
    "LightweightDetectionResult": {
      "title": "LightweightDetectionResult",
      "type": "object",
      "required": ["is_lightweight", "reasons", "metrics"],
      "properties": {
        "is_lightweight": { "type": "boolean" },
        "reasons": {
          "type": "array",
          "items": { "type": "string" },
          "description": "未命中规则的人话原因；is_lightweight=true 时为空数组"
        },
        "metrics": {
          "type": "object",
          "required": ["files_count", "lines_delta", "unmatched_files"],
          "properties": {
            "files_count": { "type": "integer", "minimum": 0 },
            "lines_delta": { "type": "integer", "minimum": 0 },
            "unmatched_files": {
              "type": "array",
              "items": { "type": "string" },
              "description": "未命中 type_whitelist 的具体路径"
            }
          }
        }
      }
    }
  }
}
```

---

## 行为规则

```gherkin
Feature: spec-vc review/commit 解耦 + commit-msg hook 校验链重构 + 结构化错误输出

  Background:
    Given spec-vc 仓库已初始化
    And ADR-018 plan stage 为 implement-ready 或更高
    And Spec-018 已就绪

  # ─── Rule 1: spec-vc review 命令基础行为 ───
  Rule: spec-vc review 写入 review.json 与 commit-msg
    Scenario: subagent 模式成功路径
      Given staged 区有变更
      And commit message subject 含 [ADR-018]
      When 执行 `spec-vc review --mode subagent --message "feat: x [ADR-018]"`
      Then .git/spec-vc-review.json 存在
      And review.json.mode == "subagent"
      And review.json.anchor 匹配 ^ADR-018@[0-9a-f]{12}$
      And review.json.verified == false
      And .git/spec-vc-commit-msg 存在且内容为完整 commit message
      And stdout 含 "audit-anchor: ADR-018@..."
      And exit code == 0

    Scenario: simple 模式 + note 含 anchor 成功
      Given staged 区有变更
      And commit message subject 含 [ADR-018]
      And anchor 计算结果为 "ADR-018@a3f7c891b2d4"
      When 执行 `spec-vc review --mode simple --message "feat: x [ADR-018]" --note "已读 staged diff ADR-018@a3f7c891b2d4，结论：..."`
      Then exit code == 0
      And review.json.mode == "simple"
      And review.json.note 含 "ADR-018@a3f7c891b2d4"

    Scenario: simple 模式 + note 不含 anchor 阻塞
      Given anchor 计算结果为 "ADR-018@a3f7c891b2d4"
      When 执行 `spec-vc review --mode simple --message "feat: x [ADR-018]" --note "已审查"`
      Then exit code != 0
      And stderr 含 BlockingError 四段结构（reason / current_state / fix_commands / docs_ref）
      And stderr 含当前 anchor "ADR-018@a3f7c891b2d4"
      And stderr 含含 anchor 的 --note 模板示例

    Scenario: simple 模式缺 note 阻塞
      When 执行 `spec-vc review --mode simple --message "feat: x [ADR-018]"`
      Then exit code != 0
      And stderr 含 BlockingError，reason 含 "--note required"

    Scenario: --verified flag 写入
      When 执行 `spec-vc review --mode subagent --message "feat: x [ADR-018]" --verified`
      Then review.json.verified == true

    Scenario: 重复 review 覆盖前一次
      Given .git/spec-vc-review.json 已存在
      When 再次执行 `spec-vc review --mode subagent --message "feat: x [ADR-018]"`
      Then review.json 被覆盖
      And review.json.created_at 为最新时间

    Scenario: 无 staged changes 阻塞
      Given staged 区为空
      When 执行 `spec-vc review --message "feat: x [ADR-018]"`
      Then exit code != 0
      And stderr 含 BlockingError，fix_commands 含 "git add ..."

    Scenario: [ADR-???] 未填充阻塞
      When 执行 `spec-vc review --message "feat: x [ADR-???]"`
      Then exit code != 0
      And stderr 含 BlockingError，fix_commands 含 sed 替换示例

  # ─── Rule 2: spec-vc commit 薄包装 ───
  Rule: spec-vc commit 仅做提交动作
    Scenario: commit-msg 已存在 + 全部 hook 通过 → 成功
      Given .git/spec-vc-review.json 与 .git/spec-vc-commit-msg 已存在
      And anchor 匹配当前 staged
      When 执行 `spec-vc commit`
      Then 调用 git commit -F .git/spec-vc-commit-msg
      And exit code == 0
      And HEAD 已推进

    Scenario: commit-msg 不存在阻塞
      Given .git/spec-vc-commit-msg 不存在
      When 执行 `spec-vc commit`
      Then exit code != 0
      And stderr 含 BlockingError，fix_commands 含 "spec-vc review ..."

    Scenario: hook 失败被转译为 BlockingError
      Given commit-msg hook 会返回非 0
      When 执行 `spec-vc commit`
      Then exit code != 0
      And stderr 含原 hook 阻塞输出
      And stderr 含转译后的 BlockingError 结构（不重复 hook 内容，但补充上下文）

  # ─── Rule 3: commit prepare deprecation alias ───
  Rule: commit prepare 保留为 review --mode subagent 别名
    Scenario: 调用 commit prepare 行为等价于 review
      When 执行 `spec-vc commit prepare --message "feat: x [ADR-018]"`
      Then 行为等价于 `spec-vc review --mode subagent --message "feat: x [ADR-018]"`
      And stderr 含 "[spec-vc] DEPRECATION:" 警告

  # ─── Rule 4: commit-msg hook 新校验链 ───
  Rule: commit-msg hook 校验链各分支
    Scenario: SPEC_VC_BYPASS 跳过审计校验
      Given 环境变量 SPEC_VC_BYPASS="hotfix-x"
      And .git/spec-vc-review.json 不存在
      And commit message subject 含 [ADR-018]
      When git commit 触发 commit-msg hook
      Then exit code == 0
      And .git/spec-vc-bypass.log 已写入

    Scenario: [ADR-NNN] + review.json 缺失 → BlockingError
      Given .git/spec-vc-review.json 不存在
      And commit message subject 含 [ADR-018]
      When git commit 触发 commit-msg hook
      Then exit code != 0
      And stderr 含 BlockingError
      And BlockingError.fix_commands 含 "spec-vc review --mode subagent --message ..."
      And BlockingError.docs_ref 含 "ADR-018"

    Scenario: [ADR-NNN] + anchor 不匹配 → BlockingError
      Given .git/spec-vc-review.json.anchor == "ADR-018@aaaaaaaaaaaa"
      And 当前 staged sha12 == "bbbbbbbbbbbb"
      And commit message subject 含 [ADR-018]
      When git commit 触发 commit-msg hook
      Then exit code != 0
      And stderr 含 BlockingError
      And BlockingError.current_state 含 "expected: ADR-018@bbbbbbbbbbbb"
      And BlockingError.current_state 含 "actual: ADR-018@aaaaaaaaaaaa"
      And BlockingError.fix_commands 含 "spec-vc review --message ..."

    Scenario: [ADR-NNN] + review.json mtime 不新鲜 → BlockingError
      Given .git/spec-vc-review.json 的 mtime 早于 .git/spec-vc-commit-msg 的 mtime
      When git commit 触发 commit-msg hook
      Then exit code != 0
      And stderr 含 BlockingError，reason 含 "证据不新鲜"

    Scenario: [ADR-NNN] + simple 模式 + note 不含 anchor → BlockingError
      Given review.json.mode == "simple"
      And review.json.note 不含 review.json.anchor 子串
      When git commit 触发 commit-msg hook
      Then exit code != 0
      And stderr 含 BlockingError

    Scenario: require_user_verified=true 且 verified=false → BlockingError
      Given .spec-vc.toml 中 require_user_verified=true
      And review.json.verified == false
      When git commit 触发 commit-msg hook
      Then exit code != 0
      And stderr 含 BlockingError，reason 含 "用户实际验证未标记"
      And fix_commands 含 "spec-vc review --verified --message ..."

    Scenario: [ADR-NNN] + 全部通过 → 放行
      Given .git/spec-vc-review.json 存在且 anchor 匹配
      And review.json.mtime > .git/spec-vc-commit-msg.mtime
      And Spec 完整性通过
      And plan stage >= implement-ready
      When git commit 触发 commit-msg hook
      Then exit code == 0

  # ─── Rule 5: [ADR-none] 量化判定 ───
  Rule: [ADR-none] 走量化轻量路径
    Scenario: 命中量化规则 → 放行
      Given staged files == ["doc/README.md", "doc/foo.md"]
      And 净变更行数 == 10
      And commit message subject 含 [ADR-none]
      When git commit 触发 commit-msg hook
      Then exit code == 0

    Scenario: 文件数超限 → BlockingError
      Given staged files 数量 == 6（超过 files_max=5）
      And 全部文件类型命中白名单
      And commit message subject 含 [ADR-none]
      When git commit 触发 commit-msg hook
      Then exit code != 0
      And stderr 含 BlockingError，current_state 含 "files_count: 6 > 5"
      And fix_commands 含 "升级为 [ADR-NNN] 或拆分本次 commit"

    Scenario: 文件类型未命中白名单 → BlockingError
      Given staged files 含 "src/foo.py"
      And commit message subject 含 [ADR-none]
      When git commit 触发 commit-msg hook
      Then exit code != 0
      And BlockingError.current_state 含 "unmatched_files: [src/foo.py]"
      And BlockingError.fix_commands 含 "升级为 [ADR-NNN]"

    Scenario: 净变更行数超限 → BlockingError
      Given 净变更行数 == 51
      And commit message subject 含 [ADR-none]
      When git commit 触发 commit-msg hook
      Then exit code != 0
      And BlockingError.current_state 含 "lines_delta: 51 > 50"

  # ─── Rule 6: BlockingError 输出格式契约 ───
  Rule: 所有阻塞输出含完整四段
    Scenario: 任一 hook 或 CLI 阻塞分支
      When 任意阻塞条件触发
      Then stderr 输出含 "[spec-vc] BLOCKED:"
      And stderr 含 "Current state:" 与至少一行事实
      And stderr 含 "How to fix:" 与至少一条 shell 命令（"$ " 前缀）
      And stderr 含 "Docs:" 与至少一条锚点（SKILL.md / ADR-XXX / Spec-XXX）

  # ─── Rule 7: PostToolUse hook 行为保持但降级 ───
  Rule: PostToolUse hook 仍写 session log，但 commit-msg hook 不再读
    Scenario: 启动 Agent 工具 → session log 仍追加
      Given 启动 Agent 工具调用
      When PostToolUse hook 触发
      Then .git/spec-vc-subagent-sessions.log 追加一行（保持 ADR-013 ~ ADR-017 行为）

    Scenario: commit-msg hook 不读 session log
      Given .git/spec-vc-subagent-sessions.log 为空
      And .git/spec-vc-review.json 存在且 anchor 匹配
      When git commit 触发 commit-msg hook
      Then exit code == 0（不再依赖 session log）

  # ─── Rule 8: 自举端到端 ───
  Rule: ADR-018 自身 commit 走新流程
    Scenario: feature 实现 + 单测过 → 通过新 hook 链 commit
      Given ADR-018 代码实现完成
      And pytest 全过
      When 执行 `spec-vc review` + `spec-vc commit`
      Then commit 成功
      And .git/spec-vc-bypass.log 无新增条目
```

---

## 非目标

### 5.1 明确排除的功能
- 不防 simple 模式的真正作弊（AI 仍可在不读 diff 的情况下抄一次 sha12）——只把诚实成本抬到"至少读一次 prepare 输出"
- 不修改 ADR / Spec / Change 持久化数据模型（向后兼容所有现有数据文件）
- 不删除 PostToolUse hook（降级为辅助日志，未来如果证明完全无用再讨论删除）
- 不向后兼容旧的 `.git/spec-vc-audit-anchor` 单文件机制（由 review.json 完全替代，spec-vc 损坏时仍可通过 SPEC_VC_BYPASS 逃生）
- 不在本变更中实现 `require_user_verified=true` 的硬门禁默认开启——仅做配置开关，默认关闭

### 5.2 未来可能扩展
- review.json 增加 `reviewer` 字段记录是哪个 AI / 用户产生的（多 AI 协作时区分）
- 量化规则细化（按 path 分组，前端 / 后端不同阈值）
- 跨 commit 复用 review.json（开发分支多 commit 共享一次审计，需要谨慎设计 anchor 多对一映射）
- 把 BlockingError 序列化成 JSON 供 IDE / 编辑器解析

---

## 非功能性需求

### 6.1 性能要求
| 指标 | 目标值 | 测量方法 |
|------|--------|----------|
| spec-vc review 耗时（单次，subagent 模式仅写文件不含 subagent 自身） | < 500ms | time 命令 |
| commit-msg hook 校验链耗时 | < 200ms | hook 内部计时 |
| lightweight 量化判定耗时 | < 100ms | hook 内部计时 |

### 6.2 可用性要求
- 无网络依赖（全部本地操作）
- 失败必须输出 BlockingError，禁止静默失败

### 6.3 安全要求
- 不引入新的执行用户输入路径
- review.json 与 commit-msg 仅在 .git/ 内，不暴露给仓库外

---

## 错误处理

### 7.1 异常分类
| 类别 | 示例 | 处理策略 |
|------|------|----------|
| 用户输入异常 | --note 缺失、anchor 不含 | BlockingError 输出，exit 非 0 |
| 状态异常 | review.json 缺失、mtime 不新鲜 | BlockingError 输出，exit 非 0 |
| 系统异常 | 无法写 .git/、git 命令失败 | BlockingError 输出 + 原始错误，exit 非 0 |
| 配置异常 | .spec-vc.toml 解析失败 | BlockingError 提示修复配置文件 |

### 7.2 降级策略
- spec-vc 自身损坏（CLI 不可用 / 校验链 bug）→ 用户设 SPEC_VC_BYPASS=<原因> 绕过

### 7.3 重试策略
不适用（同步 CLI 命令，由 AI / 用户决定是否重试）。

---

## 测试策略

### 8.1 验收标准
```gherkin
Given ADR-018 代码实现完成
When 本 ADR 自身的 commit 走新流程
Then spec-vc review + spec-vc commit + commit-msg hook 全过
And .git/spec-vc-bypass.log 无新增条目
And pytest 全部测试通过
```

### 8.2 测试用例
| 测试类型 | 覆盖范围 | 优先级 |
|----------|----------|--------|
| 单元测试 | review 命令 8 项 | P0 |
| 单元测试 | 新 hook 校验链 6 项 | P0 |
| 单元测试 | 量化判定 5 项 | P0 |
| 单元测试 | BlockingError 输出结构断言（每阻塞分支） | P0 |
| 集成测试 | 端到端：review + commit + hook 全过 | P0 |
| 回归测试 | 现有 109 测试不挂（anchor 相关 helper 升级到 review.json） | P0 |
| 自举测试 | 本变更自身 commit 走新流程 | P0 |

### 8.3 边界条件
- staged_sha12 完全相同的两次 review：mtime 更新但 anchor 不变
- staged 包含 0 字节文件
- staged 包含路径含空格的文件
- type_whitelist 配置项为空数组（应视为无文件能匹配，所有 [ADR-none] 都阻塞）
- files_max=0 / lines_max=0 边界
- BYPASS 与 require_user_verified 同时启用（BYPASS 优先）

### 8.4 Mock 策略
- 测试通过临时 git 仓库 + init_repo 隔离
- subagent 不真启动；测试通过手工写 .git/spec-vc-review.json 模拟

---

## 日志实现

### 9.1 日志级别规范
| 级别 | 使用场景 | 示例 |
|------|----------|------|
| BLOCK | hook 阻塞 / CLI 阻塞 | stderr 输出 BlockingError 结构 |
| INFO | 命令成功 | stdout 输出 anchor 与下一步指引 |
| DEPRECATION | commit prepare alias 调用 | stderr "[spec-vc] DEPRECATION:" |

### 9.2 必须记录的事件
| 事件 | 日志位置 | 必须字段 |
|------|----------|----------|
| spec-vc review 成功 | stdout | audit-anchor、下一步指引 |
| commit-msg hook 阻塞 | stderr | BlockingError 四段 |
| SPEC_VC_BYPASS 触发 | .git/spec-vc-bypass.log | timestamp / reason / commit subject |
| PostToolUse 写入 | .git/spec-vc-subagent-sessions.log | timestamp / tool_name / description（保留 ADR-013 ~ ADR-017 行为） |

### 9.3 日志格式
- BlockingError stderr：文本格式（见接口契约 /internal/blocking-error/format）
- bypass log：行式纯文本：`<ISO 时间> | <reason> | <commit subject>`
- subagent sessions log：行式纯文本（保持现有格式）

### 9.4 敏感信息处理
- 不涉及（spec-vc 不处理 PII / 凭证）

### 9.5 日志采样策略
- 全量记录（无采样）

---

## 部署与集成

### 10.1 部署要求
- 依赖服务：无（纯本地）
- 配置项：`.spec-vc.toml` 新增 `[lightweight]` 段（可选，有默认值）
- 环境变量：保持 `SPEC_VC_BYPASS` 语义

### 10.2 数据库迁移
不适用（无数据库）。

### 10.3 向后兼容
- `.git/spec-vc-audit-anchor` 弃用，旧文件残留不影响新流程（新流程不读它）
- `.git/spec-vc-subagent-sessions.log` 保留写入但 commit-msg hook 不读
- `commit prepare` 命令保留为 alias + deprecation warning（至少保留到下一个 ADR 周期）
- 现有 ADR / Spec / Change 数据文件格式不变

---

## 变更历史

| 版本 | 日期 | 作者 | 变更内容 |
|------|------|------|----------|
| 0.1.0 | 2026-05-24 | arcaneorion | 初始版本 |

---

## References

- **ADR**: ADR-018
- **Related Specs**: Spec-013（hook 校验链补完）/ Spec-016（PostToolUse stdin JSON）/ Spec-017（anchor 内容绑定，本 ADR 部分 supersedes 其依赖）
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
