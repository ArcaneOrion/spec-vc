# Spec-021: hook/venv 入口确定性与跨 Agent 兼容

- **ADR**: ADR-021
- **Status**: Draft
- **Author**: arcaneorion
- **Date**: 2026-05-24
- **Version**: 0.1.0

---

## 概述

### 1.1 问题陈述

CLI agent（Claude Code、Codex 或其他工具）需要通过普通 `git commit` 触发稳定的 spec-vc hook，因为当前 hook 会优先执行 PATH 中的 `spec-vc`，在项目 venv 含错误入口时会抢占 skill venv 并触发 `ModuleNotFoundError: spec_vc`。

### 1.2 解决方案概述

`commit-msg` 与 `prepare-commit-msg` hook 的执行入口改为 deterministic 顺序：优先使用 init 注入的 `SPEC_VC_BIN`，该路径使用 `$HOME/.claude/skills/spec-vc/.venv/bin/spec-vc`，最后才 fallback 到 PATH 中的 `spec-vc`。`spec-vc init` 继续覆盖/修复目标仓库 hook，使旧 hook 可被治愈。

### 1.3 范围边界

**包含**:
- `hooks/commit-msg` 入口优先级调整
- `hooks/prepare-commit-msg` 入口优先级调整
- `src/spec_vc/cli.py:_install_hook` 注入 `$HOME` 路径而非 `~`
- 测试覆盖 PATH 中存在坏 `spec-vc` 时仍优先调用 skill venv 入口
- 兼容 Claude/Codex/其他 CLI agent 的普通 git hook 调用

**不包含**:
- 修改 ADR-018/019/020 的 review.json、Spec 完整性、anchor、mtime 校验语义
- 修改 PostToolUse hook 记录策略
- 修改 `spec-vc review` 审查助手报告内容
- 引入 Codex 专属协议或依赖

---

## 接口契约

```yaml
openapi: "3.0.3"
info:
  title: spec-vc hook/venv 入口确定性契约（ADR-021）
  version: "0.1.0"
  description: |
    本 Spec 使用 /internal/* 路径表达 CLI hook 行为契约，不代表 HTTP 服务。

paths:
  /internal/hook/commit-msg-entrypoint:
    post:
      summary: commit-msg hook 入口选择顺序
      description: |
        当 git 执行 .git/hooks/commit-msg 时，hook 必须按以下顺序选择入口：
        1. 读取 init 注入的 SPEC_VC_BIN（默认 $HOME/.claude/skills/spec-vc/.venv/bin/spec-vc）
        2. 如果 SPEC_VC_BIN 可执行，则 exec "$SPEC_VC_BIN" hook commit-msg "$1"
        3. 仅当 SPEC_VC_BIN 不存在或不可执行时，才 fallback 到 PATH 中的 spec-vc
        4. 如果两者都不可用，stderr 输出明确错误并 exit 1

        PATH 中的 spec-vc 不得抢占可执行的 SPEC_VC_BIN。
      responses:
        "0":
          description: hook 入口执行成功并完成 commit-msg 校验
        "1":
          description: SPEC_VC_BIN 与 PATH fallback 均不可用，或下游 hook 校验阻塞

  /internal/hook/prepare-commit-msg-entrypoint:
    post:
      summary: prepare-commit-msg hook 入口选择顺序
      description: |
        当 git 执行 .git/hooks/prepare-commit-msg 时，hook 必须按以下顺序选择入口：
        1. 读取 init 注入的 SPEC_VC_BIN（默认 $HOME/.claude/skills/spec-vc/.venv/bin/spec-vc）
        2. 如果 SPEC_VC_BIN 可执行，则 exec "$SPEC_VC_BIN" hook prepare-commit-msg "$1" "${2:-}" "${3:-}"
        3. 仅当 SPEC_VC_BIN 不存在或不可执行时，才 fallback 到 PATH 中的 spec-vc
        4. 如果两者都不可用，stderr 输出明确错误并 exit 1

        PATH 中的 spec-vc 不得抢占可执行的 SPEC_VC_BIN。
      responses:
        "0":
          description: hook 入口执行成功并完成 prepare-commit-msg 处理
        "1":
          description: SPEC_VC_BIN 与 PATH fallback 均不可用，或下游 hook 处理失败

  /internal/init/install-hook:
    post:
      summary: spec-vc init 写入 deterministic hook
      description: |
        spec-vc init 写入 hook 模板时，{{SPEC_VC_BIN}} 必须替换为 $HOME/.claude/skills/spec-vc/.venv/bin/spec-vc。
        禁止写入双引号内的 ~ 路径，因为 bash 变量中的 ~ 不会展开。
        重跑 spec-vc init 必须覆盖旧 hook，使 PATH 优先的历史 hook 被治愈。
      responses:
        "0":
          description: hook 已安装或修复
        "1":
          description: init 失败
```

