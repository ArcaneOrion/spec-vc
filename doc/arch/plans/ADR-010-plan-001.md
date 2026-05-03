# ADR-010 执行方案 001

- **ADR**: ADR-010
- **ADR Title**: 简化提交流程：移除机械 manifest/audit-report/test-report/verify 层，保留 PostToolUse hook 证据链
- **Stage**: close
- **Created At**: 2026-05-03T21:29:02
- **Summary**: 移除机械 manifest/audit-report/test-report/verify 层，简化 prepare/submit 为轻量提交流程

## Clarification

- 动机与上下文: ADR-009 的 PostToolUse hook 在 Harness 层提供了不可伪造的 subagent 审计证据（sessions.log），使得 ADR-005 引入的机械 manifest/audit-report/test-report/verify 层成为冗余。原始意图是'保证多 agent 审计流程被执行'，但实现选错了载体——把审计推迟到提交前一刻的机械格式检查，而非过程级证据。PostToolUse hook 解决了这个偏差：实时记录每次 Agent 调用，AI Bash 工具无法干预。现在可以卸掉机械层，把 commit 协议从 ADR-005+ADR-008 的'重机械验证'收敛到 ADR-009 的'轻量证据链'。
- 目标与边界: 砍掉：src/spec_vc/verify.py、src/spec_vc/manifest.py、tests/python/test_verify.py 三个文件；commit.py 中 build_audit_manifest/write_audit_prompt/prepare_test_prompt/cleanup_tests 及所有 manifest 相关数据类和常量；cli.py 中 cmd_commit_verify、cmd_commit_clean 函数及对应子命令注册，cmd_commit_prepare 中 manifest 生成逻辑，cmd_commit_submit 中 manifest 交叉比对+verify 调用；SKILL.md commit 段中 manifest/audit-report/test-report 描述。保留：token 门禁（write_commit_token/validate_and_consume_token）、PostToolUse hook（run_post_tool_use）、subagent session 检查、BYPASS、commit-msg hook 全部不变。简化后 prepare 只做 Spec check + 写 commit-msg + 写 prepare-ts；submit 只做 TTY 检测 + 交互确认 + basic token + git commit。
- 设计与架构: 三层变更：(1) 删除层——verify.py（run_verify + 三个检查函数）、manifest.py（AuditManifest/AuditUnit/TestUnit/ComplexityReport/AuditFinding/AuditReport/TestUnitResult/TestReport/VerificationResult 数据类）、test_verify.py；(2) 清理层——commit.py 删 build_audit_manifest/write_audit_prompt/prepare_test_prompt/cleanup_tests 及所有 manifest 相关数据类和常量；cli.py 删 cmd_commit_verify/cmd_commit_clean 及对应子命令，简化 cmd_commit_prepare（去掉 manifest 生成）和 cmd_commit_submit（去掉 manifest 交叉比对+verify）；(3) 文档层——SKILL.md commit 段重写，移除 manifest/audit-report/test-report 描述，更新为轻量流程。变更不涉及 hooks.py（commit-msg/PostToolUse 校验链不变），不涉及 token 门禁和 session 检查逻辑。
- 实现路径: (1) 删除 src/spec_vc/verify.py、src/spec_vc/manifest.py、tests/python/test_verify.py。(2) commit.py：删除 build_audit_manifest/write_audit_prompt/prepare_test_prompt/cleanup_tests 函数；删除 AuditManifest/AuditUnit/TestUnit/ComplexityReport 数据类；删除 MANIFEST_FILENAME/AUDIT_REPORT_FILENAME/TEST_REPORT_FILENAME 常量；清理 import（json/math/sys/shutil/re、manifest 模块引用等）。(3) cli.py：删除 cmd_commit_verify 函数+注册（build_parser 中 verify 子命令）；删除 cmd_commit_clean 函数+注册（build_parser 中 clean 子命令）；简化 cmd_commit_prepare——保留 Spec check + write_commit_message + prepare-ts 写入，删除 check_spec_readiness 返回值处理中的额外逻辑、build_audit_manifest 调用、manifest JSON 输出；简化 cmd_commit_submit——保留 TTY 检测 + 确认 + write_commit_token + git commit，删除 manifest_path 交叉比对 + verify 调用。(4) SKILL.md：commit 段（6a-6f）重写，移除 manifest/audit-report/test-report/hash chain 描述，保留 PostToolUse hook 配置说明 + commit-msg hook 校验链 + BYPASS。(5) tests：删除 test_verify.py；更新 test_cli.py 中 prepare/submit 相关测试（移除 manifest 检查断言）；更新 test_commit.py 中相关测试。
- 验证与测试: (1) 改前基线：全量 pytest 通过。(2) 改后验证：prepare 成功执行（写 commit-msg + prepare-ts，不生成 manifest/audit-report/test-report）；submit 在 TTY 确认后成功写 token + git commit（无 manifest 交叉比对）；commit-msg hook 校验链不变（BYPASS→token→subagent session→ADR）；spec check 仍然在 prepare 入口执行；全量 pytest 通过。(3) 验证删除的文件不再被任何 import 引用。
- 风险与回滚: git revert 恢复。风险极低——删除的是已被 ADR-009 判定为冗余的机械验证层，不影响核心 token 门禁/PostToolUse hook/commit-msg hook。


