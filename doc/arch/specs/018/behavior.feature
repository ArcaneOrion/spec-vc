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
