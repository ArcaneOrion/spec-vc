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