## Clarification History

- 动机与上下文: ADR-009 的 PostToolUse hook 在 Harness 层提供了不可伪造的 subagent 审计证据（sessions.log），使得 ADR-005 引入的机械 manifest/audit-report/test-report/verify 层成为冗余。原始意图是'保证多 agent 审计流程被执行'，但实现选错了载体——把审计推迟到提交前一刻的机械格式检查，而非过程级证据。PostToolUse hook 解决了这个偏差：实时记录每次 Agent 调用，AI Bash 工具无法干预。现在可以卸掉机械层，把 commit 协议从 ADR-005+ADR-008 的'重机械验证'收敛到 ADR-009 的'轻量证据链'。
- 目标与边界: 砍掉：src/spec_vc/verify.py、src/spec_vc/manifest.py、tests/python/test_verify.py 三个文件；commit.py 中 build_audit_manifest/write_audit_prompt/prepare_test_prompt/cleanup_tests 及所有 manifest 相关数据类和常量；cli.py 中 cmd_commit_verify、cmd_commit_clean 函数及对应子命令注册，cmd_commit_prepare 中 manifest 生成逻辑，cmd_commit_submit 中 manifest 交叉比对+verify 调用；SKILL.md commit 段中 manifest/audit-report/test-report 描述。保留：token 门禁（write_commit_token/validate_and_consume_token）、PostToolUse hook（run_post_tool_use）、subagent session 检查、BYPASS、commit-msg hook 全部不变。简化后 prepare 只做 Spec check + 写 commit-msg + 写 prepare-ts；submit 只做 TTY 检测 + 交互确认 + basic token + git commit。
- 设计与架构: 三层变更：(1) 删除层——verify.py（run_verify + 三个检查函数）、manifest.py（AuditManifest/AuditUnit/TestUnit/ComplexityReport/AuditFinding/AuditReport/TestUnitResult/TestReport/VerificationResult 数据类）、test_verify.py；(2) 清理层——commit.py 删 build_audit_manifest/write_audit_prompt/prepare_test_prompt/cleanup_tests 及所有 manifest 相关数据类和常量；cli.py 删 cmd_commit_verify/cmd_commit_clean 及对应子命令，简化 cmd_commit_prepare（去掉 manifest 生成）和 cmd_commit_submit（去掉 manifest 交叉比对+verify）；(3) 文档层——SKILL.md commit 段重写，移除 manifest/audit-report/test-report 描述，更新为轻量流程。变更不涉及 hooks.py（commit-msg/PostToolUse 校验链不变），不涉及 token 门禁和 session 检查逻辑。
- 实现路径: (1) 删除 src/spec_vc/verify.py、src/spec_vc/manifest.py、tests/python/test_verify.py。(2) commit.py：删除 build_audit_manifest/write_audit_prompt/prepare_test_prompt/cleanup_tests 函数；删除 AuditManifest/AuditUnit/TestUnit/ComplexityReport 数据类；删除 MANIFEST_FILENAME/AUDIT_REPORT_FILENAME/TEST_REPORT_FILENAME 常量；清理 import（json/math/sys/shutil/re、manifest 模块引用等）。(3) cli.py：删除 cmd_commit_verify 函数+注册（build_parser 中 verify 子命令）；删除 cmd_commit_clean 函数+注册（build_parser 中 clean 子命令）；简化 cmd_commit_prepare——保留 Spec check + write_commit_message + prepare-ts 写入，删除 check_spec_readiness 返回值处理中的额外逻辑、build_audit_manifest 调用、manifest JSON 输出；简化 cmd_commit_submit——保留 TTY 检测 + 确认 + write_commit_token + git commit，删除 manifest_path 交叉比对 + verify 调用。(4) SKILL.md：commit 段（6a-6f）重写，移除 manifest/audit-report/test-report/hash chain 描述，保留 PostToolUse hook 配置说明 + commit-msg hook 校验链 + BYPASS。(5) tests：删除 test_verify.py；更新 test_cli.py 中 prepare/submit 相关测试（移除 manifest 检查断言）；更新 test_commit.py 中相关测试。
- 验证与测试: (1) 改前基线：全量 pytest 通过。(2) 改后验证：prepare 成功执行（写 commit-msg + prepare-ts，不生成 manifest/audit-report/test-report）；submit 在 TTY 确认后成功写 token + git commit（无 manifest 交叉比对）；commit-msg hook 校验链不变（BYPASS→token→subagent session→ADR）；spec check 仍然在 prepare 入口执行；全量 pytest 通过。(3) 验证删除的文件不再被任何 import 引用。
- 风险与回滚: git revert 恢复。风险极低——删除的是已被 ADR-009 判定为冗余的机械验证层，不影响核心 token 门禁/PostToolUse hook/commit-msg hook。


