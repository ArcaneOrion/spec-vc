# ADR-008 执行方案 001

- **ADR**: ADR-008
- **ADR Title**: 引入 TTY-bound commit 机制，将 spec-vc commit 拆分为 prepare/submit 两阶段
- **Stage**: validate
- **Created At**: 2026-05-03T11:42:32
- **Summary**: 将 spec-vc commit 拆分为 prepare/submit 两阶段，token 仅由用户真实 TTY 运行的 submit 写入，AI 无法触发 commit

## Clarification

- 动机与上下文: ADR-006 token 门禁存在设计漏洞：spec-vc commit 在 manifest 输出之前就写入 token，token 仅证明'命令被调用过'，不证明审计子流程完成。AI 可调用 spec-vc commit 拿 token 后丢弃 manifest，5 分钟内在无审计的情况下直接 git commit。ADR-007 SPEC_VC_BYPASS 作为逃生口本是给用户应急用的，但在当前 token 语义下对 AI 同样可用。问题本质是 token 无法区分'AI 调用的 commit'和'用户发起的提交'——机制边界与权限边界错位。
- 目标与边界: 将 spec-vc commit 拆分为 prepare 和 submit 两阶段。prepare（AI 调用）：Spec 就绪检查 + 生成 manifest + 写入 .git/spec-vc-manifest.json + .git/spec-vc-commit-msg，不写 token。AI 读 manifest 跑 subagent 审计后写入 audit-report.json 和 test-report.json。submit（用户 TTY 调用）：os.isatty 检测 + 重新生成 manifest 交叉比对 + 跑 verify + 交互确认 + 写 token（含 hash chain）+ 执行 git commit。token 语义升级为'用户确认 + 审计完成 + 报告未被篡改'。SPEC_VC_BYPASS 保留为 raw escape（跳过 token 存在性校验），在 spec-vc binary 真正损坏时可用。不含 L3-B（OOB 确认）、不含 spec-vc 内置 subagent、不含 termios 加密确认。
- 设计与架构: 四层变更：(1) commit.py 新增 cmd_commit_prepare 和 cmd_commit_submit，原 cmd_commit 逻辑拆分到 prepare。(2) write_commit_token 升级为 write_commit_token_with_hash_chain，token 内容从 uuid+timestamp 扩展为 uuid+timestamp+manifest_hash+audit_hash+test_hash。(3) hooks.py commit-msg hook 新增 hash chain 校验：读 token 内 3 个哈希，重新计算 .git/ 下对应文件哈希并比对。SPEC_VC_BYPASS 分支保留在 token 校验之前，跳过存在性校验但不跳过 ADR 引用校验。(4) SKILL.md commit 段重写为 prepare/submit 两阶段协议，明确 AI 停在 prepare 之后提示用户运行 submit。交叉比对机制：submit 重新从当前仓库状态生成 manifest 并与 .git/spec-vc-manifest.json 逐项比对，防止 prepare 后提交前文件被篡改。
- 实现路径: (1) cli.py: 在 build_parser 中新增 prepare 子命令（--message 参数）和 submit 子命令（无参数），cmd_commit_prepare 覆盖原 cmd_commit 前半段（spec check + manifest 生成 + 写入 .git），cmd_commit_submit 实现 TTY 检测 + 交叉比对 + verify + token + commit。(2) commit.py: write_commit_token 签名改为接受 manifest_hash/audit_hash/test_hash；新增 build_commit_message 写入 .git/spec-vc-commit-msg。(3) hooks.py: validate_and_consume_token 新增 hash_chain 校验分支；更新错误提示信息反映 prepare/submit 流程。(4) SKILL.md: commit 段全部重写，删除原有单一 cmd_commit 协议，替换为 prepare-submit 两阶段。(5) tests/python/: 新增 test_commit_prepare.py 覆盖 prepare 行为（写 manifest 不写 token、prepare 空 staged 返回 0）；新增 test_commit_submit.py 覆盖 submit 行为（非 TTY 拒绝、manifest 不匹配拒绝、缺 report 拒绝、端到端成功）；更新 test_hooks.py 覆盖 hash chain 校验（篡改 report 后 hook 阻塞、bypass 仍跳过 token 存在性）；确保现有 94 个测试全部通过（如有变更更新对应测试）。(6) CLAUDE.md: 更新常用命令和 commit 相关说明。
- 验证与测试: (1) 改前：运行全量 pytest，建立基线（当前 94 个）。用你披露的手法复现漏洞：spec-vc commit 2>/dev/null > /dev/null 后 git commit -m '...'，确认当前可通过（token 存在期内）。(2) 改后：复现手法失效——prepare 不写 token，git commit 被 hook 阻塞；submit 在非 TTY 环境被拒绝（CI 模拟或管道调用）；端到端 prepare→submit 成功提交且 token 包含 hash chain；篡改 .git/spec-vc-manifest.json 后 submit 交叉比对失败阻塞；篡改 audit-report 后 hook 阻塞；SPEC_VC_BYPASS 设置后仍可跳过 token 存在性校验放行。(3) 新增 7 个测试 + 基线 94 = 101，全部通过。
- 风险与回滚: (1) TTY 检测绕过：os.isatty() 可被 script 命令或 pty 包装绕过，方案为初始防线+SKILL.md 禁令，未来按需升级 termios。(2) submit 和 git commit 之间有极短时间窗可篡改 staged files，hook 在 commit-msg 阶段二次校验 hash chain 作为保险。(3) .git/ 下 manifest/report 在 prepare-submit 之间被意外清理则 submit 阻塞提示重新 prepare。(4) 如果 prepare/submit 引入致命 bug 需紧急提交，SPEC_VC_BYPASS 保留为 raw escape，或 chmod -x .git/hooks/commit-msg 为最终物理兜底。(5) 回滚路径：git revert 变更 commit 后 token 门禁回到 ADR-006 状态，功能无退化。


