---
description: 列出当前项目所有 ADR,支持按状态过滤
---

# /spec-vc adr-list

列出 `doc/arch/` 下所有 ADR,按编号排序。

## 参数

- `--status=<Proposed|Accepted|Deprecated|Superseded>`(可选):按状态过滤
- `--tags=<tag>`(可选):按 tag 过滤
- `--format=<table|compact|full>`(可选):输出格式,默认 table

## 执行指令给 Claude

1. 使用 `Glob` 列出 `doc/arch/adr-*.md`
2. 对每个文件,`Read` 首 20 行提取:
   - 编号(从文件名)
   - 标题(第一行 `# ADR-NNN: <title>`)
   - 状态(从 `**Status**:` 行)
   - 日期(从 `**Date**:` 行)
   - Tags(从 `**Tags**:` 行)
3. 应用过滤器(status / tags)
4. 按指定格式输出:
   - `table`(默认):markdown 表格
   - `compact`:一行一条,`ADR-NNN [Status] Title`
   - `full`:每条 ADR 附 Context 的前两行
5. 最后追加汇总:总数、各状态分布

## 输出样例(table 格式)

```
| 编号 | 标题 | 状态 | 日期 |
|------|------|------|------|
| ADR-000 | 采用 ADR 方法论 | Accepted | 2026-04-20 |
| ADR-001 | 引入三层版本控制 | Accepted | 2026-04-21 |
| ADR-002 | commit-msg hook 严格模式 | Proposed | 2026-04-22 |

总计:3 条 ADR(Accepted 2 / Proposed 1)
```

## 附带同步

运行后询问用户是否需要把结果写回 `doc/arch/README.md` 的索引表格(即更新索引本身)。
如果用户同意,使用 `Edit` 工具更新 `doc/arch/README.md` 的 `## 当前 ADR 列表` 段落。
