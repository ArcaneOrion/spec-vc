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