## Clarification History

- 动机与上下文: ADR-006 token 门禁存在设计漏洞：spec-vc commit 在 manifest 输出之前就写入 token，token 仅证明'命令被调用过'，不证明审计子流程完成。AI 可调用 spec-vc commit 拿 token 后丢弃 manifest，5 分钟内在无审计的情况下直接 git commit。ADR-007 SPEC_VC_BYPASS 作为逃生口本是给用户应急用的，但在当前 token 语义下对 AI 同样可用。问题本质是 token 无法区分'AI 调用的 commit'和'用户发起的提交'——机制边界与权限边界错位。
- 目标与边界: 将 spec-vc commit 拆分为 prepare 和 submit 两阶段。prepare（AI 调用）：Spec 就绪检查 + 生成 manifest + 写入 .git/spec-vc-manifest.json + .git/spec-vc-commit-msg，不写 token。AI 读 manifest 跑 subagent 审计后写入 audit-report.json 和 test-report.json。submit（用户 TTY 调用）：os.isatty 检测 + 重新生成 manifest 交叉比对 + 跑 verify + 交互确认 + 写 token（含 hash chain）+ 执行 git commit。token 语义升级为'用户确认 + 审计完成 + 报告未被篡改'。SPEC_VC_BYPASS 保留为 raw escape（跳过 token 存在性校验），在 spec-vc binary 真正损坏时可用。不含 L3-B（OOB 确认）、不含 spec-vc 内置 subagent、不含 termios 加密确认。
- 设计与架构: 四层变更：(1) commit.py 新增 cmd_commit_prepare 和 cmd_commit_submit，原 cmd_commit 逻辑拆分到 prepare。(2) write_commit_token 升级为 write_commit_token_with_hash_chain，token 内容从 uuid+timestamp 扩展为 uuid+timestamp+manifest_hash+audit_hash+test_hash。(3) hooks.py commit-msg hook 新增 hash chain 校验：读 token 内 3 个哈希，重新计算 .git/ 下对应文件哈希并比对。SPEC_VC_BYPASS 分支保留在 token 校验之前，跳过存在性校验但不跳过 ADR 引用校验。(4) SKILL.md commit 段重写为 prepare/submit 两阶段协议，明确 AI 停在 prepare 之后提示用户运行 submit。交叉比对机制：submit 重新从当前仓库状态生成 manifest 并与 .git/spec-vc-manifest.json 逐项比对，防止 prepare 后提交前文件被篡改。
- 实现路径: (1) cli.py: 在 build_parser 中新增 prepare 子命令（--message 参数）和 submit 子命令（无参数），cmd_commit_prepare 覆盖原 cmd_commit 前半段（spec check + manifest 生成 + 写入 .git），cmd_commit_submit 实现 TTY 检测 + 交叉比对 + verify + token + commit。(2) commit.py: write_commit_token 签名改为接受 manifest_hash/audit_hash/test_hash；新增 build_commit_message 写入 .git/spec-vc-commit-msg。(3) hooks.py: validate_and_consume_token 新增 hash_chain 校验分支；更新错误提示信息反映 prepare/submit 流程。(4) SKILL.md: commit 段全部重写，删除原有单一 cmd_commit 协议，替换为 prepare-submit 两阶段。(5) tests/python/: 新增 test_commit_prepare.py 覆盖 prepare 行为（写 manifest 不写 token、prepare 空 staged 返回 0）；新增 test_commit_submit.py 覆盖 submit 行为（非 TTY 拒绝、manifest 不匹配拒绝、缺 report 拒绝、端到端成功）；更新 test_hooks.py 覆盖 hash chain 校验（篡改 report 后 hook 阻塞、bypass 仍跳过 token 存在性）；确保现有 94 个测试全部通过（如有变更更新对应测试）。(6) CLAUDE.md: 更新常用命令和 commit 相关说明。
- 验证与测试: (1) 改前：运行全量 pytest，建立基线（当前 94 个）。用你披露的手法复现漏洞：spec-vc commit 2>/dev/null > /dev/null 后 git commit -m '...'，确认当前可通过（token 存在期内）。(2) 改后：复现手法失效——prepare 不写 token，git commit 被 hook 阻塞；submit 在非 TTY 环境被拒绝（CI 模拟或管道调用）；端到端 prepare→submit 成功提交且 token 包含 hash chain；篡改 .git/spec-vc-manifest.json 后 submit 交叉比对失败阻塞；篡改 audit-report 后 hook 阻塞；SPEC_VC_BYPASS 设置后仍可跳过 token 存在性校验放行。(3) 新增 7 个测试 + 基线 94 = 101，全部通过。
- 风险与回滚: (1) TTY 检测绕过：os.isatty() 可被 script 命令或 pty 包装绕过，方案为初始防线+SKILL.md 禁令，未来按需升级 termios。(2) submit 和 git commit 之间有极短时间窗可篡改 staged files，hook 在 commit-msg 阶段二次校验 hash chain 作为保险。(3) .git/ 下 manifest/report 在 prepare-submit 之间被意外清理则 submit 阻塞提示重新 prepare。(4) 如果 prepare/submit 引入致命 bug 需紧急提交，SPEC_VC_BYPASS 保留为 raw escape，或 chmod -x .git/hooks/commit-msg 为最终物理兜底。(5) 回滚路径：git revert 变更 commit 后 token 门禁回到 ADR-006 状态，功能无退化。


