# spec-vc CLI 重构设计文档

## 1. 文档目的

本文档定义 `spec-vc` 从“基于 `commands/*.md` 的 agent 执行说明 + shell 脚本/ hooks”重构为“由正式 CLI 定义行为”的设计方案。

目标不是立刻替换全部现有实现，而是在**保持现有 Layer 2（ADR + commit 锚定）能力可用**的前提下，逐步完成以下转变：

- 把命令行为从 Markdown 指令迁移到可测试、可复用的程序实现
- 把复杂规则从 shell 文本处理迁移到结构化代码
- 把 hooks 从“承载规则本体”收敛为“调用 CLI 的薄 shim”
- 为后续 `spec-*` 子命令族（Layer 3）预留稳定的命令框架

本文档也作为**下次继续此重构工作时的上下文入口**使用；第 14 节包含可直接续作的状态摘要与建议顺序。

---

## 2. 当前状态与问题定义

### 2.1 当前仓库的真实实现边界

当前仓库已实现并可验证的能力主要集中在 Layer 2：

- `hooks/prepare-commit-msg`：在 commit message 中注入 `[ADR-???]` 提示
- `hooks/commit-msg`：强制要求 `[ADR-NNN]` 或 `[ADR-none]`
- `scripts/new-adr.sh`：生成新 ADR 文件
- `scripts/check-refs.sh`：做基础健康检查
- `tests/e2e-init.sh`：验证最小端到端闭环

当前仓库**未实现**或**未完全收敛**的部分包括：

- `commands/*.md` 仍是 agent 执行说明，不是正式 CLI
- `[ADR-none]` 豁免规则仍为占位实现
- `check-refs.sh` 还未实现严格意义上的“双向引用一致性检查”
- `doc/arch/README.md` 索引维护未完全程序化
- Layer 3 的 `spec-*` 命令尚未开始正式实现

### 2.2 当前实现的核心问题

从工程角度看，当前主要矛盾不是“功能完全没有”，而是“**行为定义分散且不稳定**”。

当前行为分散在四处：

- `README.md`：框架宣称与用户说明
- `commands/*.md`：给 agent 的命令执行步骤
- `hooks/*.sh`：运行时约束
- `scripts/*.sh`：部分实现逻辑

由此产生的直接问题：

1. **实现与文档漂移**
   - 例如 `commands/adr-new.md` 说明要更新索引，但 `scripts/new-adr.sh` 不负责该行为
2. **行为依赖 agent 解释**
   - 相同命令在不同 agent / 上下文下可能有不同执行结果
3. **测试无法覆盖“命令级行为”**
   - 当前只能测脚本与 hooks，不能测完整命令系统
4. **规则重复表达且难以演进**
   - 状态解析、路径约定、引用规则散落在多个 shell / Markdown 文件中

---

## 3. 重构目标

### 3.1 总体目标

将 `spec-vc` 重构为一个以 CLI 为主、以 Markdown 文档为辅、以 shell hook 为接入层的工具：

- **CLI 定义行为**
- **Markdown 解释行为**
- **hooks 调用行为**

### 3.2 非目标

本次重构的非目标：

- 不在第一阶段引入 Layer 3 的完整实现
- 不在第一阶段解决所有团队级策略差异（如每个仓库不同的豁免规则）
- 不追求立即删除全部现有 shell 脚本
- 不引入服务端、数据库或后台守护进程

### 3.3 成功标准

当以下条件满足时，可认为 CLI 重构一期完成：

1. 用户可通过正式命令运行：
   - `spec-vc adr init`
   - `spec-vc adr new`
   - `spec-vc adr list`
   - `spec-vc adr status`
   - `spec-vc adr upgrade`
2. hooks 不再承载复杂规则，只作为 shim 调用 CLI
3. ADR 解析与状态校验使用统一代码路径，而不是多处 `grep/sed`
4. `commands/*.md` 不再定义行为，只保留帮助文档与示例
5. 自动化测试覆盖 CLI 主路径，而不仅是 shell 片段

---

## 4. 设计原则

### 4.1 单一事实源

命令语义应只有一个事实源：**CLI 实现代码**。

文档、hooks、测试、README 都应引用该语义，而不是各自再定义一份“接近但不完全一致”的规则。

### 4.2 结构化优先于文本拼接

凡涉及以下对象，应优先做结构化解析，而不是文本近似匹配：

- ADR 元数据
- 状态机
- commit 中的 ADR 引用
- 项目配置

### 4.3 渐进迁移

现有 shell 与模板资产不应一次性推倒重来，而应按“保兼容、逐步收敛”的方式迁移。

### 4.4 可测试性优先