## Motivation and Context

ADR-009 的 PostToolUse hook 在 Harness 层提供了不可伪造的 subagent 审计证据（sessions.log），使得 ADR-005 引入的机械 manifest/audit-report/test-report/verify 层成为冗余。原始意图是'保证多 agent 审计流程被执行'，但实现选错了载体——把审计推迟到提交前一刻的机械格式检查，而非过程级证据。PostToolUse hook 解决了这个偏差：实时记录每次 Agent 调用，AI Bash 工具无法干预。现在可以卸掉机械层，把 commit 协议从 ADR-005+ADR-008 的'重机械验证'收敛到 ADR-009 的'轻量证据链'。


## Goals and Boundaries

砍掉：src/spec_vc/verify.py、src/spec_vc/manifest.py、tests/python/test_verify.py 三个文件；commit.py 中 build_audit_manifest/write_audit_prompt/prepare_test_prompt/cleanup_tests 及所有 manifest 相关数据类和常量；cli.py 中 cmd_commit_verify、cmd_commit_clean 函数及对应子命令注册，cmd_commit_prepare 中 manifest 生成逻辑，cmd_commit_submit 中 manifest 交叉比对+verify 调用；SKILL.md commit 段中 manifest/audit-report/test-report 描述。保留：token 门禁（write_commit_token/validate_and_consume_token）、PostToolUse hook（run_post_tool_use）、subagent session 检查、BYPASS、commit-msg hook 全部不变。简化后 prepare 只做 Spec check + 写 commit-msg + 写 prepare-ts；submit 只做 TTY 检测 + 交互确认 + basic token + git commit。


## Design and Architecture

三层变更：(1) 删除层——verify.py（run_verify + 三个检查函数）、manifest.py（AuditManifest/AuditUnit/TestUnit/ComplexityReport/AuditFinding/AuditReport/TestUnitResult/TestReport/VerificationResult 数据类）、test_verify.py；(2) 清理层——commit.py 删 build_audit_manifest/write_audit_prompt/prepare_test_prompt/cleanup_tests 及所有 manifest 相关数据类和常量；cli.py 删 cmd_commit_verify/cmd_commit_clean 及对应子命令，简化 cmd_commit_prepare（去掉 manifest 生成）和 cmd_commit_submit（去掉 manifest 交叉比对+verify）；(3) 文档层——SKILL.md commit 段重写，移除 manifest/audit-report/test-report 描述，更新为轻量流程。变更不涉及 hooks.py（commit-msg/PostToolUse 校验链不变），不涉及 token 门禁和 session 检查逻辑。


