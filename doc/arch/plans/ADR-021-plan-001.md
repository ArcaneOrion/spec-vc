# ADR-021 执行方案 001

- **ADR**: ADR-021
- **ADR Title**: 修复 hook/venv 入口确定性，兼容 Codex
- **Stage**: close
- **Created At**: 2026-05-24T22:06:46
- **Summary**: 修复 hook/venv 入口确定性，避免项目 venv 或 PATH 中旧 spec-vc 抢占；兼容 Claude/Codex/其他 CLI agent 的 git hook 使用

## Clarification

- 动机与上下文: Quant 项目实测 spec-vc commit 仍被项目 .venv 或 PATH 中旧入口抢占，导致 commit-msg hook 运行时找不到 spec_vc 模块；最近两个 [ADR-none] 修复只部分解决了 hook 路径问题，没有保证入口确定性。
- 目标与边界: 修复 commit-msg/prepare-commit-msg hook 入口确定性，避免项目 venv 抢占；兼容 Claude/Codex/其他 CLI agent 通过普通 git commit 触发 hook；不改变 ADR-018/019/020 的 review.json、Spec 完整性、anchor、mtime 校验语义。
- 设计与架构: hook 必须优先调用 init 注入的 deterministic skill venv 入口；路径使用 `$HOME/.claude/skills/spec-vc/.venv/bin/spec-vc` 而不是 `~`；PATH fallback 仅作为最后兜底或可选兼容；spec-vc init 应幂等地写入/修正 hook 配置，确保旧 hook 可治愈。Codex 兼容的关键是 hook 与 CLI 入口不依赖 Claude 专属环境，只依赖 git + shell + spec-vc 可执行文件。
- 实现路径: 修改 hooks/commit-msg 与 hooks/prepare-commit-msg 的执行顺序：先尝试 SPEC_VC_BIN（skill venv 绝对路径），再考虑 PATH 中的 spec-vc；将 cli.py:_install_hook 写入的路径从 `~` 改为字面 `$HOME`，确保 shell 能正确展开；必要时补充测试，模拟 PATH 中存在坏的 spec-vc 入口时 hook 仍然命中 skill venv；验证 spec-vc init 能修复旧 hook。
- 验证与测试: 先用当前仓库复现坏场景：PATH 中存在项目 venv / 错误 spec-vc 时 git commit 仍应失败；修复后运行 pytest / 对应 hook 测试；再做 shell 级验证：PATH 里放坏 spec-vc，git commit 仍调用 skill venv 入口，commit-msg hook 通过。
- 风险与回滚: 回滚时恢复 hooks/commit-msg、hooks/prepare-commit-msg 和 cli.py:_install_hook 的改动即可；若存在旧 hook 配置，可重新运行 spec-vc init 覆盖。


## Clarification History

- 动机与上下文: Quant 项目实测 spec-vc commit 仍被项目 .venv 或 PATH 中旧入口抢占，导致 commit-msg hook 运行时找不到 spec_vc 模块；最近两个 [ADR-none] 修复只部分解决了 hook 路径问题，没有保证入口确定性。
- 目标与边界: 修复 commit-msg/prepare-commit-msg hook 入口确定性，避免项目 venv 抢占；兼容 Claude/Codex/其他 CLI agent 通过普通 git commit 触发 hook；不改变 ADR-018/019/020 的 review.json、Spec 完整性、anchor、mtime 校验语义。
- 设计与架构: hook 必须优先调用 init 注入的 deterministic skill venv 入口；路径使用 `$HOME/.claude/skills/spec-vc/.venv/bin/spec-vc` 而不是 `~`；PATH fallback 仅作为最后兜底或可选兼容；spec-vc init 应幂等地写入/修正 hook 配置，确保旧 hook 可治愈。Codex 兼容的关键是 hook 与 CLI 入口不依赖 Claude 专属环境，只依赖 git + shell + spec-vc 可执行文件。
- 实现路径: 修改 hooks/commit-msg 与 hooks/prepare-commit-msg 的执行顺序：先尝试 SPEC_VC_BIN（skill venv 绝对路径），再考虑 PATH 中的 spec-vc；将 cli.py:_install_hook 写入的路径从 `~` 改为字面 `$HOME`，确保 shell 能正确展开；必要时补充测试，模拟 PATH 中存在坏的 spec-vc 入口时 hook 仍然命中 skill venv；验证 spec-vc init 能修复旧 hook。
- 验证与测试: 先用当前仓库复现坏场景：PATH 中存在项目 venv / 错误 spec-vc 时 git commit 仍应失败；修复后运行 pytest / 对应 hook 测试；再做 shell 级验证：PATH 里放坏 spec-vc，git commit 仍调用 skill venv 入口，commit-msg hook 通过。
- 风险与回滚: 回滚时恢复 hooks/commit-msg、hooks/prepare-commit-msg 和 cli.py:_install_hook 的改动即可；若存在旧 hook 配置，可重新运行 spec-vc init 覆盖。