新实现的设计应以“能写稳定测试”为约束：

- 纯逻辑可做单测
- git 交互可做集成测试
- hook 交互可做端到端测试

### 4.5 层次清晰

需要明确区分三类职责：

- **领域逻辑**：ADR、状态、引用、一致性规则
- **命令接口**：CLI 参数与输出
- **仓库接入**：git hook、模板安装、文件复制

---

## 5. 技术选型

### 5.1 语言与运行时

选择 Python，理由：

- 当前工作环境明确为 NixOS，Python 由 `uv` 管理
- 需要较强的文本/文件/子进程处理能力
- 需要较强的测试支持
- 后续若扩展到 Layer 3，Python 生态适合做多种格式适配

### 5.2 CLI 框架

一期建议使用标准库 `argparse`。

原因：

- 依赖最少
- 规则模型尚未稳定，先保证行为收敛而非命令美观
- 未来如确有需要，可再切换到 `typer`

### 5.3 项目管理

使用 `uv` 管理 Python 项目：

- 新增 `pyproject.toml`
- 提供可执行入口 `spec-vc`
- 在测试中使用 `uv run` 统一环境

---

## 6. 目标架构

建议的新目录结构如下：

```text
spec-vc/
├── pyproject.toml
├── README.md
├── SKILL.md
├── src/
│   └── spec_vc/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── adr.py
│       ├── index.py
│       ├── gitops.py
│       ├── status.py
│       ├── hooks.py
│       ├── templates.py
│       └── errors.py
├── hooks/
│   ├── commit-msg
│   └── prepare-commit-msg
├── templates/
├── commands/
├── tests/
└── doc/
```

### 6.1 模块职责

#### `src/spec_vc/cli.py`

- CLI 入口
- 子命令注册
- 参数解析
- 统一退出码处理

#### `src/spec_vc/config.py`

- 读取项目配置
- 合并默认值、仓库配置、环境变量覆盖
- 暴露统一配置对象

#### `src/spec_vc/adr.py`

- ADR 文件解析
- ADR 编号分配
- ADR 模板渲染
- ADR 状态合法性校验

#### `src/spec_vc/index.py`

- 生成并更新 `doc/arch/README.md` 中的 ADR 表格
- 保持索引输出稳定排序

#### `src/spec_vc/gitops.py`

- 对 `git` 子命令做薄封装
- 提供：是否在仓库内、读 log、读 staged files、读 config、安装 hooks 等

#### `src/spec_vc/status.py`

- 计算健康检查结果
- 定义结果模型：幽灵引用、孤儿 ADR、状态漂移、引用不一致
- 输出 text / table / json 三种格式的基础数据

#### `src/spec_vc/hooks.py`

- 实现 `commit-msg` / `prepare-commit-msg` 的真正规则逻辑
- shell hook 仅负责调用这里

#### `src/spec_vc/templates.py`

- 定位模板目录
- 渲染模板内容
- 负责安全替换与模板读取

#### `src/spec_vc/errors.py`

- 定义领域错误类型
- 统一错误消息与 exit code 映射

---

## 7. 配置模型

### 7.1 配置文件

建议引入仓库级配置文件：`.spec-vc.toml`

示例：

```toml
[project]
adr_dir = "doc/arch"
strict = true

[exemption]
enabled = true
allowed_paths = ["README.md", "docs/**", ".github/**"]
blocked_paths = ["src/**", "lib/**", "core/**"]
allowed_extensions = [".md", ".txt"]
max_changed_lines = 40

[hooks]
install_mode = "shim"
```

### 7.2 配置优先级

建议采用以下优先级：

1. CLI 显式参数
2. 环境变量
3. `.spec-vc.toml`
4. 默认值

### 7.3 初期必须配置项

第一阶段只需要正式支持以下字段：

- `adr_dir`
- `strict`
- `[exemption]` 基本规则

其他配置可以先保留为未来扩展点。

---

## 8. CLI 命令设计

### 8.1 用户可见命令

```bash
spec-vc adr init
spec-vc adr new "<title>"
spec-vc adr list
spec-vc adr status
spec-vc adr link
spec-vc adr upgrade
```

### 8.2 hooks 专用内部命令

```bash
spec-vc hook commit-msg <message-file>
spec-vc hook prepare-commit-msg <message-file> [source] [sha]
```

这样做的目的：

- 让 shell hook 变薄
- 让规则只维护一份
- 让测试直接覆盖 Python 实现

### 8.3 命令语义约束

#### `spec-vc adr init`

职责：

- 初始化 ADR 目录
- 可选生成种子 ADR-000
- 安装 hooks
- 配置 commit template

