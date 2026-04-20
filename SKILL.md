---
name: spec-vc
description: Decision Version Control via ADR + Commit anchoring. Use this skill when the user wants to initialize ADR infrastructure in a project, create a new architecture decision record, link commits to ADRs, check the health of the decision-commit anchoring, or upgrade existing hooks. Trigger phrases:"/spec-vc","创建 ADR","记录架构决策","decision version control","ADR 初始化","三层版本控制".
---

# spec-vc · ADR + Commit 锚定

本 skill 是三层版本控制框架的**第一层落地**——把 git 的语义层从 "what/how" 扩展到 "why"。

## SKILL_ROOT 约定

所有 commands 中出现的 `$SKILL_ROOT` 指向本 `SKILL.md` 所在的目录(即包含 `commands/`、`hooks/`、`scripts/`、`templates/` 的目录)。

Claude 执行本 skill 时,按以下顺序解析 `$SKILL_ROOT`:

1. 如果环境变量 `SPEC_VC_SKILL_ROOT` 已设置,使用其值
2. 否则,使用本 SKILL.md 文件所在目录的绝对路径(通常通过 `realpath "$(dirname <本文件>)"` 获取)
3. 调用脚本时用 `env SKILL_ROOT="$SKILL_ROOT" bash "$SKILL_ROOT/scripts/<name>.sh"` 显式传入

不要硬编码任何仓库、skill 或项目的绝对路径;所有路径都以 `$SKILL_ROOT` 为根。

## 使用边界

**适用**:
- 初始化项目的 ADR 基础设施(`doc/arch/` + git hooks)
- 创建新的架构决策记录
- 校验 commit 与 ADR 的双向锚定完整性
- 按状态/编号浏览历史决策
- 升级 hooks 到最新版本

**不适用**:
- 普通代码重构、debug、业务逻辑实现 → 用常规工具
- 规格版本控制(OpenAPI / Protobuf / Lean) → 等待本 skill 的 `spec-*` 子命令族(Layer 3,设计开发中)
- 非架构级 commit → 使用 `[ADR-none]` 显式豁免

## 命令索引

当前只实现了 Layer 2(决策版本控制)的 `adr-*` 子命令族。Layer 3 的 `spec-*` 子命令族将在 v0.3 引入。

| 命令 | 文件 | 用途 |
|------|------|------|
| `/spec-vc adr-init` | `commands/adr-init.md` | 初始化 `doc/arch/` + 安装 hooks |
| `/spec-vc adr-new "<title>"` | `commands/adr-new.md` | 创建新 ADR |
| `/spec-vc adr-link <ADR-NNN>` | `commands/adr-link.md` | 把暂存区 commit 关联到 ADR |
| `/spec-vc adr-status` | `commands/adr-status.md` | 双向锚定健康检查 |
| `/spec-vc adr-list` | `commands/adr-list.md` | 列出/过滤 ADR |
| `/spec-vc adr-upgrade` | `commands/adr-upgrade.md` | 升级当前项目中的 hooks 到本 skill 版本 |

## 核心不变量

1. **ADR 编号单调递增,不可复用**。即使 ADR 被废弃也保留记录,编号永不回收。
2. **每条 commit 必须带 `[ADR-NNN]` 或 `[ADR-none]`**。严格模式由 commit-msg hook 强制执行。
3. **双向引用是事实**,不是元数据。ADR 的 References 字段与 commit message 中的引用共同构成锚定。
4. **ADR 状态机**:`Proposed → Accepted → (Superseded by ADR-XXX | Deprecated)`,永远不删除。

## 设计哲学

- ADR 是 **commit message 的语义扩展**,不是平行文档系统。
- 双向锚定便于**漂移检测**:`/spec-vc adr-status` 会扫描出孤儿 ADR(无 commit 引用)、幽灵引用(commit 引用不存在的 ADR)、状态漂移(Superseded 指向不存在的目标)三类问题。
- 严格 hooks 是启动阶段的外部约束,帮助在 commit 前强制思考决策对应关系。

## 版本与升级

每个 hook 文件顶部有 `Version: x.y.z` 行。`/spec-vc adr-upgrade` 会:

1. 读取当前项目 `.git/hooks/` 下的 spec-vc 相关 hook 的 Version 字段
2. 对比 `$SKILL_ROOT/hooks/` 中的版本
3. 如有差异,展示 diff 并询问是否覆盖

## 关联资源

- 理论基础:仓库根目录 `README.md`(三层版本控制框架说明 + 实现进度)
- 模板:`templates/adr.md`(Nygard 五段式)、`templates/seed-adr-000.md`(init 时的种子 ADR)
- 未来层:本 skill 将扩展 `spec-*` 子命令族,对应 Layer 3(规格版本控制,normative)
