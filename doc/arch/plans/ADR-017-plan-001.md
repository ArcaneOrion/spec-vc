# ADR-017 执行方案 001

- **ADR**: ADR-017
- **ADR Title**: commit-msg 审计证据由间接代理升级为内容绑定
- **Stage**: close
- **Created At**: 2026-05-17T20:36:00
- **Summary**: 修复 ADR-013/016 暴露的审计信任漏洞 H1（tool_input 代理）+ H2（一次审计跨多 commit 复用）

## Clarification

- 动机与上下文: ADR-013 用 'description 非空' 作审计真实发生的代理证据，ADR-016 修复 stdin 传值后该假设的脆弱性显形：H1 (description 来自 tool_input 而非 tool_response，Agent 失败仍写日志) + H2 (commit-msg mtime 一次 prepare 后所有后续 commit 都靠 session log 末行复用通过新鲜度检查)。本次会话内已两次实证：22:54:32 行是 audit 内部 429 失败时 hook 仍写入 (H1)；ee83394 commit 未重 audit 仍通过 (H2)。两漏洞共同破坏 'audit 真实发生且绑定本次 commit' 的语义。需要把代理证据升级为内容绑定。
- 目标与边界: 做：commit prepare 写 anchor 文件 (ADR-XXX@<sha12>)；commit-msg hook 新增'末行 description 含 anchor'校验；PostToolUse hook 软处理 PostToolUseFailure 事件 (虽 Agent 业务失败常仍走 PostToolUse，此为 hygiene)。不做：不改 ADR-013 空 description 跳过逻辑；不改 ADR-none 豁免路径 (豁免规则已量化卡死)；不改 SPEC_VC_BYPASS 语义；不尝试从 tool_response 内容判断 Agent 业务成功失败 (Claude Code 契约不保证字段)。
- 设计与架构: 1) commit prepare 增 anchor 生成：anchor = 'ADR-XXX@<sha12>' 或 'ADR-none@<sha12>'，sha12 = sha256(git diff --cached --no-renames --no-color)[:12]。写入 .git/spec-vc-audit-anchor (单行) + stdout 提示 AI 复述。2) PostToolUse hook (run_post_tool_use) 解析 stdin JSON 后加守卫：hook_event_name == 'PostToolUseFailure' → return 0。3) commit-msg hook 在 check_session_log_freshness 后新增 check_anchor_binding：读 .git/spec-vc-audit-anchor，要求 session log 末行 description 包含 anchor 子串；anchor 文件不存在 + [ADR-NNN] → 阻塞 (要求走 prepare)；anchor 文件不存在 + [ADR-none] → 跳过 (保持豁免)。4) SPEC_VC_BYPASS 跳过 anchor 检查。5) settings.json 模板不变。
- 实现路径: 1. commit.py 新增 compute_audit_anchor(repo_root, adr_token) + write_audit_anchor。2. cli.py:cmd_commit_prepare 在写 commit-msg 后调 write_audit_anchor 并 stdout 提示 anchor。3. hooks.py:run_post_tool_use 加 hook_event_name 守卫。4. hooks.py:run_commit_msg 在新鲜度后新增 check_anchor_binding。5. 加测试覆盖 anchor 稳定性 / 写入 / PostToolUseFailure 跳过 / commit-msg 通过 / 阻塞末行无 anchor / 阻塞 [ADR-NNN] 无 anchor 文件 / [ADR-none] 跳过 / BYPASS 跳过 共 8 个用例。6. 新建 Spec-017 形式化接口契约 + 行为规则。7. 更新 SKILL.md 6c 段添加 anchor 复述要求。
- 验证与测试: 修改前已实证：(a) 22:54:32 行是 Agent 429 失败仍写入；(b) ee83394 commit 没重 audit 仍通过。修改后单测：anchor 计算 / 写入 / hook PostToolUseFailure / commit-msg pass / block-no-anchor-in-desc / block-no-anchor-file-with-NNN / ADR-none-skip / BYPASS-skip 8 用例。集成验证：本次 ADR-017 自己 commit 时即走完整新流程——commit prepare 应输出 anchor 并写文件；AI 必须在 audit description 中复述 anchor；commit 通过证明端到端工作。回归：pytest tests/python/ 全过。
- 风险与回滚: 风险 A：与 ADR-016 历史 commit 不兼容——纯前向变更，历史不受影响。风险 B：staged 改动 anchor 失效需重 audit——设计意图，文档明示。风险 C：anchor 文件不存在的现有仓库——首次 prepare 时自动生成。风险 D：SPEC_VC_BYPASS 保留逃生口。风险 E：git diff --cached 输出版本敏感——用 --no-renames --no-color 提升稳定性，若发现碰撞或漂移可改 git write-tree。回滚：单 commit revert 恢复 ADR-016 后状态。


