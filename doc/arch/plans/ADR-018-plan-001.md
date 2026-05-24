# ADR-018 执行方案 001

- **ADR**: ADR-018
- **ADR Title**: 审查/提交解耦：spec-vc review 独立、审计证据脱离 PostToolUse hook
- **Stage**: close
- **Created At**: 2026-05-24T12:36:02
- **Summary**: 审查/提交解耦：spec-vc review 独立承担审计、commit-msg hook 校验源切换为 review.json、新增 [ADR-none] 量化判定、所有错误信息可操作

## Clarification

- 动机与上下文: spec-vc commit 当前把代码审查、实际使用验证、提交动作三件事耦合在一起，审查被异化为'通过 hook'；审计证据搭在 PostToolUse hook 间接通道（matcher → harness stdin JSON → AI 在 Agent description 复述 anchor），任一环节静默失败 → AI 不知道 → bypass 兜底，邻近项目实践显示 bypass 变 2/3 常态；[ADR-none] 触发主观，轻量改动用重流程无释放口；当前阻塞错误信息只说'被阻塞'，AI 无法自我修复反向强化 bypass 习惯。
- 目标与边界: 做：(1) 新增 spec-vc review 命令承担审查职责，含 subagent/simple 两种模式；(2) 改造 spec-vc commit 为薄包装提交入口；(3) 改造 commit-msg hook 校验链，审计证据源从 PostToolUse session log 切换到 .git/spec-vc-review.json；(4) 新增 lightweight.py + [ADR-none] 量化判定规则；(5) 所有阻塞错误改造为结构化输出（reason / current_state / fix_commands / docs_ref）；(6) review --verified flag + require_user_verified 配置项。不做：动 clarify/plan/Spec 创作协议或 change 状态机节点；动 ADR/Spec 数据模型；删 PostToolUse hook（降级为辅助日志保留兼容）；把用户实际验证做成默认硬门禁（保 honor system）。
- 设计与架构: 命令边界：spec-vc review [--mode subagent|simple] [--verified] [--note] [--message] 计算 anchor=ADR-XXX@<staged-diff-sha12> + 按模式校验证据 + 写 .git/spec-vc-review.json + 写 .git/spec-vc-commit-msg；spec-vc commit 做 Spec 就绪检查 + 应用 commit-msg 调 git commit + hook 失败时转译指引。审计证据载体 .git/spec-vc-review.json 字段：anchor / mode / verified / note / created_at / subagent_log_tail（subagent 模式）/ staged_sha12。simple 模式诚实成本：--note 文本必须含 anchor 子串，强制 AI 抄一次 sha12 = 至少看一眼 prepare 输出。[ADR-none] 量化规则：staged files ≤ 5 + 全部命中文档/配置白名单（*.md / *.txt / doc/** / .gitignore / .editorconfig / 配置 *.json）+ diff 净变更 ≤ 50 行；命中即自动建议，AI 可 override。用户实际验证：--verified flag 写入 review.json，默认不校验；require_user_verified=true 时升级硬门禁。commit-msg hook 校验链：(1) SPEC_VC_BYPASS → 跳到 ADR 引用；(2) ADR 引用格式；(3) [ADR-NNN] → plan stage ≥ implement-ready + Spec 完整性 + review.json 存在 + anchor 匹配当前 staged sha12 + mtime > commit-msg mtime + simple 模式 note 含 anchor；(4) [ADR-none] → 量化命中放行 / 未命中阻塞。错误信息结构（横切约束）：BlockingError(reason: 一行原因 / current_state: 事实摘要含文件存在性·mtime·anchor 实际值 / fix_commands: 可粘贴 shell 命令列表 / docs_ref: SKILL.md 锚点·ADR·Spec 引用)；所有 hook 阻塞与 CLI 错误统一走这个结构。
- 实现路径: 1. errors.py 新增 BlockingError 类 + 格式化函数；2. review.py（新）Review dataclass / review.json 读写 / anchor 计算从 commit.py 迁入 / cmd_review 含两种模式实现；3. lightweight.py（新）detect_lightweight_change(repo_root) -> (bool, reasons)；4. config.py 加 LightweightConfig（files_max / lines_max / type_whitelist）+ require_user_verified 字段；5. commit.py 拆出 anchor 计算到 review.py，cmd_commit 重写为薄包装（Spec 就绪 + git commit + hook 失败转译）；6. hooks.py 改 run_commit_msg_check 校验链读 review.json，删除旧 check_anchor_binding 函数，PostToolUse hook 保留但 commit-msg hook 不再读 session log；7. cli.py 注册 spec-vc review，commit prepare 保留 alias 打 stderr deprecation；8. SKILL.md + templates/SKILL.md 流程文档拆为 review + commit + 错误恢复；9. CLAUDE.md 提交流程小节同步；10. tests/python/test_cli.py 新增 19 测试 + 现有 anchor helper 升级到 review.json；11. 自举：feature 实现 + 测试过后 → 旧流程合入 → 之后所有 commit 走新流程。
- 验证与测试: 单测增量 19 项：review 命令 8（anchor 计算稳定性 / json 序列化 / subagent 模式证据 / simple 模式 note 含 anchor 校验 / --verified 写入 / 无 --note 阻塞 / mode 互斥 / 重复 review 覆盖）+ 新 hook 链 6（review.json 缺失阻塞 / anchor 不匹配阻塞 / mtime 不新鲜阻塞 / simple 模式 note 不含 anchor 阻塞 / [ADR-none] 量化命中放行 / [ADR-none] 未命中阻塞）+ 量化判定 5（文件数边界 / 类型白名单 / 行数边界 / 混合类型拒绝 / override 路径）。错误输出测试：每个 hook 阻塞分支断言输出含 reason / fix_commands / docs_ref 三段非空。回归：现有 109 测试不能挂，anchor 相关通过 helper 升级到 review.json。端到端自举：本 ADR-018 自身 commit 走新流程，spec-vc review + spec-vc commit + hook 校验链全过，无 bypass。长期 KPI：.git/spec-vc-bypass.log 条目数 = 0（除非真有 spec-vc bug）。
- 风险与回滚: 所有变更是新增 + 重命名 + 校验链分支调整，回滚路径清晰：(1) git revert ADR-018 整链 commit；(2) hooks.py 校验链改回读 session log（旧代码保留在 git 历史）；(3) .git/spec-vc-review.json 是新文件，旧代码忽略；(4) SPEC_VC_BYPASS 逃生口语义保持，spec-vc 损坏时仍可绕过；(5) commit prepare alias 提供 deprecation 缓冲，避免历史习惯立刻断裂。自举失败保险：feature 分支期间若发现严重问题，丢弃分支，旧流程（ADR-011 + ADR-017）保持工作。本变更不改 ADR / Spec / change 数据模型，所有数据文件向后兼容。


## Clarification History

- 动机与上下文: spec-vc commit 当前把代码审查、实际使用验证、提交动作三件事耦合在一起，审查被异化为'通过 hook'；审计证据搭在 PostToolUse hook 间接通道（matcher → harness stdin JSON → AI 在 Agent description 复述 anchor），任一环节静默失败 → AI 不知道 → bypass 兜底，邻近项目实践显示 bypass 变 2/3 常态；[ADR-none] 触发主观，轻量改动用重流程无释放口；当前阻塞错误信息只说'被阻塞'，AI 无法自我修复反向强化 bypass 习惯。
- 目标与边界: 做：(1) 新增 spec-vc review 命令承担审查职责，含 subagent/simple 两种模式；(2) 改造 spec-vc commit 为薄包装提交入口；(3) 改造 commit-msg hook 校验链，审计证据源从 PostToolUse session log 切换到 .git/spec-vc-review.json；(4) 新增 lightweight.py + [ADR-none] 量化判定规则；(5) 所有阻塞错误改造为结构化输出（reason / current_state / fix_commands / docs_ref）；(6) review --verified flag + require_user_verified 配置项。不做：动 clarify/plan/Spec 创作协议或 change 状态机节点；动 ADR/Spec 数据模型；删 PostToolUse hook（降级为辅助日志保留兼容）；把用户实际验证做成默认硬门禁（保 honor system）。
- 设计与架构: 命令边界：spec-vc review [--mode subagent|simple] [--verified] [--note] [--message] 计算 anchor=ADR-XXX@<staged-diff-sha12> + 按模式校验证据 + 写 .git/spec-vc-review.json + 写 .git/spec-vc-commit-msg；spec-vc commit 做 Spec 就绪检查 + 应用 commit-msg 调 git commit + hook 失败时转译指引。审计证据载体 .git/spec-vc-review.json 字段：anchor / mode / verified / note / created_at / subagent_log_tail（subagent 模式）/ staged_sha12。simple 模式诚实成本：--note 文本必须含 anchor 子串，强制 AI 抄一次 sha12 = 至少看一眼 prepare 输出。[ADR-none] 量化规则：staged files ≤ 5 + 全部命中文档/配置白名单（*.md / *.txt / doc/** / .gitignore / .editorconfig / 配置 *.json）+ diff 净变更 ≤ 50 行；命中即自动建议，AI 可 override。用户实际验证：--verified flag 写入 review.json，默认不校验；require_user_verified=true 时升级硬门禁。commit-msg hook 校验链：(1) SPEC_VC_BYPASS → 跳到 ADR 引用；(2) ADR 引用格式；(3) [ADR-NNN] → plan stage ≥ implement-ready + Spec 完整性 + review.json 存在 + anchor 匹配当前 staged sha12 + mtime > commit-msg mtime + simple 模式 note 含 anchor；(4) [ADR-none] → 量化命中放行 / 未命中阻塞。错误信息结构（横切约束）：BlockingError(reason: 一行原因 / current_state: 事实摘要含文件存在性·mtime·anchor 实际值 / fix_commands: 可粘贴 shell 命令列表 / docs_ref: SKILL.md 锚点·ADR·Spec 引用)；所有 hook 阻塞与 CLI 错误统一走这个结构。
- 实现路径: 1. errors.py 新增 BlockingError 类 + 格式化函数；2. review.py（新）Review dataclass / review.json 读写 / anchor 计算从 commit.py 迁入 / cmd_review 含两种模式实现；3. lightweight.py（新）detect_lightweight_change(repo_root) -> (bool, reasons)；4. config.py 加 LightweightConfig（files_max / lines_max / type_whitelist）+ require_user_verified 字段；5. commit.py 拆出 anchor 计算到 review.py，cmd_commit 重写为薄包装（Spec 就绪 + git commit + hook 失败转译）；6. hooks.py 改 run_commit_msg_check 校验链读 review.json，删除旧 check_anchor_binding 函数，PostToolUse hook 保留但 commit-msg hook 不再读 session log；7. cli.py 注册 spec-vc review，commit prepare 保留 alias 打 stderr deprecation；8. SKILL.md + templates/SKILL.md 流程文档拆为 review + commit + 错误恢复；9. CLAUDE.md 提交流程小节同步；10. tests/python/test_cli.py 新增 19 测试 + 现有 anchor helper 升级到 review.json；11. 自举：feature 实现 + 测试过后 → 旧流程合入 → 之后所有 commit 走新流程。
- 验证与测试: 单测增量 19 项：review 命令 8（anchor 计算稳定性 / json 序列化 / subagent 模式证据 / simple 模式 note 含 anchor 校验 / --verified 写入 / 无 --note 阻塞 / mode 互斥 / 重复 review 覆盖）+ 新 hook 链 6（review.json 缺失阻塞 / anchor 不匹配阻塞 / mtime 不新鲜阻塞 / simple 模式 note 不含 anchor 阻塞 / [ADR-none] 量化命中放行 / [ADR-none] 未命中阻塞）+ 量化判定 5（文件数边界 / 类型白名单 / 行数边界 / 混合类型拒绝 / override 路径）。错误输出测试：每个 hook 阻塞分支断言输出含 reason / fix_commands / docs_ref 三段非空。回归：现有 109 测试不能挂，anchor 相关通过 helper 升级到 review.json。端到端自举：本 ADR-018 自身 commit 走新流程，spec-vc review + spec-vc commit + hook 校验链全过，无 bypass。长期 KPI：.git/spec-vc-bypass.log 条目数 = 0（除非真有 spec-vc bug）。
- 风险与回滚: 所有变更是新增 + 重命名 + 校验链分支调整，回滚路径清晰：(1) git revert ADR-018 整链 commit；(2) hooks.py 校验链改回读 session log（旧代码保留在 git 历史）；(3) .git/spec-vc-review.json 是新文件，旧代码忽略；(4) SPEC_VC_BYPASS 逃生口语义保持，spec-vc 损坏时仍可绕过；(5) commit prepare alias 提供 deprecation 缓冲，避免历史习惯立刻断裂。自举失败保险：feature 分支期间若发现严重问题，丢弃分支，旧流程（ADR-011 + ADR-017）保持工作。本变更不改 ADR / Spec / change 数据模型，所有数据文件向后兼容。


## Motivation and Context

spec-vc commit 当前把代码审查、实际使用验证、提交动作三件事耦合在一起，审查被异化为'通过 hook'；审计证据搭在 PostToolUse hook 间接通道（matcher → harness stdin JSON → AI 在 Agent description 复述 anchor），任一环节静默失败 → AI 不知道 → bypass 兜底，邻近项目实践显示 bypass 变 2/3 常态；[ADR-none] 触发主观，轻量改动用重流程无释放口；当前阻塞错误信息只说'被阻塞'，AI 无法自我修复反向强化 bypass 习惯。


## Goals and Boundaries

做：(1) 新增 spec-vc review 命令承担审查职责，含 subagent/simple 两种模式；(2) 改造 spec-vc commit 为薄包装提交入口；(3) 改造 commit-msg hook 校验链，审计证据源从 PostToolUse session log 切换到 .git/spec-vc-review.json；(4) 新增 lightweight.py + [ADR-none] 量化判定规则；(5) 所有阻塞错误改造为结构化输出（reason / current_state / fix_commands / docs_ref）；(6) review --verified flag + require_user_verified 配置项。不做：动 clarify/plan/Spec 创作协议或 change 状态机节点；动 ADR/Spec 数据模型；删 PostToolUse hook（降级为辅助日志保留兼容）；把用户实际验证做成默认硬门禁（保 honor system）。


## Design and Architecture

命令边界：spec-vc review [--mode subagent|simple] [--verified] [--note] [--message] 计算 anchor=ADR-XXX@<staged-diff-sha12> + 按模式校验证据 + 写 .git/spec-vc-review.json + 写 .git/spec-vc-commit-msg；spec-vc commit 做 Spec 就绪检查 + 应用 commit-msg 调 git commit + hook 失败时转译指引。审计证据载体 .git/spec-vc-review.json 字段：anchor / mode / verified / note / created_at / subagent_log_tail（subagent 模式）/ staged_sha12。simple 模式诚实成本：--note 文本必须含 anchor 子串，强制 AI 抄一次 sha12 = 至少看一眼 prepare 输出。[ADR-none] 量化规则：staged files ≤ 5 + 全部命中文档/配置白名单（*.md / *.txt / doc/** / .gitignore / .editorconfig / 配置 *.json）+ diff 净变更 ≤ 50 行；命中即自动建议，AI 可 override。用户实际验证：--verified flag 写入 review.json，默认不校验；require_user_verified=true 时升级硬门禁。commit-msg hook 校验链：(1) SPEC_VC_BYPASS → 跳到 ADR 引用；(2) ADR 引用格式；(3) [ADR-NNN] → plan stage ≥ implement-ready + Spec 完整性 + review.json 存在 + anchor 匹配当前 staged sha12 + mtime > commit-msg mtime + simple 模式 note 含 anchor；(4) [ADR-none] → 量化命中放行 / 未命中阻塞。错误信息结构（横切约束）：BlockingError(reason: 一行原因 / current_state: 事实摘要含文件存在性·mtime·anchor 实际值 / fix_commands: 可粘贴 shell 命令列表 / docs_ref: SKILL.md 锚点·ADR·Spec 引用)；所有 hook 阻塞与 CLI 错误统一走这个结构。


## Implementation Path

1. errors.py 新增 BlockingError 类 + 格式化函数；2. review.py（新）Review dataclass / review.json 读写 / anchor 计算从 commit.py 迁入 / cmd_review 含两种模式实现；3. lightweight.py（新）detect_lightweight_change(repo_root) -> (bool, reasons)；4. config.py 加 LightweightConfig（files_max / lines_max / type_whitelist）+ require_user_verified 字段；5. commit.py 拆出 anchor 计算到 review.py，cmd_commit 重写为薄包装（Spec 就绪 + git commit + hook 失败转译）；6. hooks.py 改 run_commit_msg_check 校验链读 review.json，删除旧 check_anchor_binding 函数，PostToolUse hook 保留但 commit-msg hook 不再读 session log；7. cli.py 注册 spec-vc review，commit prepare 保留 alias 打 stderr deprecation；8. SKILL.md + templates/SKILL.md 流程文档拆为 review + commit + 错误恢复；9. CLAUDE.md 提交流程小节同步；10. tests/python/test_cli.py 新增 19 测试 + 现有 anchor helper 升级到 review.json；11. 自举：feature 实现 + 测试过后 → 旧流程合入 → 之后所有 commit 走新流程。


## Verification and Testing

单测增量 19 项：review 命令 8（anchor 计算稳定性 / json 序列化 / subagent 模式证据 / simple 模式 note 含 anchor 校验 / --verified 写入 / 无 --note 阻塞 / mode 互斥 / 重复 review 覆盖）+ 新 hook 链 6（review.json 缺失阻塞 / anchor 不匹配阻塞 / mtime 不新鲜阻塞 / simple 模式 note 不含 anchor 阻塞 / [ADR-none] 量化命中放行 / [ADR-none] 未命中阻塞）+ 量化判定 5（文件数边界 / 类型白名单 / 行数边界 / 混合类型拒绝 / override 路径）。错误输出测试：每个 hook 阻塞分支断言输出含 reason / fix_commands / docs_ref 三段非空。回归：现有 109 测试不能挂，anchor 相关通过 helper 升级到 review.json。端到端自举：本 ADR-018 自身 commit 走新流程，spec-vc review + spec-vc commit + hook 校验链全过，无 bypass。长期 KPI：.git/spec-vc-bypass.log 条目数 = 0（除非真有 spec-vc bug）。


## Risks and Rollback

所有变更是新增 + 重命名 + 校验链分支调整，回滚路径清晰：(1) git revert ADR-018 整链 commit；(2) hooks.py 校验链改回读 session log（旧代码保留在 git 历史）；(3) .git/spec-vc-review.json 是新文件，旧代码忽略；(4) SPEC_VC_BYPASS 逃生口语义保持，spec-vc 损坏时仍可绕过；(5) commit prepare alias 提供 deprecation 缓冲，避免历史习惯立刻断裂。自举失败保险：feature 分支期间若发现严重问题，丢弃分支，旧流程（ADR-011 + ADR-017）保持工作。本变更不改 ADR / Spec / change 数据模型，所有数据文件向后兼容。


## Affected Areas

待补充

## Pre-Change Validation

Spec 创作协议完成：Spec-018 dev-doc 6 必查区块全填（概述/接口契约/数据形状/行为规则/测试策略/日志实现）+ 3 形式化文件已生成（contract.openapi.yaml / schema.json / behavior.feature）；spec check 8/8 全过。baseline pytest 109/109 全过（基线绿）。漏洞证据：(a) 用户提供的邻近项目 spec-vc 实践报告——2/3 commit 走 SPEC_VC_BYPASS，门禁形同虚设；(b) 本仓库验证 23 个 anchor + post_tool_use 测试虽过，但承载机制仍依赖 PostToolUse hook → harness stdin JSON → AI 复述 anchor 的间接通道，邻近项目报告的归因（'Agent 内部 Bash description'）虽可能不准确，但'链路脆弱、AI 无法自我修复阻塞、bypass 兜底'的现象是真实设计警告。设计已固化层次：(1) 命令边界=spec-vc review 独立审查 / spec-vc commit 薄包装提交 / commit-msg hook 校验链；(2) 审计证据载体=.git/spec-vc-review.json（schema 已定义 8 字段，含 anchor / mode / verified / note / staged_sha12 / created_at 等）；(3) commit-msg hook 校验链顺序固化（BYPASS → ADR 引用 → plan stage → Spec 完整性 → review.json 校验 → [ADR-none] 量化判定）；(4) BlockingError 横切结构=reason / current_state / fix_commands / docs_ref；(5) [ADR-none] 量化阈值=files_max=5 / lines_max=50 / type_whitelist 6 模式。覆盖盲区：现有 src/spec_vc/commit.py 无 cmd_review 函数；src/spec_vc/hooks.py 无 lightweight 判定与 review.json 校验链；src/spec_vc/errors.py 无 BlockingError 类；src/spec_vc/config.py 无 LightweightConfig + require_user_verified；src/spec_vc/cli.py 无 review 子命令；tests/python/test_cli.py 无 19 新增测试。


## Post-Change Validation

代码 + 测试 + 文档全部实施完成。新增模块：errors.py 含 BlockingError 类（reason / current_state / fix_commands / docs_ref 四段结构 + format() 输出）；review.py 含 ReviewRecord dataclass + read_review/write_review + write_review_and_msg（自动抬升 mtime 保证 review.json mtime > commit-msg mtime）；lightweight.py 含 detect_lightweight_change 量化判定函数 + LightweightDetectionResult。改造模块：hooks.py 新增 _check_review_record + _check_lightweight 函数取代旧 _check_anchor_binding，commit-msg hook 校验链 SPEC_VC_BYPASS → ADR 引用 → [ADR-NNN] plan stage + Spec + review.json (anchor 匹配 + mtime 新鲜 + simple 注解 + verified 升级) → [ADR-none] 量化判定；commit.py 保留 anchor 计算函数供 review.py 复用；cli.py 新增 cmd_review + 重构 cmd_commit 为薄包装 + cmd_commit_prepare 作为 deprecation alias。config.py 新增 LightweightConfig + require_user_verified 字段。CLI 注册 spec-vc review 子命令。单测 122/122 全过（原 109 + 13 净增）：review 命令 7 项（test_commit.py：review 阻塞/写文件/no manifest/输出提示/with spec/alias deprecation）+ 新 hook 链 6 项（freshness/anchor binding 重构为 review.json mtime + anchor 匹配）+ 量化判定 5 项（passes_docs/blocks_files_exceed/blocks_lines_exceed/blocks_unmatched_type/passes_doc_glob_pattern）+ simple 模式 3 项（requires_note/note_must_contain_anchor/with_anchor_passes）+ BlockingError 结构 1 项 + require_user_verified 1 项 + post_tool_use_still_writes_session_log 1 项。BlockingError 输出实证（test_blocking_error_output_contains_four_sections）：stderr 含 '[spec-vc] BLOCKED:' / 'Current state:' / 'How to fix:' / 'Docs:' / '$ ' 前缀的可执行命令。错误输出测试每个 hook 阻塞分支断言 reason + fix_commands + docs_ref 三段非空通过。文档同步：SKILL.md 6 段重写（拆为 review + commit-msg hook 校验链 + 薄包装 commit + PostToolUse 辅助日志 + 失败恢复 + SPEC_VC_BYPASS），CLAUDE.md 提交流程小节同步（ADR-011 → ADR-018 简化版），README.md 索引由 spec-vc 自动更新含 ADR-018。代码已 cp 到 ~/.claude/skills/spec-vc/src/spec_vc/（errors.py + config.py + review.py + lightweight.py + hooks.py + cli.py）让本会话后续 commit 走新代码。集成验证将由本 ADR-018 自身 commit 完成——必须 spec-vc review 生成 review.json → spec-vc commit 应用 commit-msg → commit-msg hook 验证通过端到端工作 + .git/spec-vc-bypass.log 无新增条目。


## Closure Summary

审查/提交解耦：spec-vc review 独立承担审计、commit-msg hook 校验源从 PostToolUse session log 切换为 .git/spec-vc-review.json、新增 [ADR-none] 量化判定、所有阻塞错误统一为 BlockingError 结构化输出。新模块: errors.py (BlockingError 类) + review.py (ReviewRecord + write_review_and_msg) + lightweight.py (detect_lightweight_change)。改造: hooks.py (新校验链 _check_review_record + _check_lightweight) + cli.py (cmd_review + cmd_commit 薄包装 + cmd_commit_prepare deprecation alias) + config.py (LightweightConfig + require_user_verified)。simple 模式要求 --note 含 anchor 子串，把通过门禁的最小成本抬到至少抄一次 sha12。新增 13 净测试（review 命令 + 新 hook 链 + 量化判定 + simple 模式 + BlockingError 结构 + require_user_verified + PostToolUse 辅助日志）。pytest 122/122 全过。哲学转向: spec-vc commit 不再承担审查门禁，AI 可以'先审查、再让用户验证、再提交'；审计证据搭在直接文件 review.json 上，commit-msg hook 直接读取，彻底脱离 PostToolUse hook → harness stdin JSON → AI 复述 anchor 的间接链路；所有阻塞输出走 BlockingError 让 AI 能按 fix_commands 自我修复，避免循环 bypass。supersedes ADR-011 (prepare+hook 单路径) 与 ADR-017 (session log + anchor 间接证据)。本 commit 自身即端到端集成验证：202aad0 通过新 hook 校验链 + .git/spec-vc-bypass.log 无新增条目。


## References

- **Commits**: 待从 git 自动采集
- **Plan**: doc/arch/plans/ADR-018-plan-001.md


## Checkpoints

- [ ] 澄清完成
- [ ] 前置验证完成
- [ ] 实施完成
- [ ] 后置验证完成
- [ ] ADR 回填完成
