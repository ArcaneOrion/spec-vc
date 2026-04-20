---
description: 创建新的架构决策记录,自动取下一个编号并生成模板
---

# /spec-vc adr-new "<title>"

创建新的 ADR 文件。

## 参数

- `<title>`:必填。简短的名词短语,描述决策内容。例如 "LDAP 用于多租户集成"

## 执行步骤

1. 校验当前目录已初始化 spec-vc(存在 `doc/arch/`)
2. 调用 `scripts/new-adr.sh "<title>"`:
   - 扫描现有 ADR 编号,取 max + 1(零填充三位)
   - 从 `templates/adr.md` 渲染,替换 `{{NUMBER}}` / `{{TITLE}}` / `{{DATE}}` / `{{AUTHOR}}`
   - 写入 `doc/arch/adr-NNN.md`
3. 使用 `Edit` 工具打开新 ADR,引导用户填写 Context/Decision/Consequences
4. 更新 `doc/arch/README.md` 的 ADR 列表表格(在对应位置追加一行)
5. 输出下次 commit 的推荐 message 格式:
   ```
   <type>(<scope>): <subject> [ADR-NNN]
   ```

## 执行指令给 Claude

1. 解析 `$SKILL_ROOT`(见 `SKILL.md` 的"SKILL_ROOT 约定")
2. 校验 `doc/arch/` 存在;不存在则提示运行 `/spec-vc adr-init`
3. 运行 `env SKILL_ROOT="$SKILL_ROOT" bash "$SKILL_ROOT/scripts/new-adr.sh" "<title>"`
4. `Read` 生成的 ADR 文件
5. 与用户对话,引导填写:
   - **Context**:有哪些力量在起作用?技术约束、时间压力、依赖情况
   - **Decision**:最终选择是什么?用 "我们将..." 的主动语态
   - **Consequences**:积极/消极/中性后果分别是什么
   - **Alternatives Considered**:还考虑了哪些备选,为什么排除
6. 更新索引表格
7. 建议下一步:写代码 → commit 时引用 `[ADR-NNN]`

## 使用建议

- 不要等"决策完美"才创建 ADR。**提议阶段**就可以创建,Status 设为 Proposed
- ADR 是**决策当下的快照**,不是事后总结
- 一条 ADR 只记一个决策;多个决策拆成多条 ADR
- Context 部分保持价值中立,只陈述力量,不预判方向
