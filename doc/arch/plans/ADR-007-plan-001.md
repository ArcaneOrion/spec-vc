# ADR-007 执行方案 001

- **ADR**: ADR-007
- **ADR Title**: 为 commit token 门禁引入 emergency bypass 机制
- **Stage**: close
- **Created At**: 2026-04-30T21:29:53
- **Summary**: 为 ADR-006 token 门禁补 emergency 逃生口：环境变量 SPEC_VC_BYPASS 非空跳过 token 校验并写审计日志（fail-open）

## Clarification

- 动机与上下文: ADR-006 token 门禁把'必须经过 spec-vc commit'升级为机制约束，但同时引入单点故障：commit-msg hook 调用 ~/.claude/skills/spec-vc/.venv/bin/spec-vc，binary 损坏 / skill 路径变更 / venv 错乱时整个仓库 commit 通道锁死。开源前需要最简逃生口，但不能稀释 token 门禁本身的约束力（不提供配置项永久关闭、不提供 CLI flag）。
- 目标与边界: 做：环境变量 SPEC_VC_BYPASS 非空时 hook 跳过 token 校验，并写审计日志到 .git/spec-vc-bypass.log（fail-open，写入失败仅 stderr 警告，hook 仍放行）。不做：双触发通道（git config + env）、commit message 追加 [BYPASS] 标记、配置项 / CLI flag 永久关闭、强制原因白名单、跨克隆审计同步。ADR 引用 + 豁免规则照常生效，只跳过 token 校验。
- 设计与架构: 在 hooks.py:run_commit_msg 的 validate_and_consume_token 调用之前插入分支：os.environ.get('SPEC_VC_BYPASS') 非空 → 跳过 token 校验 → try 写审计日志一行（格式：ISO 时间 | 原因 | commit subject）→ except OSError 时 stderr 输出警告但仍放行 → 继续走原有 ADR 引用 + 豁免规则校验。日志文件位于 .git/spec-vc-bypass.log，git 不追踪，与 .git/spec-vc-commit-token 同性质。错误提示信息显式列出 SPEC_VC_BYPASS 用法，降低拼错概率。
- 实现路径: 首先修改 hooks.py:run_commit_msg 添加 bypass 分支（约 8-10 行）；其次修改 commit-msg 阻塞提示信息加 SPEC_VC_BYPASS=<原因> git commit 用法说明；然后新增 pytest 测试三个：bypass 触发放行 + 日志写入、无 bypass 走原 token 校验、日志路径不可写仍放行（fail-open）；最后 README 末尾追加'紧急绕过 / Troubleshooting'段说明环境变量用法和 chmod -x .git/hooks/commit-msg 兜底。
- 验证与测试: pytest tests/python/ 全量通过（基线 91 + 新增 3 = 94）。手动验证：a) SPEC_VC_BYPASS=1 git commit 在无 token 时也能放行；b) 无 SPEC_VC_BYPASS 时 git commit 仍被 token 门禁阻塞；c) bypass 后 .git/spec-vc-bypass.log 出现新行；d) 把 .git 改为只读后 SPEC_VC_BYPASS=1 git commit 仍能放行（fail-open 验证）；e) README 紧急绕过指引按字面执行可走通。
- 风险与回滚: 滥用风险：bypass 可能被习惯性使用（用户填 SPEC_VC_BYPASS=1 而非真实原因）—— 单人项目可接受，开源后通过观察日志中原因分布识别滥用模式，必要时再加 commit 标记或团队审计工具（不在 ADR-007 范围）。机制本身崩溃：手工 chmod -x .git/hooks/commit-msg 让 git 跳过 hook（git 原生兜底），README 写明此路径。代码回滚：单 commit reset 即可，token 门禁回到 ADR-006 实施状态。


## Clarification History