## Clarification History

- 动机与上下文: ADR-013 用 'description 非空' 作审计真实发生的代理证据，ADR-016 修复 stdin 传值后该假设的脆弱性显形：H1 (description 来自 tool_input 而非 tool_response，Agent 失败仍写日志) + H2 (commit-msg mtime 一次 prepare 后所有后续 commit 都靠 session log 末行复用通过新鲜度检查)。本次会话内已两次实证：22:54:32 行是 audit 内部 429 失败时 hook 仍写入 (H1)；ee83394 commit 未重 audit 仍通过 (H2)。两漏洞共同破坏 'audit 真实发生且绑定本次 commit' 的语义。需要把代理证据升级为内容绑定。
- 目标与边界: 做：commit prepare 写 anchor 文件 (ADR-XXX@<sha12>)；commit-msg hook 新增'末行 description 含 anchor'校验；PostToolUse hook 软处理 PostToolUseFailure 事件 (虽 Agent 业务失败常仍走 PostToolUse，此为 hygiene)。不做：不改 ADR-013 空 description 跳过逻辑；不改 ADR-none 豁免路径 (豁免规则已量化卡死)；不改 SPEC_VC_BYPASS 语义；不尝试从 tool_response 内容判断 Agent 业务成功失败 (Claude Code 契约不保证字段)。
- 设计与架构: 1) commit prepare 增 anchor 生成：anchor = 'ADR-XXX@<sha12>' 或 'ADR-none@<sha12>'，sha12 = sha256(git diff --cached --no-renames --no-color)[:12]。写入 .git/spec-vc-audit-anchor (单行) + stdout 提示 AI 复述。2) PostToolUse hook (run_post_tool_use) 解析 stdin JSON 后加守卫：hook_event_name == 'PostToolUseFailure' → return 0。3) commit-msg hook 在 check_session_log_freshness 后新增 check_anchor_binding：读 .git/spec-vc-audit-anchor，要求 session log 末行 description 包含 anchor 子串；anchor 文件不存在 + [ADR-NNN] → 阻塞 (要求走 prepare)；anchor 文件不存在 + [ADR-none] → 跳过 (保持豁免)。4) SPEC_VC_BYPASS 跳过 anchor 检查。5) settings.json 模板不变。
- 实现路径: 1. commit.py 新增 compute_audit_anchor(repo_root, adr_token) + write_audit_anchor。2. cli.py:cmd_commit_prepare 在写 commit-msg 后调 write_audit_anchor 并 stdout 提示 anchor。3. hooks.py:run_post_tool_use 加 hook_event_name 守卫。4. hooks.py:run_commit_msg 在新鲜度后新增 check_anchor_binding。5. 加测试覆盖 anchor 稳定性 / 写入 / PostToolUseFailure 跳过 / commit-msg 通过 / 阻塞末行无 anchor / 阻塞 [ADR-NNN] 无 anchor 文件 / [ADR-none] 跳过 / BYPASS 跳过 共 8 个用例。6. 新建 Spec-017 形式化接口契约 + 行为规则。7. 更新 SKILL.md 6c 段添加 anchor 复述要求。
- 验证与测试: 修改前已实证：(a) 22:54:32 行是 Agent 429 失败仍写入；(b) ee83394 commit 没重 audit 仍通过。修改后单测：anchor 计算 / 写入 / hook PostToolUseFailure / commit-msg pass / block-no-anchor-in-desc / block-no-anchor-file-with-NNN / ADR-none-skip / BYPASS-skip 8 用例。集成验证：本次 ADR-017 自己 commit 时即走完整新流程——commit prepare 应输出 anchor 并写文件；AI 必须在 audit description 中复述 anchor；commit 通过证明端到端工作。回归：pytest tests/python/ 全过。
- 风险与回滚: 风险 A：与 ADR-016 历史 commit 不兼容——纯前向变更，历史不受影响。风险 B：staged 改动 anchor 失效需重 audit——设计意图，文档明示。风险 C：anchor 文件不存在的现有仓库——首次 prepare 时自动生成。风险 D：SPEC_VC_BYPASS 保留逃生口。风险 E：git diff --cached 输出版本敏感——用 --no-renames --no-color 提升稳定性，若发现碰撞或漂移可改 git write-tree。回滚：单 commit revert 恢复 ADR-016 后状态。


