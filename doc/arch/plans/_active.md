# spec-vc Active Change

- **ADR**: ADR-006
- **Plan**: doc/arch/plans/ADR-006-plan-001.md
- **Stage**: implement-ready
- **Status**: active
- **Updated At**: 2026-04-27T16:18:23
- **Summary**: 在 commit-msg hook 中增加 token 校验：spec-vc commit 写入一次性 token，hook 验 token 无则阻塞，阻断绕过 spec-vc 直接 git commit 的路径

该文件用于 spec-vc 子系统恢复当前活跃变更上下文。