- 动机与上下文: ADR-006 token 门禁把'必须经过 spec-vc commit'升级为机制约束，但同时引入单点故障：commit-msg hook 调用 ~/.claude/skills/spec-vc/.venv/bin/spec-vc，binary 损坏 / skill 路径变更 / venv 错乱时整个仓库 commit 通道锁死。开源前需要最简逃生口，但不能稀释 token 门禁本身的约束力（不提供配置项永久关闭、不提供 CLI flag）。
- 目标与边界: 做：环境变量 SPEC_VC_BYPASS 非空时 hook 跳过 token 校验，并写审计日志到 .git/spec-vc-bypass.log（fail-open，写入失败仅 stderr 警告，hook 仍放行）。不做：双触发通道（git config + env）、commit message 追加 [BYPASS] 标记、配置项 / CLI flag 永久关闭、强制原因白名单、跨克隆审计同步。ADR 引用 + 豁免规则照常生效，只跳过 token 校验。
- 设计与架构: 在 hooks.py:run_commit_msg 的 validate_and_consume_token 调用之前插入分支：os.environ.get('SPEC_VC_BYPASS') 非空 → 跳过 token 校验 → try 写审计日志一行（格式：ISO 时间 | 原因 | commit subject）→ except OSError 时 stderr 输出警告但仍放行 → 继续走原有 ADR 引用 + 豁免规则校验。日志文件位于 .git/spec-vc-bypass.log，git 不追踪，与 .git/spec-vc-commit-token 同性质。错误提示信息显式列出 SPEC_VC_BYPASS 用法，降低拼错概率。
- 实现路径: 首先修改 hooks.py:run_commit_msg 添加 bypass 分支（约 8-10 行）；其次修改 commit-msg 阻塞提示信息加 SPEC_VC_BYPASS=<原因> git commit 用法说明；然后新增 pytest 测试三个：bypass 触发放行 + 日志写入、无 bypass 走原 token 校验、日志路径不可写仍放行（fail-open）；最后 README 末尾追加'紧急绕过 / Troubleshooting'段说明环境变量用法和 chmod -x .git/hooks/commit-msg 兜底。
- 验证与测试: pytest tests/python/ 全量通过（基线 91 + 新增 3 = 94）。手动验证：a) SPEC_VC_BYPASS=1 git commit 在无 token 时也能放行；b) 无 SPEC_VC_BYPASS 时 git commit 仍被 token 门禁阻塞；c) bypass 后 .git/spec-vc-bypass.log 出现新行；d) 把 .git 改为只读后 SPEC_VC_BYPASS=1 git commit 仍能放行（fail-open 验证）；e) README 紧急绕过指引按字面执行可走通。
- 风险与回滚: 滥用风险：bypass 可能被习惯性使用（用户填 SPEC_VC_BYPASS=1 而非真实原因）—— 单人项目可接受，开源后通过观察日志中原因分布识别滥用模式，必要时再加 commit 标记或团队审计工具（不在 ADR-007 范围）。机制本身崩溃：手工 chmod -x .git/hooks/commit-msg 让 git 跳过 hook（git 原生兜底），README 写明此路径。代码回滚：单 commit reset 即可，token 门禁回到 ADR-006 实施状态。


## Motivation and Context

ADR-006 token 门禁把'必须经过 spec-vc commit'升级为机制约束，但同时引入单点故障：commit-msg hook 调用 ~/.claude/skills/spec-vc/.venv/bin/spec-vc，binary 损坏 / skill 路径变更 / venv 错乱时整个仓库 commit 通道锁死。开源前需要最简逃生口，但不能稀释 token 门禁本身的约束力（不提供配置项永久关闭、不提供 CLI flag）。


## Goals and Boundaries

做：环境变量 SPEC_VC_BYPASS 非空时 hook 跳过 token 校验，并写审计日志到 .git/spec-vc-bypass.log（fail-open，写入失败仅 stderr 警告，hook 仍放行）。不做：双触发通道（git config + env）、commit message 追加 [BYPASS] 标记、配置项 / CLI flag 永久关闭、强制原因白名单、跨克隆审计同步。ADR 引用 + 豁免规则照常生效，只跳过 token 校验。


## Design and Architecture

在 hooks.py:run_commit_msg 的 validate_and_consume_token 调用之前插入分支：os.environ.get('SPEC_VC_BYPASS') 非空 → 跳过 token 校验 → try 写审计日志一行（格式：ISO 时间 | 原因 | commit subject）→ except OSError 时 stderr 输出警告但仍放行 → 继续走原有 ADR 引用 + 豁免规则校验。日志文件位于 .git/spec-vc-bypass.log，git 不追踪，与 .git/spec-vc-commit-token 同性质。错误提示信息显式列出 SPEC_VC_BYPASS 用法，降低拼错概率。


## Implementation Path

