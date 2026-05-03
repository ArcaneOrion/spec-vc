# spec-vc Active Change

- **ADR**: ADR-008
- **Plan**: doc/arch/plans/ADR-008-plan-001.md
- **Stage**: validate
- **Status**: active
- **Updated At**: 2026-05-03T12:33:59
- **Summary**: 将 spec-vc commit 拆分为 prepare/submit 两阶段，token 仅由用户真实 TTY 运行的 submit 写入，AI 无法触发 commit

该文件用于 spec-vc 子系统恢复当前活跃变更上下文。