## Motivation and Context

Quant 项目实测 spec-vc commit 仍被项目 .venv 或 PATH 中旧入口抢占，导致 commit-msg hook 运行时找不到 spec_vc 模块；最近两个 [ADR-none] 修复只部分解决了 hook 路径问题，没有保证入口确定性。


## Goals and Boundaries

修复 commit-msg/prepare-commit-msg hook 入口确定性，避免项目 venv 抢占；兼容 Claude/Codex/其他 CLI agent 通过普通 git commit 触发 hook；不改变 ADR-018/019/020 的 review.json、Spec 完整性、anchor、mtime 校验语义。


## Design and Architecture

hook 必须优先调用 init 注入的 deterministic skill venv 入口；路径使用 `$HOME/.claude/skills/spec-vc/.venv/bin/spec-vc` 而不是 `~`；PATH fallback 仅作为最后兜底或可选兼容；spec-vc init 应幂等地写入/修正 hook 配置，确保旧 hook 可治愈。Codex 兼容的关键是 hook 与 CLI 入口不依赖 Claude 专属环境，只依赖 git + shell + spec-vc 可执行文件。


## Implementation Path

修改 hooks/commit-msg 与 hooks/prepare-commit-msg 的执行顺序：先尝试 SPEC_VC_BIN（skill venv 绝对路径），再考虑 PATH 中的 spec-vc；将 cli.py:_install_hook 写入的路径从 `~` 改为字面 `$HOME`，确保 shell 能正确展开；必要时补充测试，模拟 PATH 中存在坏的 spec-vc 入口时 hook 仍然命中 skill venv；验证 spec-vc init 能修复旧 hook。


## Verification and Testing

先用当前仓库复现坏场景：PATH 中存在项目 venv / 错误 spec-vc 时 git commit 仍应失败；修复后运行 pytest / 对应 hook 测试；再做 shell 级验证：PATH 里放坏 spec-vc，git commit 仍调用 skill venv 入口，commit-msg hook 通过。


## Risks and Rollback

回滚时恢复 hooks/commit-msg、hooks/prepare-commit-msg 和 cli.py:_install_hook 的改动即可；若存在旧 hook 配置，可重新运行 spec-vc init 覆盖。


## Affected Areas

待补充

## Pre-Change Validation

ADR-021 前置验证完成：已复现两个根因：(1) bash 变量中的 ~ 不展开，SPEC_VC_BIN="~/.claude/..." 不可执行；(2) 旧 hook 逻辑 PATH 优先，会命中临时目录中的坏 spec-vc。Spec-021 已创建并 formalize all，spec check 显示全部 11 个 Spec 就绪。


## Post-Change Validation

pytest tests/python/ 126 项全部通过，含 test_cli.py 新增的 hook 入口注入测试。f313c79 完成核心修复（hooks/commit-msg、hooks/prepare-commit-msg 优先 SPEC_VC_BIN 且使用字面 $HOME 而非 ~；cli.py:_install_hook 同步注入字面 $HOME 路径），68e091c 同步 .claude/settings.json 与 active context。ADR-021 的 4 个 commit 本身就是 shell 级实测：commit-msg hook 在 PATH 含项目 venv 旧入口情况下仍命中 skill venv 入口并完成 review.json/anchor/mtime/Spec 完整性校验。


## Closure Summary

修复 git hook 入口确定性：hook 模板改为 SPEC_VC_BIN（字面 $HOME 路径）优先、PATH 兜底；cli.py:_install_hook 统一注入字面 $HOME 避免 .claude/settings.json 跨开发者污染。解决项目 venv 抢占导致的 ModuleNotFoundError，使 Codex 等非 Claude CLI agent 走普通 git commit 也能稳定触发 spec-vc hook。


## References

- **Commits**: 待从 git 自动采集
- **Plan**: doc/arch/plans/ADR-021-plan-001.md


## Checkpoints

- [ ] 澄清完成
- [ ] 前置验证完成
- [ ] 实施完成
- [ ] 后置验证完成
- [ ] ADR 回填完成
