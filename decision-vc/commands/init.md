---
description: 在当前项目中初始化 decision-vc 基础设施,创建 doc/arch/ 目录并安装 git hooks
---

# /decision-vc init

在当前 git 仓库中初始化 ADR 基础设施。

## 参数

- `--seed/--no-seed`(默认 `--seed`):是否生成种子 ADR-000"采用 ADR 方法论"
- `--adr-dir=<path>`(默认 `doc/arch`):ADR 目录位置

## 前置约定

本命令引用 `$SKILL_ROOT`,解析规则见 `SKILL.md` 顶部"SKILL_ROOT 约定"。所有 `cp`/`Read` 路径都以 `$SKILL_ROOT` 为根,不硬编码任何仓库绝对路径。

## 执行步骤(给 Claude 的指令)

### 1. 解析 SKILL_ROOT

SKILL.md 所在目录即为 `$SKILL_ROOT`。在调用脚本前,先用 `Bash` 把 `$SKILL_ROOT` 赋值好,后续所有命令通过 `env SKILL_ROOT="$SKILL_ROOT" ...` 显式传入。

### 2. 校验前置条件

- `git rev-parse --is-inside-work-tree` 为 true(否则提示"先 git init")
- `.git/hooks/` 目录存在(否则可能是 submodule/worktree,提示手动指定)
- 目标 `${ADR_DIR}` 不存在,或用户同意覆盖

### 3. 创建 ADR 目录与索引

```bash
mkdir -p "${ADR_DIR}"
# 从模板渲染索引(替换 {{DATE}} 等占位符,当前模板无占位符需替换)
cp "$SKILL_ROOT/templates/index.md" "${ADR_DIR}/README.md"
```

### 4. 生成种子 ADR-000(若 --seed)

```bash
# 从固定种子模板渲染(不依赖 Claude 现场填充,保证内容确定)
DATE=$(date +%Y-%m-%d)
AUTHOR=$(git config user.name 2>/dev/null || echo "unknown")
sed -e "s|{{DATE}}|${DATE}|g" \
    -e "s|{{AUTHOR}}|${AUTHOR}|g" \
    "$SKILL_ROOT/templates/seed-adr-000.md" > "${ADR_DIR}/adr-000.md"
```

如果用户传 `--no-seed`,跳过此步。后续第一条 ADR 由 `/decision-vc new` 创建,编号仍从 000 起。

### 5. 安装 git hooks (cp 策略)

```bash
cp "$SKILL_ROOT/hooks/prepare-commit-msg" .git/hooks/prepare-commit-msg
cp "$SKILL_ROOT/hooks/commit-msg"         .git/hooks/commit-msg
chmod +x .git/hooks/prepare-commit-msg .git/hooks/commit-msg
```

**为什么选 cp 不选 symlink**:

- cp:项目 hooks 独立于 skill,即使 skill 被删除或移动,项目 hooks 仍能工作
- 代价:skill 升级后各项目 hooks 漂移,需要显式运行 `/decision-vc upgrade` 同步
- symlink 的替代方案会导致"skill 目录一动所有项目 hooks 全坏",风险过高

**冲突处理**:如果 `.git/hooks/commit-msg` 已存在且非 decision-vc(文件头无 `decision-vc` 字样),询问用户:
- (a) 备份旧 hook 为 `.git/hooks/commit-msg.backup-<timestamp>` 后覆盖
- (b) 中止,由用户手动合并
- (c) 把旧 hook 内容作为第一步,decision-vc 校验作为第二步,串联执行

### 6. 配置 commit message 模板

```bash
git config commit.template "$SKILL_ROOT/templates/commit-msg"
```

该配置是**本仓库级别**的(写入 `.git/config`),不会影响其他项目。

### 7. 如果配置了非默认 ADR_DIR

默认 `ADR_DIR=doc/arch` 已写死在 hook 里。如果用户指定了其他路径,当前版本要求用户手动在 hook 顶部设置 `ADR_DIR=...`(或 export 环境变量)。v0.2 会提供 `.git/hooks/decision-vc.env` 自动加载机制。

### 8. 输出清单

```
✅ decision-vc 初始化成功
  - doc/arch/README.md       (ADR 索引)
  - doc/arch/adr-000.md      (种子:采用 ADR 方法论)  [若 --seed]
  - .git/hooks/prepare-commit-msg
  - .git/hooks/commit-msg
  - git config commit.template (已配置)

下一步:
  1. 创建首条实际 ADR:/decision-vc new "<title>"
  2. 正常开发 → git commit,subject 行末尾加 [ADR-NNN] 或 [ADR-none]
  3. 周期性运行 /decision-vc status 检查锚定健康
```

## 错误处理

- 不在 git 仓库:提示先 `git init`,不进行任何改动
- hooks 目录不存在:提示可能是 submodule/worktree
- 用户拒绝覆盖已有 `doc/arch/` 或 hooks:直接退出,不做任何改动

## 测试清单

初始化后应满足(见 `tests/e2e-init.sh`):

- [x] `doc/arch/README.md` 存在
- [x] 若 `--seed`,`doc/arch/adr-000.md` 存在且 Status 为 Accepted
- [x] `.git/hooks/commit-msg` 可执行
- [x] `git commit --allow-empty -m "test"` 被阻塞(缺 [ADR-])
- [x] `git commit --allow-empty -m "test [ADR-000]"` 通过(若 --seed)
- [x] `git commit --allow-empty -m "test [ADR-999]"` 被阻塞(引用不存在的 ADR)