## Implementation Path

(1) 删除 src/spec_vc/verify.py、src/spec_vc/manifest.py、tests/python/test_verify.py。(2) commit.py：删除 build_audit_manifest/write_audit_prompt/prepare_test_prompt/cleanup_tests 函数；删除 AuditManifest/AuditUnit/TestUnit/ComplexityReport 数据类；删除 MANIFEST_FILENAME/AUDIT_REPORT_FILENAME/TEST_REPORT_FILENAME 常量；清理 import（json/math/sys/shutil/re、manifest 模块引用等）。(3) cli.py：删除 cmd_commit_verify 函数+注册（build_parser 中 verify 子命令）；删除 cmd_commit_clean 函数+注册（build_parser 中 clean 子命令）；简化 cmd_commit_prepare——保留 Spec check + write_commit_message + prepare-ts 写入，删除 check_spec_readiness 返回值处理中的额外逻辑、build_audit_manifest 调用、manifest JSON 输出；简化 cmd_commit_submit——保留 TTY 检测 + 确认 + write_commit_token + git commit，删除 manifest_path 交叉比对 + verify 调用。(4) SKILL.md：commit 段（6a-6f）重写，移除 manifest/audit-report/test-report/hash chain 描述，保留 PostToolUse hook 配置说明 + commit-msg hook 校验链 + BYPASS。(5) tests：删除 test_verify.py；更新 test_cli.py 中 prepare/submit 相关测试（移除 manifest 检查断言）；更新 test_commit.py 中相关测试。


## Verification and Testing

(1) 改前基线：全量 pytest 通过。(2) 改后验证：prepare 成功执行（写 commit-msg + prepare-ts，不生成 manifest/audit-report/test-report）；submit 在 TTY 确认后成功写 token + git commit（无 manifest 交叉比对）；commit-msg hook 校验链不变（BYPASS→token→subagent session→ADR）；spec check 仍然在 prepare 入口执行；全量 pytest 通过。(3) 验证删除的文件不再被任何 import 引用。


## Risks and Rollback

git revert 恢复。风险极低——删除的是已被 ADR-009 判定为冗余的机械验证层，不影响核心 token 门禁/PostToolUse hook/commit-msg hook。


## Affected Areas

待补充

## Pre-Change Validation

待补充

## Post-Change Validation

ADR-010 实施完成：(1) 删除 verify.py(175行)、manifest.py(106行)、test_verify.py(319行)、test_manifest.py(147行)、test_commit_prepare.py(105行)、test_commit_submit.py(126行)。(2) commit.py 从 380 行缩减到 113 行——保留 write_commit_token/validate_and_consume_token/gather_commit_context，删除 build_audit_manifest/write_audit_prompt/prepare_test_prompt/cleanup_tests 及 manifest 所有数据类和常量。(3) cli.py 简化 cmd_commit_prepare（去掉 manifest 生成）、cmd_commit_submit（去掉 manifest 交叉比对/verify），删除 cmd_commit_verify/cmd_commit_clean 及对应子命令注册。(4) SKILL.md commit 段重写为轻量流程，CLAUDE.md 更新。(5) 全量 67 pytest 通过。(6) 删除文件无残留 import 引用。


## Closure Summary

ADR-010 实施完成：移除了 ADR-005 引入的机械 manifest/audit-report/test-report/verify 层，将 commit 协议从重机械验证收敛为轻量证据链。prepare 简化为 Spec check + 写 commit-msg + 写 prepare-ts；submit 简化为 TTY 确认 + basic token + git commit。删除 8 个文件（verify.py/manifest.py/test_verify.py/test_manifest.py/test_commit_prepare.py/test_commit_submit.py），净减少 1374 行代码。67 pytest 全通过。核心防线不变：token 门禁 + PostToolUse hook + subagent session 检查 + BYPASS + commit-msg hook。


## References

- **Commits**: 待从 git 自动采集
- **Plan**: doc/arch/plans/ADR-010-plan-001.md


## Risks and Rollback

待补充

## Checkpoints

- [ ] 澄清完成
- [ ] 前置验证完成
- [ ] 实施完成
- [ ] 后置验证完成
- [ ] ADR 回填完成