首先修改 hooks.py:run_commit_msg 添加 bypass 分支（约 8-10 行）；其次修改 commit-msg 阻塞提示信息加 SPEC_VC_BYPASS=<原因> git commit 用法说明；然后新增 pytest 测试三个：bypass 触发放行 + 日志写入、无 bypass 走原 token 校验、日志路径不可写仍放行（fail-open）；最后 README 末尾追加'紧急绕过 / Troubleshooting'段说明环境变量用法和 chmod -x .git/hooks/commit-msg 兜底。


## Verification and Testing

pytest tests/python/ 全量通过（基线 91 + 新增 3 = 94）。手动验证：a) SPEC_VC_BYPASS=1 git commit 在无 token 时也能放行；b) 无 SPEC_VC_BYPASS 时 git commit 仍被 token 门禁阻塞；c) bypass 后 .git/spec-vc-bypass.log 出现新行；d) 把 .git 改为只读后 SPEC_VC_BYPASS=1 git commit 仍能放行（fail-open 验证）；e) README 紧急绕过指引按字面执行可走通。


## Risks and Rollback

滥用风险：bypass 可能被习惯性使用（用户填 SPEC_VC_BYPASS=1 而非真实原因）—— 单人项目可接受，开源后通过观察日志中原因分布识别滥用模式，必要时再加 commit 标记或团队审计工具（不在 ADR-007 范围）。机制本身崩溃：手工 chmod -x .git/hooks/commit-msg 让 git 跳过 hook（git 原生兜底），README 写明此路径。代码回滚：单 commit reset 即可，token 门禁回到 ADR-006 实施状态。


## Affected Areas

待补充

## Pre-Change Validation

修改前状态：1) hooks.py:run_commit_msg 不检查 SPEC_VC_BYPASS 环境变量，token 校验无逃生口——spec-vc binary 损坏 / skill 路径变更会锁死整个仓库 commit；2) 阻塞错误信息仅提示'请通过 spec-vc commit 流程提交代码'，未列出 bypass 用法，用户无法发现逃生路径；3) 全量 pytest 基线 91 个测试通过（90 历史 + 1 个 _sections bug fix）；4) .git/spec-vc-bypass.log 不存在；5) README 无紧急绕过 / Troubleshooting 段。已通过 spec check 确认 Spec-002 全部就绪可作为审计依据。


## Post-Change Validation

修改后验证：1) 94/94 pytest 全部通过（基线 91 + 新增 3 个 bypass 测试）；2) SPEC_VC_BYPASS=hotfix hook commit-msg 无 token 时放行且 .git/spec-vc-bypass.log 新增一行含 'hotfix' 和 commit subject；3) SPEC_VC_BYPASS 未设置时 git commit 仍被 token 门禁阻塞；4) 阻塞错误信息显式打印 SPEC_VC_BYPASS 用法；5) 把 .git/spec-vc-bypass.log 做成目录后 SPEC_VC_BYPASS=repair 仍能 commit（fail-open 验证通过）；6) README 末尾新增'紧急绕过'段，说明环境变量用法、原因字段建议和 chmod -x 兜底方案。


## Closure Summary

ADR-007 成功为 ADR-006 token 门禁引入最简 emergency bypass 机制：在 hooks.py:run_commit_msg 中增加环境变量 SPEC_VC_BYPASS 检查分支——非空时跳过 token 校验并写审计日志到 .git/spec-vc-bypass.log（fail-open，写入失败仅 stderr 警告仍放行）；ADR 引用与豁免规则照常生效，仅跳过 token 校验。同步更新 commit.py 错误提示信息显式列出 bypass 用法；README 新增'紧急绕过'段说明环境变量用法和 chmod -x .git/hooks/commit-msg 最终兜底方案。新增 3 个 pytest 测试覆盖 bypass 触发、空字符串回退 token 校验、日志写入失败仍放行三种场景。全量 94 测试通过。本次变更也是 spec-vc 首次完整 dogfooding——从 ADR-007 决策→Spec-002 行为规则→pre/post validation→close 回填全链路闭环。过程暴露并修复了 _sections.py replace_section 在 body 以数字开头时触发 invalid group reference 的 bug（已在 [ADR-005] 下独立修复）。


## References

- **Commits**: 待从 git 自动采集
- **Plan**: doc/arch/plans/ADR-007-plan-001.md


## Risks and Rollback

待补充

## Checkpoints

- [ ] 澄清完成
- [ ] 前置验证完成
- [ ] 实施完成
- [ ] 后置验证完成
- [ ] ADR 回填完成