## Motivation and Context

ADR-006 token 门禁存在设计漏洞：spec-vc commit 在 manifest 输出之前就写入 token，token 仅证明'命令被调用过'，不证明审计子流程完成。AI 可调用 spec-vc commit 拿 token 后丢弃 manifest，5 分钟内在无审计的情况下直接 git commit。ADR-007 SPEC_VC_BYPASS 作为逃生口本是给用户应急用的，但在当前 token 语义下对 AI 同样可用。问题本质是 token 无法区分'AI 调用的 commit'和'用户发起的提交'——机制边界与权限边界错位。


## Goals and Boundaries

将 spec-vc commit 拆分为 prepare 和 submit 两阶段。prepare（AI 调用）：Spec 就绪检查 + 生成 manifest + 写入 .git/spec-vc-manifest.json + .git/spec-vc-commit-msg，不写 token。AI 读 manifest 跑 subagent 审计后写入 audit-report.json 和 test-report.json。submit（用户 TTY 调用）：os.isatty 检测 + 重新生成 manifest 交叉比对 + 跑 verify + 交互确认 + 写 token（含 hash chain）+ 执行 git commit。token 语义升级为'用户确认 + 审计完成 + 报告未被篡改'。SPEC_VC_BYPASS 保留为 raw escape（跳过 token 存在性校验），在 spec-vc binary 真正损坏时可用。不含 L3-B（OOB 确认）、不含 spec-vc 内置 subagent、不含 termios 加密确认。


## Design and Architecture

四层变更：(1) commit.py 新增 cmd_commit_prepare 和 cmd_commit_submit，原 cmd_commit 逻辑拆分到 prepare。(2) write_commit_token 升级为 write_commit_token_with_hash_chain，token 内容从 uuid+timestamp 扩展为 uuid+timestamp+manifest_hash+audit_hash+test_hash。(3) hooks.py commit-msg hook 新增 hash chain 校验：读 token 内 3 个哈希，重新计算 .git/ 下对应文件哈希并比对。SPEC_VC_BYPASS 分支保留在 token 校验之前，跳过存在性校验但不跳过 ADR 引用校验。(4) SKILL.md commit 段重写为 prepare/submit 两阶段协议，明确 AI 停在 prepare 之后提示用户运行 submit。交叉比对机制：submit 重新从当前仓库状态生成 manifest 并与 .git/spec-vc-manifest.json 逐项比对，防止 prepare 后提交前文件被篡改。


## Implementation Path

