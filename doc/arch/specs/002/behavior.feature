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