输出结果应明确列出创建/修改的文件。

#### `spec-vc adr new <title>`

职责：

- 分配新编号
- 渲染新 ADR
- 更新索引
- 输出推荐 commit message

要求：

- 不允许覆盖现有 `adr-NNN.md`
- 必须保证编号分配安全

#### `spec-vc adr list`

职责：

- 列出 ADR
- 支持按状态过滤
- 支持不同输出格式

#### `spec-vc adr status`

职责：

- 扫描健康状态
- 支持输出 text / json
- 支持限定 revision range

注意：

- 这里建议废弃 `--since=<ref>` 这一含混参数
- 改为：`--rev-range=<A..B>` 或 `--base-ref=<ref>`

#### `spec-vc adr upgrade`

职责：

- 对比本地 hook 版本与当前 CLI 版本
- 备份旧 hook
- 更新为新 shim

---

## 9. hooks 收敛方案

### 9.1 目标状态

最终 shell hooks 不再承载核心规则，只做 CLI 调用。

#### 目标 `commit-msg` shim

```bash
#!/usr/bin/env bash
set -euo pipefail
exec spec-vc hook commit-msg "$1"
```

#### 目标 `prepare-commit-msg` shim

```bash
#!/usr/bin/env bash
set -euo pipefail
exec spec-vc hook prepare-commit-msg "$1" "${2:-}" "${3:-}"
```

### 9.2 为什么要这样做

好处有四个：

1. 规则只有一份
2. shell 文本处理风险降低
3. 测试可直接覆盖核心逻辑
4. hook 升级简单稳定

### 9.3 兼容策略

第一阶段仍保留仓库中的 `hooks/commit-msg` 与 `hooks/prepare-commit-msg` 文件，但内容改为 shim。

用户若尚未安装 CLI，可在 shim 中打印明确错误：

- 未找到 `spec-vc`
- 提示使用 `uv run spec-vc ...` 或先安装 CLI

---

## 10. 领域模型与规则收敛

### 10.1 ADR 数据模型

建议至少抽象为：

- `id: str`
- `title: str`
- `date: str`
- `status: str`
- `deciders: list[str]`
- `tags: list[str]`
- `references_commits: list[str]`
- `path: Path`

### 10.2 commit 引用模型

建议显式解析：

- `subject`
- `adr_refs`（出现的全部 ADR 标签）
- `has_none_exemption`

而不是只取“第一个匹配到的标签”。

### 10.3 `commit-msg` 的正式规则

一期建议规则如下：

1. subject 必须且只能包含一个引用：
   - `[ADR-NNN]`
   - 或 `[ADR-none]`
2. `[ADR-NNN]` 必须满足：
   - ADR 文件存在
   - ADR 文件头部 ID 与路径一致
   - 状态属于允许被引用的集合
3. `[ADR-none]` 必须通过豁免检查
4. 未知状态、非法状态、重复标签、混合标签都应失败

### 10.4 `[ADR-none]` 豁免策略

这是当前项目最重要的未完成点。

建议第一阶段采用“保守可配置”策略：

- 路径白名单
- 路径黑名单
- 扩展名白名单
- 改动行数上限

判断原则：

- 默认拒绝风险不明确的改动
- 明确允许文档、注释、非功能性元文件变更
- 对 `src/`, `lib/`, `core/` 等代码路径默认拒绝

### 10.5 `status` 的正式检查模型

一期至少支持四类检查：

1. **幽灵引用**：commit 引用的 ADR 文件不存在
2. **孤儿 ADR**：已接受 ADR 没有任何实现 commit
3. **状态漂移**：`Superseded by ADR-XXX` 的目标不存在或非法
4. **引用不一致**：ADR `References.Commits` 与 git 历史中的引用不一致

注意：

- `Proposed` 且尚无 commit 的 ADR 不应直接判硬错误
- 应区分 warning 与 error

---

## 11. 测试策略

### 11.1 测试分层

建议三层测试：

#### 单元测试

覆盖：

- ADR 解析
- commit subject 解析
- 状态机校验
- 豁免规则判定
- 索引生成

#### 集成测试

覆盖：

- 在临时 git 仓库中运行 CLI
- 真实创建文件与 hooks
- 验证 status 输出

#### 端到端测试

覆盖：

- `git commit` 真正触发 shim hooks
- `[ADR-none]` 可通过 / 不可通过样例
- 多 ADR 标签失败
- 非法状态失败

### 11.2 现有测试的保留与迁移

`tests/e2e-init.sh` 不应立刻删除。

建议：

- 短期保留，作为回归保护
- 同时新增 Python 测试
- 当 Python e2e 覆盖完整后，再决定是否退役 shell e2e

