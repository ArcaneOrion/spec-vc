# ADR-012 执行方案 001

- **ADR**: ADR-012
- **ADR Title**: 门禁消息增强：失败时返回可执行指引而非仅阻塞
- **Stage**: close
- **Created At**: 2026-05-08T12:28:51
- **Summary**: 门禁失败时返回可执行指引而非仅阻塞，强化 AI 正确行为意图：commit-msg hook 错误消息增加下一步指引 + SKILL.md 引用；change validate --phase pre 增加 clarify 完整性检查和 ADR→Spec 关联检查

## Clarification

- 动机与上下文: ADR-011 实施过程中暴露两个流程断点：(1) change validate --phase pre 不检查 clarify 完整性和 ADR→Spec 关联关系，AI 可以跳过 Spec 创作协议直接改代码；(2) 门禁阻塞消息只有功能性描述没有可执行指引，AI 读到后不知道正确下一步该做什么。门禁设计假设使用者是人类，但实际主要使用者是 AI Agent。
- 目标与边界: 增强所有门禁阻塞消息，加入可执行指引和 SKILL.md 引用。增加 change validate --phase pre 的 clarify 完整性检查和 ADR→Spec 关联检查。不改变流程本身（不增加 PreToolUse hook，不改 _active.md 结构），只改门禁消息的内容和检查范围。
- 设计与架构: hooks.py 5 处错误消息增加下一步指引 + SKILL.md 引用。cli.py 中 commit prepare 输出改为列举 hook 校验项并引用 SKILL.md。cli.py 中 change validate --phase pre 增加 clarify 完整性检查和 ADR→Spec 关联检查。change.py 新增 has_associated_spec() 辅助函数。
- 实现路径: 1. hooks.py: check_subagent_session 错误消息加 Agent 工具指引和 spec-vc init 提示；_check_plan_stage 错误消息加 change validate --phase pre 命令指引；_check_spec_readiness_for_adr 错误消息加 spec new/formalize/check 分步指引；HELP_MISSING/HELP_SLOT 加 SKILL.md 引用。2. cli.py: cmd_commit_prepare 输出改写为列举 4 项 hook 校验 + SKILL.md 引用；cmd_change_validate pre 阶段增加 clarify 检查和 Spec 关联检查。3. change.py: 新增 has_associated_spec(repo_root, config, adr_id) 检查 ADR 是否有关联 Spec。4. 测试更新：匹配新错误消息格式，新增 ADR→Spec 关联检查测试。
- 验证与测试: 1. pytest 全量测试通过。2. hook 阻塞消息包含可执行指引和 SKILL.md 引用。3. validate --phase pre 在 clarify 未完成时阻塞并提示。4. validate --phase pre 在 ADR 无关联 Spec 时提示走 Spec 创作协议。5. commit prepare 输出正确描述新流程。
- 风险与回滚: git revert 回退所有变更。改动集中在 hooks.py/cli.py/change.py 三个文件加测试，回退范围明确。


## Clarification History

- 动机与上下文: ADR-011 实施过程中暴露两个流程断点：(1) change validate --phase pre 不检查 clarify 完整性和 ADR→Spec 关联关系，AI 可以跳过 Spec 创作协议直接改代码；(2) 门禁阻塞消息只有功能性描述没有可执行指引，AI 读到后不知道正确下一步该做什么。门禁设计假设使用者是人类，但实际主要使用者是 AI Agent。
- 目标与边界: 增强所有门禁阻塞消息，加入可执行指引和 SKILL.md 引用。增加 change validate --phase pre 的 clarify 完整性检查和 ADR→Spec 关联检查。不改变流程本身（不增加 PreToolUse hook，不改 _active.md 结构），只改门禁消息的内容和检查范围。
- 设计与架构: hooks.py 5 处错误消息增加下一步指引 + SKILL.md 引用。cli.py 中 commit prepare 输出改为列举 hook 校验项并引用 SKILL.md。cli.py 中 change validate --phase pre 增加 clarify 完整性检查和 ADR→Spec 关联检查。change.py 新增 has_associated_spec() 辅助函数。
- 实现路径: 1. hooks.py: check_subagent_session 错误消息加 Agent 工具指引和 spec-vc init 提示；_check_plan_stage 错误消息加 change validate --phase pre 命令指引；_check_spec_readiness_for_adr 错误消息加 spec new/formalize/check 分步指引；HELP_MISSING/HELP_SLOT 加 SKILL.md 引用。2. cli.py: cmd_commit_prepare 输出改写为列举 4 项 hook 校验 + SKILL.md 引用；cmd_change_validate pre 阶段增加 clarify 检查和 Spec 关联检查。3. change.py: 新增 has_associated_spec(repo_root, config, adr_id) 检查 ADR 是否有关联 Spec。4. 测试更新：匹配新错误消息格式，新增 ADR→Spec 关联检查测试。
- 验证与测试: 1. pytest 全量测试通过。2. hook 阻塞消息包含可执行指引和 SKILL.md 引用。3. validate --phase pre 在 clarify 未完成时阻塞并提示。4. validate --phase pre 在 ADR 无关联 Spec 时提示走 Spec 创作协议。5. commit prepare 输出正确描述新流程。
- 风险与回滚: git revert 回退所有变更。改动集中在 hooks.py/cli.py/change.py 三个文件加测试，回退范围明确。


## Motivation and Context

