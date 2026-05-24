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