## Motivation and Context

ADR-013 用 'description 非空' 作审计真实发生的代理证据，ADR-016 修复 stdin 传值后该假设的脆弱性显形：H1 (description 来自 tool_input 而非 tool_response，Agent 失败仍写日志) + H2 (commit-msg mtime 一次 prepare 后所有后续 commit 都靠 session log 末行复用通过新鲜度检查)。本次会话内已两次实证：22:54:32 行是 audit 内部 429 失败时 hook 仍写入 (H1)；ee83394 commit 未重 audit 仍通过 (H2)。两漏洞共同破坏 'audit 真实发生且绑定本次 commit' 的语义。需要把代理证据升级为内容绑定。


## Goals and Boundaries

做：commit prepare 写 anchor 文件 (ADR-XXX@<sha12>)；commit-msg hook 新增'末行 description 含 anchor'校验；PostToolUse hook 软处理 PostToolUseFailure 事件 (虽 Agent 业务失败常仍走 PostToolUse，此为 hygiene)。不做：不改 ADR-013 空 description 跳过逻辑；不改 ADR-none 豁免路径 (豁免规则已量化卡死)；不改 SPEC_VC_BYPASS 语义；不尝试从 tool_response 内容判断 Agent 业务成功失败 (Claude Code 契约不保证字段)。


## Design and Architecture

1) commit prepare 增 anchor 生成：anchor = 'ADR-XXX@<sha12>' 或 'ADR-none@<sha12>'，sha12 = sha256(git diff --cached --no-renames --no-color)[:12]。写入 .git/spec-vc-audit-anchor (单行) + stdout 提示 AI 复述。2) PostToolUse hook (run_post_tool_use) 解析 stdin JSON 后加守卫：hook_event_name == 'PostToolUseFailure' → return 0。3) commit-msg hook 在 check_session_log_freshness 后新增 check_anchor_binding：读 .git/spec-vc-audit-anchor，要求 session log 末行 description 包含 anchor 子串；anchor 文件不存在 + [ADR-NNN] → 阻塞 (要求走 prepare)；anchor 文件不存在 + [ADR-none] → 跳过 (保持豁免)。4) SPEC_VC_BYPASS 跳过 anchor 检查。5) settings.json 模板不变。


## Implementation Path

1. commit.py 新增 compute_audit_anchor(repo_root, adr_token) + write_audit_anchor。2. cli.py:cmd_commit_prepare 在写 commit-msg 后调 write_audit_anchor 并 stdout 提示 anchor。3. hooks.py:run_post_tool_use 加 hook_event_name 守卫。4. hooks.py:run_commit_msg 在新鲜度后新增 check_anchor_binding。5. 加测试覆盖 anchor 稳定性 / 写入 / PostToolUseFailure 跳过 / commit-msg 通过 / 阻塞末行无 anchor / 阻塞 [ADR-NNN] 无 anchor 文件 / [ADR-none] 跳过 / BYPASS 跳过 共 8 个用例。6. 新建 Spec-017 形式化接口契约 + 行为规则。7. 更新 SKILL.md 6c 段添加 anchor 复述要求。


## Verification and Testing

