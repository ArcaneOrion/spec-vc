---
description: 把暂存区的下一次 commit 与指定 ADR 关联
---

# /decision-vc link <ADR-NNN>

手动把暂存区的下一次 commit 关联到指定 ADR。主要用途:

1. 在 `git commit` 之前预先指定 ADR 编号(避免编辑器打开后再查)
2. 在 ADR 中反向记录关联 commit 的 hash(代码 commit 后)

## 参数

- `<ADR-NNN>`:ADR 编号(如 `007` 或 `ADR-007`,两种写法均可)

## 执行步骤

### 模式 A:预关联(commit 之前)

1. 校验 `doc/arch/adr-NNN.md` 存在
2. 使用 `git config commit.template` 创建一次性模板,subject 行预填 `[ADR-NNN]` 槽位
3. 提示用户 `git commit` 即可

### 模式 B:反向记录(commit 之后)

1. 询问用户要记录哪一个 commit(默认 HEAD)
2. 取该 commit 的 short hash 与 subject
3. 使用 `Edit` 工具在 `doc/arch/adr-NNN.md` 的 `References.Commits` 段追加:
   ```
   - <short-hash> <subject>
   ```
4. 提示用户:若尚未推送,可以 amend 历史 ADR;若已推送,新建一条更新 commit(使用同一 ADR 编号)

## 执行指令给 Claude

1. 归一化 ADR 编号:接受 `7` / `007` / `ADR-7` / `ADR-007`,统一为 `007` 三位格式
2. 校验 `doc/arch/adr-${ID}.md` 存在;不存在则提示 `/decision-vc new` 或列出可选 ADR
3. 询问用户是模式 A 还是模式 B(用 `AskUserQuestion`)
4. 按对应模式执行

## 注意事项

- 模式 B 是"事后对齐",经常用来修正 `/decision-vc status` 报告的孤儿 ADR
- 一条 ADR 可以引用多个 commit(分阶段实现的决策)
- 一条 commit 只能引用一个 ADR(原则上),如需引用多个请拆分 commit
