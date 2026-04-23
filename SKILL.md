---
name: spec-vc
description: 加载 ADR 驱动的变更治理子系统。进入后先装载仓库治理上下文，再决定是恢复已有变更、进入澄清、还是只读查询。
disable-model-invocation: true
---

# spec-vc · 加载式变更治理子系统

你现在进入的是一个 **ADR 驱动的变更治理子系统**，不是单纯的命令集合。

## 启动步骤

1. 运行 `spec-vc skill load`，装载当前仓库治理上下文
2. 判断当前仓库是否已初始化 `spec-vc`
3. 检查是否存在活跃变更上下文 `doc/arch/plans/_active.md`
4. 如果存在活跃变更：优先恢复该变更，继续围绕对应 ADR 和 plan 工作
5. 如果不存在活跃变更，但用户明确要求做需要 ADR 的代码修改：进入澄清模式，并通过 `spec-vc change start --adr ... --summary ...` 创建执行方案
6. 如果用户只是查询 ADR / 状态 / 当前上下文：保持只读模式，不创建新计划
7. 只有当执行方案存在，且前置验证已明确后，才进入代码修改阶段

## 子系统原则

- ADR 记录“为什么这么做”
- Plan 记录“这一轮准备怎么改”
- Validation 记录“改前改后如何验证”
- 对需要 ADR 的改动，先澄清，再落计划，再改代码
- 非架构级的小改动仍可走 `[ADR-none]` 简化路径，不强制进入完整计划流程

## 活跃上下文

- 当前活跃变更索引：`doc/arch/plans/_active.md`
- 执行方案目录：`doc/arch/plans/`
- 计划命名：`ADR-<NNN>-plan-<NNN>.md`

## 推荐调用顺序

- 装载上下文：`spec-vc skill load`
- 启动/恢复变更：`spec-vc change start --adr ADR-007 --summary "..."`
- 查看当前活跃变更：`spec-vc change show-active`
- 关闭活跃变更：`spec-vc change close`
- ADR 查询与检查继续使用：`spec-vc adr list` / `spec-vc adr status`