修改前已实证：(a) 22:54:32 行是 Agent 429 失败仍写入；(b) ee83394 commit 没重 audit 仍通过。修改后单测：anchor 计算 / 写入 / hook PostToolUseFailure / commit-msg pass / block-no-anchor-in-desc / block-no-anchor-file-with-NNN / ADR-none-skip / BYPASS-skip 8 用例。集成验证：本次 ADR-017 自己 commit 时即走完整新流程——commit prepare 应输出 anchor 并写文件；AI 必须在 audit description 中复述 anchor；commit 通过证明端到端工作。回归：pytest tests/python/ 全过。


## Risks and Rollback

风险 A：与 ADR-016 历史 commit 不兼容——纯前向变更，历史不受影响。风险 B：staged 改动 anchor 失效需重 audit——设计意图，文档明示。风险 C：anchor 文件不存在的现有仓库——首次 prepare 时自动生成。风险 D：SPEC_VC_BYPASS 保留逃生口。风险 E：git diff --cached 输出版本敏感——用 --no-renames --no-color 提升稳定性，若发现碰撞或漂移可改 git write-tree。回滚：单 commit revert 恢复 ADR-016 后状态。


## Affected Areas

待补充

## Pre-Change Validation

Spec-017 dev-doc 全填 + 形式化 3 文件就绪；spec check 7/7 全过。baseline pytest 98/98 全过。H1/H2 漏洞复现证据：(a) 22:54:32 session log 行——Agent 内部 429 失败仍写入；(b) ee83394 commit 未重 audit 仍通过新鲜度检查。设计已选定层次 B (anchor 内容绑定)：anchor=ADR-XXX@<sha12>，sha12 = sha256(git diff --cached --no-renames --no-color)[:12]。commit-msg hook 新增 check_anchor_binding；PostToolUse hook 新增 PostToolUseFailure 守卫。覆盖盲区：现有 commit.py 无 anchor 相关函数；现有 hooks.py 无 hook_event_name 守卫；测试需新增 8 个用例。


## Post-Change Validation

代码 + 测试 + 文档全部实施完成。单测 109/109 全过（98 原 + 11 新 ADR-017 用例：anchor 稳定性/格式/写文件/PostToolUseFailure 守卫/正常 PostToolUse 写日志/anchor binding 通过/阻塞-无 anchor 子串/阻塞-anchor 文件缺/ADR-none 跳过/BYPASS 跳过）。旧测试受 ADR-017 影响 7 个，通过 _write_subagent_session helper 默认绑定 anchor + 2 个 freshness 测试单独加 anchor 文件修复。代码已 cp 到 skill 目录 (hooks.py + cli.py + commit.py) 让本会话后续 commit 走新代码。SKILL.md 6c 段已更新 anchor 复述要求与新校验链。集成验证将由本 ADR-017 自身 commit 完成——必须 commit prepare 生成 anchor → audit subagent description 复述 anchor → commit-msg hook 验证通过端到端工作。


## Closure Summary

把 audit 真实发生的代理证据（description 非空）升级为内容绑定（description 含 staged diff 指纹 anchor）。commit prepare 计算 ADR-XXX@<sha12> 并写 .git/spec-vc-audit-anchor；commit-msg hook 新增 check_anchor_binding 要求 session log 末行 description 含 anchor；PostToolUse hook 守卫 PostToolUseFailure 事件。[ADR-none] 与 SPEC_VC_BYPASS 路径保留原有语义。修复 ADR-013/016 暴露的 H1（间接证据脆弱）+ H2（一次 audit 跨多 commit 复用）两漏洞。哲学转向：spec-vc 不防作弊，把通过门禁的最小成本提到至少读一次 staged diff——'作弊比诚实便宜' 曲线翻过来。新增 11 测试覆盖 anchor 行为；7 旧测试通过 helper 升级 + 2 freshness 测试单独适配。109/109 全过。本 commit 自身即端到端集成验证：cc13a84 通过新 hook 校验链全 7 项含 anchor binding。


## References

- **Commits**: 待从 git 自动采集
- **Plan**: doc/arch/plans/ADR-017-plan-001.md


## Checkpoints

- [ ] 澄清完成
- [ ] 前置验证完成
- [ ] 实施完成
- [ ] 后置验证完成
- [ ] ADR 回填完成
