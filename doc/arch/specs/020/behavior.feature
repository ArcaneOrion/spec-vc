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
