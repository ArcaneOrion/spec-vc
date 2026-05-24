# spec-vc Active Change

- **ADR**: ADR-021
- **Plan**: doc/arch/plans/ADR-021-plan-001.md
- **Stage**: implement-ready
- **Status**: active
- **Updated At**: 2026-05-24T22:19:16
- **Summary**: 修复 hook/venv 入口确定性，避免项目 venv 或 PATH 中旧 spec-vc 抢占；兼容 Claude/Codex/其他 CLI agent 的 git hook 使用

该文件用于 spec-vc 子系统恢复当前活跃变更上下文。
