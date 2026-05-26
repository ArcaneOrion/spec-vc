# ADR-022 执行方案 001

- **ADR**: ADR-022
- **ADR Title**: 审计模式冻结对齐文档基线
- **Stage**: close
- **Created At**: 2026-05-25T23:10:59
- **Summary**: 在 review 进入审计模式时记录 ADR/Plan/Spec 文档基线，commit-msg hook 提交前复算校验，防止审计后改写对齐文档迁就代码。

## Clarification

- 动机与上下文: 在下游项目实战中发现：spec-vc review 进入审计模式后，现有 anchor 只绑定 staged diff，不能防止 AI 在审计后改写 ADR/Plan/Spec 等对齐基线文档来迁就代码，从而制造“已经按文档审查过”的假象。该问题破坏的是审计证据的时间边界，属于 operational harness 缺口。
- 目标与边界: 目标是在 review 写入审计证据时冻结本次审计依赖的对齐文档基线，并在 commit-msg hook 中复算校验。冻结范围为当前 ADR、当前/最新关联 Plan、关联 Spec 的 dev-doc.md 与形式化文件 contract.openapi.yaml/schema.json/behavior.feature。不做全仓库文档锁，不禁止用户在发现规格错误后修改文档；文档改动后必须重新 review 或重新对齐。
- 设计与架构: 在 review.json 中增加 document_baseline 字段，记录基线文件列表、相对路径、sha256、缺失状态等可复算信息。cmd_review 在 assemble_review_report 同一语义上下文下生成基线；commit-msg hook 在 [ADR-NNN] 且非 bypass 时读取 review.json 后复算 document_baseline 并比较。若 ADR/Plan/Spec 内容或文件集合在 review 后变化，则输出 BlockingError，提示重新运行 spec-vc review；这保护审计边界而不引入推理脚手架。
- 实现路径: 新增独立模块负责发现和哈希审计基线文档；扩展 ReviewRecord 的序列化/反序列化以兼容旧 review.json；cmd_review 写入 document_baseline；hooks.py 的 _check_review_record 在 anchor 与 mtime 校验之外增加基线比较；补充 tests/python 中 review 写入基线、review 后修改 ADR/Plan/Spec 被 hook 阻塞、旧 review.json 兼容等测试；同步 SKILL.md 与 ADR/Spec 文档。
- 验证与测试: 修改前先用失败测试复现漏洞：review 后修改 ADR/Plan/Spec，当前 hook 仍放行。修改后用同一测试确认 hook 阻塞，并运行 uv run pytest tests/python/ 全量回归；必要时补充针对基线哈希模块的单元测试。还要通过 spec-vc spec check 与 pre/post validation 记录验证口径。
- 风险与回滚: 若误伤正常流程，可回滚 ReviewRecord document_baseline 写入与 hook 比较逻辑，保留旧 anchor/mtime 校验链。由于字段向后兼容，旧 review.json 不应被解析失败；若线上遇到紧急阻塞，仍保留 SPEC_VC_BYPASS 审计逃生口。


## Clarification History

- 动机与上下文: 在下游项目实战中发现：spec-vc review 进入审计模式后，现有 anchor 只绑定 staged diff，不能防止 AI 在审计后改写 ADR/Plan/Spec 等对齐基线文档来迁就代码，从而制造“已经按文档审查过”的假象。该问题破坏的是审计证据的时间边界，属于 operational harness 缺口。
- 目标与边界: 目标是在 review 写入审计证据时冻结本次审计依赖的对齐文档基线，并在 commit-msg hook 中复算校验。冻结范围为当前 ADR、当前/最新关联 Plan、关联 Spec 的 dev-doc.md 与形式化文件 contract.openapi.yaml/schema.json/behavior.feature。不做全仓库文档锁，不禁止用户在发现规格错误后修改文档；文档改动后必须重新 review 或重新对齐。
- 设计与架构: 在 review.json 中增加 document_baseline 字段，记录基线文件列表、相对路径、sha256、缺失状态等可复算信息。cmd_review 在 assemble_review_report 同一语义上下文下生成基线；commit-msg hook 在 [ADR-NNN] 且非 bypass 时读取 review.json 后复算 document_baseline 并比较。若 ADR/Plan/Spec 内容或文件集合在 review 后变化，则输出 BlockingError，提示重新运行 spec-vc review；这保护审计边界而不引入推理脚手架。
- 实现路径: 新增独立模块负责发现和哈希审计基线文档；扩展 ReviewRecord 的序列化/反序列化以兼容旧 review.json；cmd_review 写入 document_baseline；hooks.py 的 _check_review_record 在 anchor 与 mtime 校验之外增加基线比较；补充 tests/python 中 review 写入基线、review 后修改 ADR/Plan/Spec 被 hook 阻塞、旧 review.json 兼容等测试；同步 SKILL.md 与 ADR/Spec 文档。
- 验证与测试: 修改前先用失败测试复现漏洞：review 后修改 ADR/Plan/Spec，当前 hook 仍放行。修改后用同一测试确认 hook 阻塞，并运行 uv run pytest tests/python/ 全量回归；必要时补充针对基线哈希模块的单元测试。还要通过 spec-vc spec check 与 pre/post validation 记录验证口径。
- 风险与回滚: 若误伤正常流程，可回滚 ReviewRecord document_baseline 写入与 hook 比较逻辑，保留旧 anchor/mtime 校验链。由于字段向后兼容，旧 review.json 不应被解析失败；若线上遇到紧急阻塞，仍保留 SPEC_VC_BYPASS 审计逃生口。


## Motivation and Context

