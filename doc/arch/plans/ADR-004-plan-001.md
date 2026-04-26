# ADR-004 执行方案 001

- **ADR**: ADR-004
- **ADR Title**: init命令增加uv环境安装步骤
- **Stage**: close
- **Created At**: 2026-04-26T11:00:51
- **Summary**: init命令增加uv环境安装步骤，确保spec-vc CLI在目标仓库可用

## Clarification

- 目标: spec-vc init 完成整个 skill 环境配置，每次加载 /spec-vc 时能准确加载环境，不会出现 command not found: spec-vc 错误
- 范围: spec-vc init 增加环境搭建步骤；SKILL.md 启动协议确保环境加载
- 非目标: 不负责 skill 目录同步机制；不涉及非 uv 的包管理方式；不修改 hooks/ADR/change 等子系统逻辑
- 实现策略: init 命令新增 uv sync 步骤确保 CLI 入口可用；SKILL.md 启动协议统一使用 uv run spec-vc 前缀
- 风险与回滚: uv sync 在无网络或 Python 环境缺失时可能失败；回滚：uv run 向上兼容，已有 venv 激活的用户不受影响，init 失败不影响已有的 git hooks 和配置文件
- 验收标准: init 执行后 uv run spec-vc --help 正常运行不出 command not found；uv run spec-vc skill load 调用成功；SKILL.md 中所有 CLI 调用均为 uv run spec-vc 前缀；已有测试通过且新增测试覆盖 init 环境安装步骤


## Clarification History

- Goal: [missing]
- Scope: [missing]
- Non-Goals: [missing]
- Strategy: [missing]
- Risks: [missing]
- Acceptance: init 执行后 uv run spec-vc --help 正常运行不出 command not found；uv run spec-vc skill load 调用成功；SKILL.md 中所有 CLI 调用均为 uv run spec-vc 前缀；已有测试通过且新增测试覆盖 init 环境安装步骤


## Goal

spec-vc init 完成整个 skill 环境配置，每次加载 /spec-vc 时能准确加载环境，不会出现 command not found: spec-vc 错误


## Scope

spec-vc init 增加环境搭建步骤；SKILL.md 启动协议确保环境加载


## Non-Goals

不负责 skill 目录同步机制；不涉及非 uv 的包管理方式；不修改 hooks/ADR/change 等子系统逻辑


## Implementation Strategy

init 命令新增 uv sync 步骤确保 CLI 入口可用；SKILL.md 启动协议统一使用 uv run spec-vc 前缀


## Affected Areas

待补充

## Acceptance Criteria

init 执行后 uv run spec-vc --help 正常运行不出 command not found；uv run spec-vc skill load 调用成功；SKILL.md 中所有 CLI 调用均为 uv run spec-vc 前缀；已有测试通过且新增测试覆盖 init 环境安装步骤


## Pre-Change Validation

现有 init 命令不包含环境安装步骤；SKILL.md 仍有裸 spec-vc 调用；需确认 uv run 在无 venv 激活时可用


## Post-Change Validation

spec-vc init 新增 uv sync 步骤确保 CLI 环境可用；SKILL.md clarify 阶段 next-question 统一 uv run 前缀；pyproject.toml 添加 build-system 使 uv sync 安装 entry point；测试全通过


## Closure Summary

init 新增 uv sync 环境安装步骤确保 CLI 可用；SKILL.md 统一 uv run 前缀；pyproject.toml 添加 build-system 让 uv sync 安装 entry point


## References

- **Commits**: 待从 git 自动采集
- **Plan**: doc/arch/plans/ADR-004-plan-001.md


## Risks and Rollback

uv sync 在无网络或 Python 环境缺失时可能失败；回滚：uv run 向上兼容，已有 venv 激活的用户不受影响，init 失败不影响已有的 git hooks 和配置文件


## Checkpoints

- [ ] 澄清完成
- [ ] 前置验证完成
- [ ] 实施完成
- [ ] 后置验证完成
- [ ] ADR 回填完成