ADR-011 实施过程中暴露两个流程断点：(1) change validate --phase pre 不检查 clarify 完整性和 ADR→Spec 关联关系，AI 可以跳过 Spec 创作协议直接改代码；(2) 门禁阻塞消息只有功能性描述没有可执行指引，AI 读到后不知道正确下一步该做什么。门禁设计假设使用者是人类，但实际主要使用者是 AI Agent。


## Goals and Boundaries

增强所有门禁阻塞消息，加入可执行指引和 SKILL.md 引用。增加 change validate --phase pre 的 clarify 完整性检查和 ADR→Spec 关联检查。不改变流程本身（不增加 PreToolUse hook，不改 _active.md 结构），只改门禁消息的内容和检查范围。


## Design and Architecture

hooks.py 5 处错误消息增加下一步指引 + SKILL.md 引用。cli.py 中 commit prepare 输出改为列举 hook 校验项并引用 SKILL.md。cli.py 中 change validate --phase pre 增加 clarify 完整性检查和 ADR→Spec 关联检查。change.py 新增 has_associated_spec() 辅助函数。


## Implementation Path

1. hooks.py: check_subagent_session 错误消息加 Agent 工具指引和 spec-vc init 提示；_check_plan_stage 错误消息加 change validate --phase pre 命令指引；_check_spec_readiness_for_adr 错误消息加 spec new/formalize/check 分步指引；HELP_MISSING/HELP_SLOT 加 SKILL.md 引用。2. cli.py: cmd_commit_prepare 输出改写为列举 4 项 hook 校验 + SKILL.md 引用；cmd_change_validate pre 阶段增加 clarify 检查和 Spec 关联检查。3. change.py: 新增 has_associated_spec(repo_root, config, adr_id) 检查 ADR 是否有关联 Spec。4. 测试更新：匹配新错误消息格式，新增 ADR→Spec 关联检查测试。


## Verification and Testing

1. pytest 全量测试通过。2. hook 阻塞消息包含可执行指引和 SKILL.md 引用。3. validate --phase pre 在 clarify 未完成时阻塞并提示。4. validate --phase pre 在 ADR 无关联 Spec 时提示走 Spec 创作协议。5. commit prepare 输出正确描述新流程。


## Risks and Rollback

git revert 回退所有变更。改动集中在 hooks.py/cli.py/change.py 三个文件加测试，回退范围明确。


## Affected Areas

待补充

## Pre-Change Validation

Spec-012 formalized。代码改动清单：1) hooks.py 5处消息增强+SKILL.md引用 2) cli.py commit prepare输出改写+validate pre增强 3) spec.py Spec编号与ADR对齐 4) adr.py 编号连续性检查 5) 测试更新+新增。72测试通过（编码号对齐+ADR连续性检查+plan stage 3个新增测试）。


## Post-Change Validation

ADR-012 plan-001 剩余 3 项实施完成。代码改动: (1) commit.py check_subagent_session 错误消息追加 Agent 工具指引 + spec-vc init 提示 + SKILL.md 引用; (2) hooks.py HELP_MISSING/HELP_SLOT/_check_plan_stage/_check_spec_readiness_for_adr 4 处错误消息追加可执行指引 + SKILL.md 引用，_check_spec_readiness_for_adr 改为调 spec.relevant_spec_issues 与 cli pre 检查口径对齐; (3) spec.py 新增 has_associated_spec/relevant_spec_issues 两个辅助函数; (4) cli.py cmd_change_validate pre 阶段新增 clarify 完整性检查（stage ∈ {discover,clarify} 且 missing fields 时阻塞）和 ADR→Spec 关联提示，Spec 检查范围从全局收窄为 ADR-relevant; cmd_commit_prepare 输出列举 4 项 hook 校验项 + SKILL.md 引用; (5) SKILL.md 同步 validate --phase pre 描述。测试: 新增 6 个用例（HELP_MISSING/SLOT 含 SKILL.md、commit prepare 列 4 项、clarify 阻塞、Spec 隔离、无 Spec 提示、hook 阻塞 Spec 不就绪含 SKILL.md），原有 4 个测试加 SKILL.md 断言。pytest 78/78 全过（之前 72）。手工验证: spec-vc spec check 全部就绪、change next-question 显示 stage=implement-ready。pyright 仅遗留与本次改动无关的 cmd_change_start/cmd_skill_load 中 dict.get 返回 object 的类型推断警告。


## Closure Summary

完成 commit 协议简化（ADR-011 落地）+ 门禁消息可执行指引（ADR-012 plan-001 全部 8 个目标）：5 处错误消息追加分步指引和 SKILL.md 引用；change validate --phase pre 三项检查（clarify 完整性 / ADR-relevant Spec 就绪 / ADR→Spec 关联提示）；commit prepare 输出列举 4 项 hook 校验项；spec.has_associated_spec / spec.relevant_spec_issues 抽取领域辅助函数；adr.check_adr_continuity + adr_new 编号空洞警告；spec_new 编号与 ADR 对齐。pytest 78/78 通过。plan-002 留作设计草稿，未引入 _active.md 引用链。


## References

- **Commits**: 待从 git 自动采集
- **Plan**: doc/arch/plans/ADR-012-plan-001.md


## Risks and Rollback

待补充

## Checkpoints

- [ ] 澄清完成
- [ ] 前置验证完成
- [ ] 实施完成
- [ ] 后置验证完成
- [ ] ADR 回填完成
