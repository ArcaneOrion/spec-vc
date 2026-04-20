---
description: 扫描 ADR 与 commit 的双向引用完整性,报告三类锚定漂移
---

# /spec-vc adr-status

运行 `scripts/check-refs.sh` 扫描三类锚定问题:

1. **幽灵引用** — commit message 引用了 `[ADR-NNN]`,但 `doc/arch/adr-NNN.md` 不存在
2. **孤儿 ADR** — ADR 文件存在,但没有任何 commit 引用它
3. **状态漂移** — ADR 标记为 `Superseded by ADR-XXX`,但 XXX 不存在

## 参数

- `--since=<git-ref>`(可选):只扫描某个 ref 之后的 commit,默认扫全库

## 执行指令给 Claude

1. 解析 `$SKILL_ROOT`(见 `SKILL.md` 的"SKILL_ROOT 约定")
2. 校验当前目录在 git 仓库内,且 `doc/arch/` 存在
3. 运行 `env SKILL_ROOT="$SKILL_ROOT" bash "$SKILL_ROOT/scripts/check-refs.sh" $ARGS`
3. 解析输出,把每类问题格式化为 markdown 表格呈现给用户
4. 对每个问题给出修复建议:
   - **幽灵引用**:
     - 如果是笔误 → 修正 commit(未推送可 amend,已推送需新建修正 commit 引用正确 ADR)
     - 如果 ADR 确实应存在 → `/spec-vc adr-new` 补充决策记录
   - **孤儿 ADR**:
     - 如果 ADR 已实现但历史 commit 未引用 → `/spec-vc adr-link <ADR-NNN>` 反向记录
     - 如果 ADR 从未实现 → 考虑改为 Deprecated 或删除(记录原因)
   - **状态漂移**:
     - 补齐目标 ADR,或修正 Superseded by 的指向
5. 如果无问题,简短报告"三层锚定完整"

## 输出样例

```
== spec-vc 锚定健康检查 ==

幽灵引用 (1)
  ADR-013 被以下 commit 引用,但文件不存在:
    a3f4c8d feat(cache): 引入 LRU 替换策略 [ADR-013]

孤儿 ADR (2)
  ADR-005: 统一错误码规范
  ADR-009: 事件总线采用 NATS

状态漂移 (0) — 无

建议:
  - ADR-013:疑似笔误,查 git log 确认实际决策编号
  - ADR-005/009:考虑运行 /spec-vc adr-link 反向记录实际 commit
```

## 何时运行

- 每周/每个迭代末定期巡检
- 重大重构前,确认决策链完整
- 在 CI 中作为非阻塞检查(exit code 1 时提醒但不阻塞 merge)
