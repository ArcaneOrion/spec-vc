# 架构决策记录索引

本目录存放本项目所有架构决策记录（ADR）。

## 惯例

- 每条 ADR 编号单调递增,从 000 开始,不复用
- 文件名格式:`adr-NNN.md`(三位数字,零填充)
- 状态变更不删除旧记录,在文件顶部 Status 字段更新
- 每次 commit 在 message 中引用相关 ADR:`[ADR-NNN]` 或 `[ADR-none]`

## 创建新 ADR

```bash
/spec-vc adr-new "<简短的名词短语标题>"
```

## 当前 ADR 列表

<!--
由 /spec-vc adr-list 按需自动维护。手动修改会在下次运行 list 命令时被覆盖。
-->

| 编号 | 标题 | 状态 | 日期 |
|------|------|------|------|
| ADR-000 | 采用 ADR 方法论 | Accepted | 2026-04-20 |
| ADR-001 | 严格模式 + [ADR-none] 豁免策略 | Accepted | 2026-04-20 |
| ADR-002 | hooks 安装使用 cp 而非 symlink | Accepted | 2026-04-20 |
| ADR-003 | skill 扁平化 + 命令前缀统一为 /spec-vc adr-* | Accepted | 2026-04-20 |
| ADR-004 | init命令增加uv环境安装步骤 | Accepted | 2026-04-26 |
| ADR-005 | 引入 Spec 结构化规格层与 subagent 审计协议 | Accepted | 2026-04-26 |
| ADR-006 | 引入 commit token 门禁机制，强制通过 spec-vc commit 提交 | Accepted | 2026-04-27 |
| ADR-007 | 为 commit token 门禁引入 emergency bypass 机制 | Accepted | 2026-04-30 |
| ADR-008 | 引入 TTY-bound commit 机制，将 spec-vc commit 拆分为 prepare/submit 两阶段 | Proposed | 2026-05-03 |
| ADR-009 | 引入 PostToolUse hook subagent 调用追踪机制，确保 commit 前必须经过 subagent 审计 | Proposed | 2026-05-03 |
| ADR-010 | 简化提交流程：移除机械 manifest/audit-report/test-report/verify 层，保留 PostToolUse hook 证据链 | Proposed | 2026-05-03 |
| ADR-011 | 移除 commit submit 阶段，简化为 prepare + hook 校验循环 | Accepted | 2026-05-08 |
| ADR-012 | 门禁消息增强：失败时返回可执行指引而非仅阻塞 | Proposed | 2026-05-08 |
| ADR-013 | hook 校验链补完：adr_id 路由与 session log 时间戳新鲜度 | Proposed | 2026-05-08 |
| ADR-014 | 修复审计发现的6个致命缺陷 | Proposed | 2026-05-14 |
| ADR-015 | 修复 [ADR-none] 路径被 subagent session 检查误伤 | Proposed | 2026-05-14 |
| ADR-016 | PostToolUse hook 从 stdin 读 JSON 修复 description 取值 | Proposed | 2026-05-14 |
| ADR-017 | commit-msg 审计证据由间接代理升级为内容绑定 | Proposed | 2026-05-17 |

## 状态图例

- **Proposed** — 提议中,尚未达成一致
- **Accepted** — 已接受,代码可开始实现
- **Deprecated** — 不再使用但未被替代
- **Superseded by ADR-XXX** — 被新决策替代

## 相关资源

- ADR 模板:由 spec-vc skill 的 `templates/adr.md` 提供
- 框架说明:spec-vc skill 的 README.md