---

## 数据形状

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "HookEntrypointConfig": {
      "type": "object",
      "required": ["spec_vc_bin", "fallback_policy"],
      "properties": {
        "spec_vc_bin": {
          "type": "string",
          "const": "$HOME/.claude/skills/spec-vc/.venv/bin/spec-vc",
          "description": "init 注入到 hook 模板中的 deterministic skill venv 入口"
        },
        "fallback_policy": {
          "type": "string",
          "enum": ["spec_vc_bin_first_path_last"],
          "description": "先 SPEC_VC_BIN，后 PATH fallback"
        },
        "compatible_agents": {
          "type": "array",
          "items": { "type": "string" },
          "examples": [["Claude Code", "Codex", "other CLI agent"]]
        }
      }
    },
    "HookInvocation": {
      "type": "object",
      "required": ["hook", "argv", "selected_entrypoint"],
      "properties": {
        "hook": { "type": "string", "enum": ["commit-msg", "prepare-commit-msg"] },
        "argv": { "type": "array", "items": { "type": "string" } },
        "selected_entrypoint": {
          "type": "string",
          "enum": ["SPEC_VC_BIN", "PATH_FALLBACK", "NONE"]
        }
      }
    }
  }
}
```

---

## 行为规则

```gherkin
Feature: hook/venv entrypoint determinism

  Scenario: commit-msg prefers SPEC_VC_BIN over PATH
    Given .git/hooks/commit-msg contains a valid SPEC_VC_BIN
    And PATH contains another spec-vc executable that exits with failure
    When git invokes commit-msg
    Then the hook executes SPEC_VC_BIN
    And the PATH spec-vc is not executed

  Scenario: prepare-commit-msg prefers SPEC_VC_BIN over PATH
    Given .git/hooks/prepare-commit-msg contains a valid SPEC_VC_BIN
    And PATH contains another spec-vc executable that exits with failure
    When git invokes prepare-commit-msg
    Then the hook executes SPEC_VC_BIN
    And the PATH spec-vc is not executed

  Scenario: fallback to PATH only when SPEC_VC_BIN is unavailable
    Given SPEC_VC_BIN points to a missing or non-executable file
    And PATH contains an executable spec-vc
    When git invokes the hook
    Then the hook executes PATH spec-vc

  Scenario: init writes shell-expandable HOME path
    Given spec-vc init installs hooks into a repository
    When the generated hook is inspected
    Then SPEC_VC_BIN is "$HOME/.claude/skills/spec-vc/.venv/bin/spec-vc"
    And SPEC_VC_BIN is not "~/.claude/skills/spec-vc/.venv/bin/spec-vc"

  Scenario: Codex compatibility through ordinary git hook
    Given Codex or another CLI agent runs git commit in a repository initialized by spec-vc
    When git executes prepare-commit-msg and commit-msg
    Then both hooks resolve spec-vc through deterministic shell logic
    And no Claude-specific environment variable is required
```

### 4.1 业务规则

#### Hook 入口选择
- **前置条件**: 目标仓库已运行 `spec-vc init`，hook 模板已安装。
- **触发条件**: git 调用 `prepare-commit-msg` 或 `commit-msg`。
- **执行逻辑**: 先检测 `SPEC_VC_BIN` 是否可执行；可执行则直接 exec；不可执行才查找 PATH 中的 `spec-vc`。
- **后置条件**: 下游 `spec-vc hook ...` 接管后续逻辑。
- **异常处理**: 两个入口都不可用时输出 `[spec-vc] 致命：找不到 spec-vc 可执行文件` 并返回非 0。

### 4.2 状态机（如适用）

```
[hook invoked]
  --SPEC_VC_BIN executable--> [exec SPEC_VC_BIN]
  --SPEC_VC_BIN unavailable and PATH spec-vc exists--> [exec PATH spec-vc]
  --no executable found--> [exit 1]