在下游项目实战中发现：spec-vc review 进入审计模式后，现有 anchor 只绑定 staged diff，不能防止 AI 在审计后改写 ADR/Plan/Spec 等对齐基线文档来迁就代码，从而制造“已经按文档审查过”的假象。该问题破坏的是审计证据的时间边界，属于 operational harness 缺口。


## Goals and Boundaries

目标是在 review 写入审计证据时冻结本次审计依赖的对齐文档基线，并在 commit-msg hook 中复算校验。冻结范围为当前 ADR、当前/最新关联 Plan、关联 Spec 的 dev-doc.md 与形式化文件 contract.openapi.yaml/schema.json/behavior.feature。不做全仓库文档锁，不禁止用户在发现规格错误后修改文档；文档改动后必须重新 review 或重新对齐。


## Design and Architecture

在 review.json 中增加 document_baseline 字段，记录基线文件列表、相对路径、sha256、缺失状态等可复算信息。cmd_review 在 assemble_review_report 同一语义上下文下生成基线；commit-msg hook 在 [ADR-NNN] 且非 bypass 时读取 review.json 后复算 document_baseline 并比较。若 ADR/Plan/Spec 内容或文件集合在 review 后变化，则输出 BlockingError，提示重新运行 spec-vc review；这保护审计边界而不引入推理脚手架。


## Implementation Path

新增独立模块负责发现和哈希审计基线文档；扩展 ReviewRecord 的序列化/反序列化以兼容旧 review.json；cmd_review 写入 document_baseline；hooks.py 的 _check_review_record 在 anchor 与 mtime 校验之外增加基线比较；补充 tests/python 中 review 写入基线、review 后修改 ADR/Plan/Spec 被 hook 阻塞、旧 review.json 兼容等测试；同步 SKILL.md 与 ADR/Spec 文档。


## Verification and Testing

修改前先用失败测试复现漏洞：review 后修改 ADR/Plan/Spec，当前 hook 仍放行。修改后用同一测试确认 hook 阻塞，并运行 uv run pytest tests/python/ 全量回归；必要时补充针对基线哈希模块的单元测试。还要通过 spec-vc spec check 与 pre/post validation 记录验证口径。


## Risks and Rollback

若误伤正常流程，可回滚 ReviewRecord document_baseline 写入与 hook 比较逻辑，保留旧 anchor/mtime 校验链。由于字段向后兼容，旧 review.json 不应被解析失败；若线上遇到紧急阻塞，仍保留 SPEC_VC_BYPASS 审计逃生口。


## Affected Areas

- `src/spec_vc/document_baseline.py`: 新增 ADR/Plan/Spec 基线发现、sha256 计算与差异比较。
- `src/spec_vc/cli.py`: `cmd_review` 写入 `review.json.document_baseline`。
- `src/spec_vc/review.py`: `ReviewRecord` 增加向后兼容的 `document_baseline` 字段。
- `src/spec_vc/hooks.py`: `[ADR-NNN]` commit-msg hook 在 anchor/mtime 校验后复算文档基线并阻塞漂移。
- `tests/python/test_cli.py` 与 `tests/python/test_commit.py`: 覆盖 review 后 ADR/Plan/Spec 漂移阻塞、基线字段写入与兼容路径。
- `SKILL.md`、`CLAUDE.md`、`doc/arch/adr-022.md`、`doc/arch/specs/022/`: 同步 ADR-022 流程与契约。

## Pre-Change Validation

前置验证：Spec-022 已创建并 formalize all，spec check 返回“全部 12 个 Spec 就绪”。现状分析与 explorer 独立结论一致：当前 review.json 只含 staged diff anchor/context_summary，不含 ADR/Plan/Spec 文档基线；hooks.py:_check_review_record 仅校验 review.json 存在、anchor 匹配和 mtime 新鲜，不复算对齐文档哈希。因此 review 后修改 ADR/Plan/Spec 当前不会被 hook 识别。本轮修改前验证口径：先补失败测试复现该漏洞，再实现 document_baseline 写入与 hook 复算，使同一测试通过；最后运行 uv run pytest tests/python/ 全量回归。


## Post-Change Validation

后置验证完成：先按 ADR-022 验证口径补失败测试，review 后修改 ADR/Plan 时当前 hook 放行，测试红灯复现漏洞；实现后同一组 document_baseline 测试全部通过（3 passed），覆盖 review 后修改 ADR、Plan、关联 Spec 形式化文件均被 commit-msg hook 阻塞。补充 test_review_writes_commit_msg 断言 review.json.document_baseline 写入 version/adr_token/ADR 文件基线，并跑兼容小回归（document_baseline + 旧 review.json/context_summary + bypass 相关 4 passed）。最终全量回归 uv run pytest tests/python/ 129 passed in 14.49s。Spec-022 已 formalize all，spec check 此前返回全部 12 个 Spec 就绪。


## Closure Summary

实现审计模式文档基线冻结：新增 document_baseline 模块，spec-vc review 写入 ADR/Plan/关联 Spec 的路径、存在性与 sha256；commit-msg hook 在 [ADR-NNN] 路径下复算并阻塞 review 后的基线漂移。覆盖 review 后修改 ADR、Plan、关联 Spec 形式化文件三类回归，保留旧 review.json 兼容与 SPEC_VC_BYPASS 逃生口。


## References

- **Commits**: 待从 git 自动采集
- **Plan**: doc/arch/plans/ADR-022-plan-001.md


## Checkpoints

- [x] 澄清完成
- [x] 前置验证完成
- [x] 实施完成
- [x] 后置验证完成
- [ ] ADR 回填完成
