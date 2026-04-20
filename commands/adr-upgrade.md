---
description: 把当前项目 .git/hooks/ 中的 spec-vc hook 升级到本 skill 的最新版本
---

# /spec-vc adr-upgrade

升级当前项目 `.git/hooks/` 下的 spec-vc hook 到 `$SKILL_ROOT/hooks/` 的当前版本。

## 背景

`/spec-vc adr-init` 使用 `cp` 策略安装 hooks——独立、稳健,但与 skill 版本会漂移。`upgrade` 命令提供显式同步入口。

## 执行步骤(给 Claude 的指令)

### 1. 解析 SKILL_ROOT

同 `init.md`。

### 2. 读取双方版本

```bash
extract_version() {
    local f="$1"
    grep -m1 -oE '^# Version:\s*[0-9]+\.[0-9]+\.[0-9]+' "$f" 2>/dev/null \
        | sed -E 's/^# Version:\s*//' \
        || echo "unknown"
}

LOCAL_COMMIT_MSG_VER=$(extract_version .git/hooks/commit-msg)
LOCAL_PREPARE_VER=$(extract_version .git/hooks/prepare-commit-msg)
SKILL_COMMIT_MSG_VER=$(extract_version "$SKILL_ROOT/hooks/commit-msg")
SKILL_PREPARE_VER=$(extract_version "$SKILL_ROOT/hooks/prepare-commit-msg")
```

### 3. 对比并报告

对每个 hook,展示:
```
commit-msg:
  local  : 0.0.5  (.git/hooks/commit-msg)
  skill  : 0.1.0  ($SKILL_ROOT/hooks/commit-msg)
  status : 需升级
```

如果版本一致,跳过。如果本地 hook 不含 spec-vc 标识(extract_version 返回 unknown),提示这是外部 hook,询问是否覆盖/备份。

### 4. 展示 diff

```bash
diff -u .git/hooks/commit-msg "$SKILL_ROOT/hooks/commit-msg" | head -n 100
```

### 5. 询问并执行

用 `AskUserQuestion` 询问:
- (a) 全部覆盖(含备份到 `.git/hooks/<name>.backup-<timestamp>`)
- (b) 逐个确认
- (c) 中止

执行后验证:
```bash
bash -n .git/hooks/commit-msg  # 语法检查
```

### 6. 输出清单

```
✅ upgrade 完成
  - commit-msg:        0.0.5 → 0.1.0
  - prepare-commit-msg: 0.0.5 → 0.1.0  (跳过,版本一致)

备份文件:
  - .git/hooks/commit-msg.backup-20260420-202530

下一步:
  - 运行 /spec-vc adr-status 验证一切正常
```

## 错误处理

- 如果本地 hook 被用户魔改(与 skill 原始 `0.x.y` 版本 diff 巨大),强制保留备份并明确警告
- 如果脚本语法错误,回滚到备份

## 何时运行

- skill 仓库 pull 了新版本后
- 修改本 skill 的 hook 后,同步到已初始化的项目
- `/spec-vc adr-status` 报告"hook 行为与预期不符"时(未来可能补自检)