```

### 4.3 幂等性要求

`spec-vc init` 重复执行必须覆盖 hook 模板并修复旧入口顺序，不追加重复 hook。`.claude/settings.json` 的 PostToolUse hook 仍保持已有去重/升级逻辑。

### 4.4 并发控制

无并发状态写入；hook 执行是单进程 exec 链路。

---

## 非目标

### 5.1 明确排除的功能
- 不实现 Codex 专属 MCP、hook 或配置格式。
- 不修改 commit-msg 校验链本身。
- 不修改 review.json schema。
- 不删除 PATH fallback，只将其降级为最后兜底。

### 5.2 未来可能扩展
- 支持自定义安装路径环境变量，例如 `SPEC_VC_BIN` 外部覆盖。
- 支持全局包管理器安装模式的文档化。

---

## 非功能性需求

### 6.1 性能要求
| 指标 | 目标值 | 测量方法 |
|------|--------|----------|
| hook 入口选择开销 | < 10ms | shell test |

### 6.2 可用性要求
- `SPEC_VC_BIN` 可用时不受项目 venv、PATH 顺序、Codex/Claude 运行环境影响。

### 6.3 安全要求
- hook 不执行来自仓库相对路径的未验证 `spec-vc`。
- PATH fallback 仅在 deterministic 入口不可用时使用。

### 6.4 监控告警
不适用。

---

## 错误处理

### 7.1 异常分类
| 类别 | 示例 | 处理策略 |
|------|------|----------|
| deterministic 入口不可用 | `$HOME/.claude/.../spec-vc` 不存在 | fallback 到 PATH |
| PATH fallback 不可用 | PATH 无 `spec-vc` | stderr 明确错误 + exit 1 |
| 下游校验阻塞 | review.json anchor 不匹配 | 保持 ADR-018/020 BlockingError 输出 |

### 7.2 降级策略
仅当 `SPEC_VC_BIN` 不存在或不可执行时 fallback 到 PATH 中的 `spec-vc`。

### 7.3 重试策略
无自动重试；用户可运行 `spec-vc init` 修复 hook。

---

## 测试策略

### 8.1 验收标准
```gherkin
Given PATH contains a broken spec-vc executable
And the hook template contains executable SPEC_VC_BIN
When commit-msg or prepare-commit-msg is invoked
Then the hook uses SPEC_VC_BIN
And the broken PATH executable is not called
```

### 8.2 测试用例
| 测试类型 | 覆盖范围 | 优先级 |
|----------|----------|--------|
| 单元测试 | `_install_hook` 写入 `$HOME` 路径 | P0 |
| 单元测试 | commit-msg hook 入口优先级 | P0 |
| 单元测试 | prepare-commit-msg hook 入口优先级 | P0 |
| 集成测试 | `spec-vc init` 可覆盖旧 hook | P1 |

### 8.3 边界条件
- PATH 中存在坏 `spec-vc`。
- `SPEC_VC_BIN` 不可执行，需要 fallback。
- hook 模板中的 `$HOME` 不应提前展开为具体用户路径。

### 8.4 Mock 策略
使用临时目录创建假 `spec-vc` 可执行文件记录调用路径，不依赖真实 Codex 或 Claude。

---

## 日志实现

### 9.1 日志级别规范
hook shim 不新增日志级别；保持 stderr 文本输出。

### 9.2 必须记录的事件
| 事件 | 日志级别 | 必须字段 | 说明 |
|------|----------|----------|------|
| 找不到 spec-vc 可执行文件 | stderr | hook name | 两个入口均不可用时输出 |

### 9.3 日志格式
```text
[spec-vc] 致命：找不到 spec-vc 可执行文件
```

### 9.4 敏感信息处理
不输出 token、密钥或用户输入内容。

### 9.5 日志采样策略
不适用。

---

## 部署与集成

### 10.1 部署要求
- 运行 `uv sync --project ~/.claude/skills/spec-vc` 生成 skill venv。
- 运行 `spec-vc init` 或 skill venv 下的 `spec-vc init` 安装/修复 hook。

### 10.2 数据库迁移
不涉及数据库。

### 10.3 向后兼容
- 旧仓库重跑 `spec-vc init` 后 hook 被覆盖为新入口顺序。
- PATH fallback 保留，非 Claude 安装模式仍可工作。
- Codex 通过普通 git hook 触发，无需额外接入。

---

## 变更历史

| 版本 | 日期 | 作者 | 变更内容 |
|------|------|------|----------|
| 0.1.0 | 2026-05-24 | arcaneorion | 初始版本 |

---

## References

- **ADR**: ADR-021
- **Related Specs**: Spec-018, Spec-020
- **External**: 无