(1) cli.py: 在 build_parser 中新增 prepare 子命令（--message 参数）和 submit 子命令（无参数），cmd_commit_prepare 覆盖原 cmd_commit 前半段（spec check + manifest 生成 + 写入 .git），cmd_commit_submit 实现 TTY 检测 + 交叉比对 + verify + token + commit。(2) commit.py: write_commit_token 签名改为接受 manifest_hash/audit_hash/test_hash；新增 build_commit_message 写入 .git/spec-vc-commit-msg。(3) hooks.py: validate_and_consume_token 新增 hash_chain 校验分支；更新错误提示信息反映 prepare/submit 流程。(4) SKILL.md: commit 段全部重写，删除原有单一 cmd_commit 协议，替换为 prepare-submit 两阶段。(5) tests/python/: 新增 test_commit_prepare.py 覆盖 prepare 行为（写 manifest 不写 token、prepare 空 staged 返回 0）；新增 test_commit_submit.py 覆盖 submit 行为（非 TTY 拒绝、manifest 不匹配拒绝、缺 report 拒绝、端到端成功）；更新 test_hooks.py 覆盖 hash chain 校验（篡改 report 后 hook 阻塞、bypass 仍跳过 token 存在性）；确保现有 94 个测试全部通过（如有变更更新对应测试）。(6) CLAUDE.md: 更新常用命令和 commit 相关说明。


## Verification and Testing

(1) 改前：运行全量 pytest，建立基线（当前 94 个）。用你披露的手法复现漏洞：spec-vc commit 2>/dev/null > /dev/null 后 git commit -m '...'，确认当前可通过（token 存在期内）。(2) 改后：复现手法失效——prepare 不写 token，git commit 被 hook 阻塞；submit 在非 TTY 环境被拒绝（CI 模拟或管道调用）；端到端 prepare→submit 成功提交且 token 包含 hash chain；篡改 .git/spec-vc-manifest.json 后 submit 交叉比对失败阻塞；篡改 audit-report 后 hook 阻塞；SPEC_VC_BYPASS 设置后仍可跳过 token 存在性校验放行。(3) 新增 7 个测试 + 基线 94 = 101，全部通过。


## Risks and Rollback

(1) TTY 检测绕过：os.isatty() 可被 script 命令或 pty 包装绕过，方案为初始防线+SKILL.md 禁令，未来按需升级 termios。(2) submit 和 git commit 之间有极短时间窗可篡改 staged files，hook 在 commit-msg 阶段二次校验 hash chain 作为保险。(3) .git/ 下 manifest/report 在 prepare-submit 之间被意外清理则 submit 阻塞提示重新 prepare。(4) 如果 prepare/submit 引入致命 bug 需紧急提交，SPEC_VC_BYPASS 保留为 raw escape，或 chmod -x .git/hooks/commit-msg 为最终物理兜底。(5) 回滚路径：git revert 变更 commit 后 token 门禁回到 ADR-006 状态，功能无退化。


## Affected Areas

待补充

## Pre-Change Validation

基线94个pytest全部通过。漏洞复现成功：spec-vc commit 2>/dev/null > /dev/null 生成token后，git commit -m 'test: exploit reproduction [ADR-008]' 直接通过且创建commit——token仅证明命令被调用过，不证明审计子流程完成。此commit已通过git reset --soft撤销并清理。当前工作区干净，Spec-003三个形式化文件已生成，spec check全部就绪。


## Post-Change Validation

改后验证：(1) 全量 107 个 pytest 通过（基线 94 + 新增 13：test_commit_prepare 6 个 + test_commit_submit 4 个 + test_cli hash chain 3 个）。(2) prepare 不写 token——spec-vc commit prepare 后 .git/spec-vc-commit-token 不存在，直接 git commit 被 hook 阻塞输出'未找到提交 token。请通过 spec-vc commit prepare + submit 流程提交代码'。(3) 旧 exploit（spec-vc commit 无子命令生成 token 后 git commit）不再有效——commit 无子命令时返回 1 提示指定子命令。(4) hook hash chain 校验：合法 token（5行含3哈希）匹配时通过并消费；篡改 audit-report 后哈希不匹配阻塞输出'不匹配'。(5) SPEC_VC_BYPASS 保留为 raw escape——设置后无 token 仍可 git commit 且写 bypass 日志。(6) 错误提示信息已更新为 prepare + submit 流程指引。


## Closure Summary

待补充

## References

- **Commits**: 待补充
- **Plan**: 待补充

## Risks and Rollback

待补充

## Checkpoints

- [ ] 澄清完成
- [ ] 前置验证完成
- [ ] 实施完成
- [ ] 后置验证完成
- [ ] ADR 回填完成