---

## 12. 迁移计划

### Phase 0：规则冻结与设计确认

目标：

- 冻结一期命令面
- 冻结 ADR 状态机和豁免规则模型

交付物：

- 本设计文档

### Phase 1：建立 Python CLI 骨架

目标：

- 新增 `pyproject.toml`
- 建立 `src/spec_vc/cli.py`
- 打通 `spec-vc adr list`

优先原因：

- `list` 是读操作，风险最小，适合作为 CLI 骨架验证

### Phase 2：迁移 ADR 生成与索引维护

目标：

- 用 Python 替代 `scripts/new-adr.sh`
- 同步实现索引更新
- 添加编号冲突保护

### Phase 3：迁移健康检查

目标：

- 用 Python 替代 `scripts/check-refs.sh`
- 修正 revision range 语义
- 引入 warning/error 分级
- 引入真正的双向引用一致性检查

### Phase 4：迁移 hook 逻辑

目标：

- 实现 `spec-vc hook commit-msg`
- 实现 `spec-vc hook prepare-commit-msg`
- shell hooks 改为 shim

### Phase 5：文档与命令收尾

目标：

- `commands/*.md` 改写为帮助文档
- `README.md` 改写为以 CLI 为中心的使用说明
- 保留 shell 脚本仅作过渡兼容，或逐步废弃

---

## 13. 风险与权衡

### 13.1 为什么不继续堆 shell

可以继续增强 shell 脚本，但长期成本较高：

- 文本解析脆弱
- 状态模型难维护
- 测试和复用不方便
- 复杂度上升后可读性迅速下降

因此 shell 适合做 shim，不适合承载不断增长的领域规则。

### 13.2 为什么不直接上 `typer`

不是不能，而是当前最关键问题不是开发体验，而是规则收敛与行为统一。

在规则尚未稳定时，引入更多 CLI 语法层抽象收益有限。

### 13.3 为什么不立刻删除 `commands/*.md`

因为它们现在同时承担“现有 skill 的用户入口”和“设计参考”的作用。

正确做法不是先删，而是：

- 先让 CLI 成为行为事实源
- 再把 `commands/*.md` 降级为帮助文档

---

## 14. 续作上下文（下次继续请先读这里）

### 14.1 当前已确认的事实

以下事项已在本次分析中明确：

1. 当前仓库没有正式 CLI，只有 `commands/*.md` 的执行说明
2. 当前可工作的运行核心是：
   - `hooks/commit-msg`
   - `hooks/prepare-commit-msg`
   - `scripts/new-adr.sh`
   - `scripts/check-refs.sh`
3. 已验证语法与最小 e2e：
   - `bash -n hooks/commit-msg`
   - `bash -n hooks/prepare-commit-msg`
   - `bash -n scripts/check-refs.sh`
   - `bash -n scripts/new-adr.sh`
   - `bash tests/e2e-init.sh`
4. 当前最大实现缺口：
   - `[ADR-none]` 豁免规则未实现
   - `check-refs.sh` 不是真正双向校验
   - `commands/*.md` 与实现存在漂移

### 14.2 已确认的优先级

下次继续时，建议按以下顺序推进：

1. 建立 Python CLI 骨架（先做 `adr list`）
2. 迁移 `new-adr.sh`，同时补索引更新
3. 迁移 `check-refs.sh`，修复 range 语义与双向一致性
4. 迁移 hooks 逻辑
5. 最后再收尾 `commands/*.md` 与 README

### 14.3 下次启动建议读取的文件

下次继续时，建议最先阅读这些文件：

- `doc/cli-refactor-design.md`
- `README.md`
- `SKILL.md`
- `hooks/commit-msg`
- `scripts/check-refs.sh`
- `scripts/new-adr.sh`
- `tests/e2e-init.sh`

### 14.4 下次可直接执行的首个实现任务

如果下次要直接开始编码，建议第一步做：

- 新建 `pyproject.toml`
- 新建 `src/spec_vc/cli.py`
- 先实现 `spec-vc adr list`

原因：

- 纯读操作，风险最低
- 能最快验证 CLI 包结构、入口、参数解析、测试方式是否顺畅

---

## 15. 简短结论

本次重构的本质，不是“把 shell 改写成 Python”这么简单，而是：

- 把行为定义从 Markdown 解释层收回到程序实现层
- 把规则从文本匹配收敛到结构化领域模型
- 把 hooks 从规则本体收敛为 CLI 入口

若该设计落地，`spec-vc` 将从“可工作的 skill 原型”升级为“有稳定行为定义的工程工具”，这也是后续扩展到 Layer 3 的必要前提。
