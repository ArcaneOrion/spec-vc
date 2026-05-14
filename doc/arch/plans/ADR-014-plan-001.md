# ADR-014 执行方案 001

- **ADR**: ADR-014
- **ADR Title**: 修复审计发现的6个致命缺陷
- **Stage**: close
- **Created At**: 2026-05-14T18:00:30
- **Summary**: 修复审计发现的6个致命缺陷：导入遮蔽、重复模板段、配置类型损坏、路径遍历、hook硬编码路径、Bash兼容性

## Clarification

- 动机与上下文: 审计发现6个致命缺陷阻塞项目正确性和可移植性：(B1)change.py导入被本地同名函数遮蔽导致读写不对称、(B2)create_plan模板中Risks and Rollback段重复出现污染所有plan文件、(B3)config.py的bool()/list()/int()强制转换静默损坏TOML配置值、(B4)read_plan_content和plan_path缺少路径遍历防御、(B5)hooks/commit-msg硬编码Claude Code安装路径导致在其他环境永久阻塞、(B6)scripts/check-refs.sh使用declare -A关联数组不兼容macOS默认Bash 3.2
- 目标与边界: 仅修复6个致命缺陷，不改动架构设计，不引入新功能。修改范围限定在change.py/config.py/cli.py/_sections.py/hooks/commit-msg/scripts/check-refs.sh。不同时处理高危/中危/低危问题
- 设计与架构: 逐缺陷最小侵入性修复：B1删除change.py:9死代码导入保留本地_read_section（两个实现语义不同各服务于spec.py和change.py不同场景）；B2删除change.py:261-264重复模板行；B3用isinstance类型守卫替换bool()/list()/int()强制转换并向用户提供描述性ValidationError；B4在read_plan_content加plan_id格式正则校验+plan_path加路径包含性检查；B5将hooks/commit-msg改为模板文件init时动态填充SPEC_VC_BIN；B6用普通索引数组替代declare -A关联数组
- 实现路径: 执行顺序：B1(零风险纯删除)→B2(行删除)→B4(安全加固)→B3(涉及config层需更新测试)→B5(变更hook安装流程)→B6(独立脚本最低优先级)。每缺陷独立commit便于回退
- 验证与测试: 每修复后运行相关单元测试；全部完成后运行pytest tests/python/ -v完整测试套件；B5手动验证spec-vc init在新环境生成正确hook路径；B6手动在macOS验证check-refs.sh可执行
- 风险与回滚: 每缺陷独立提交，可单独cherry-pick回退。风险点：B3对之前enabled='false'(字符串)的配置行为从静默反转变为明确报错——这是修复而非破坏；B4路径校验可能影响plan_path的19处调用点需逐一验证


## Clarification History

- 动机与上下文: 审计发现6个致命缺陷阻塞项目正确性和可移植性：(B1)change.py导入被本地同名函数遮蔽导致读写不对称、(B2)create_plan模板中Risks and Rollback段重复出现污染所有plan文件、(B3)config.py的bool()/list()/int()强制转换静默损坏TOML配置值、(B4)read_plan_content和plan_path缺少路径遍历防御、(B5)hooks/commit-msg硬编码Claude Code安装路径导致在其他环境永久阻塞、(B6)scripts/check-refs.sh使用declare -A关联数组不兼容macOS默认Bash 3.2
- 目标与边界: 仅修复6个致命缺陷，不改动架构设计，不引入新功能。修改范围限定在change.py/config.py/cli.py/_sections.py/hooks/commit-msg/scripts/check-refs.sh。不同时处理高危/中危/低危问题
- 设计与架构: 逐缺陷最小侵入性修复：B1删除change.py:9死代码导入保留本地_read_section（两个实现语义不同各服务于spec.py和change.py不同场景）；B2删除change.py:261-264重复模板行；B3用isinstance类型守卫替换bool()/list()/int()强制转换并向用户提供描述性ValidationError；B4在read_plan_content加plan_id格式正则校验+plan_path加路径包含性检查；B5将hooks/commit-msg改为模板文件init时动态填充SPEC_VC_BIN；B6用普通索引数组替代declare -A关联数组
- 实现路径: 执行顺序：B1(零风险纯删除)→B2(行删除)→B4(安全加固)→B3(涉及config层需更新测试)→B5(变更hook安装流程)→B6(独立脚本最低优先级)。每缺陷独立commit便于回退
- 验证与测试: 每修复后运行相关单元测试；全部完成后运行pytest tests/python/ -v完整测试套件；B5手动验证spec-vc init在新环境生成正确hook路径；B6手动在macOS验证check-refs.sh可执行
- 风险与回滚: 每缺陷独立提交，可单独cherry-pick回退。风险点：B3对之前enabled='false'(字符串)的配置行为从静默反转变为明确报错——这是修复而非破坏；B4路径校验可能影响plan_path的19处调用点需逐一验证


## Motivation and Context

审计发现6个致命缺陷阻塞项目正确性和可移植性：(B1)change.py导入被本地同名函数遮蔽导致读写不对称、(B2)create_plan模板中Risks and Rollback段重复出现污染所有plan文件、(B3)config.py的bool()/list()/int()强制转换静默损坏TOML配置值、(B4)read_plan_content和plan_path缺少路径遍历防御、(B5)hooks/commit-msg硬编码Claude Code安装路径导致在其他环境永久阻塞、(B6)scripts/check-refs.sh使用declare -A关联数组不兼容macOS默认Bash 3.2


## Goals and Boundaries

仅修复6个致命缺陷，不改动架构设计，不引入新功能。修改范围限定在change.py/config.py/cli.py/_sections.py/hooks/commit-msg/scripts/check-refs.sh。不同时处理高危/中危/低危问题


## Design and Architecture

逐缺陷最小侵入性修复：B1删除change.py:9死代码导入保留本地_read_section（两个实现语义不同各服务于spec.py和change.py不同场景）；B2删除change.py:261-264重复模板行；B3用isinstance类型守卫替换bool()/list()/int()强制转换并向用户提供描述性ValidationError；B4在read_plan_content加plan_id格式正则校验+plan_path加路径包含性检查；B5将hooks/commit-msg改为模板文件init时动态填充SPEC_VC_BIN；B6用普通索引数组替代declare -A关联数组


## Implementation Path

执行顺序：B1(零风险纯删除)→B2(行删除)→B4(安全加固)→B3(涉及config层需更新测试)→B5(变更hook安装流程)→B6(独立脚本最低优先级)。每缺陷独立commit便于回退


## Verification and Testing

每修复后运行相关单元测试；全部完成后运行pytest tests/python/ -v完整测试套件；B5手动验证spec-vc init在新环境生成正确hook路径；B6手动在macOS验证check-refs.sh可执行


## Risks and Rollback

每缺陷独立提交，可单独cherry-pick回退。风险点：B3对之前enabled='false'(字符串)的配置行为从静默反转变为明确报错——这是修复而非破坏；B4路径校验可能影响plan_path的19处调用点需逐一验证


## Affected Areas

待补充

## Pre-Change Validation

变更范围已验证：6个致命缺陷定位明确，每项修复方案已做可行边界审计。B1纯删除无风险；B2行删除无副作用；B4路径校验覆盖19处plan_path调用需逐一验证；B3 isinstance守卫对正确配置零影响对错误配置明确报错；B5 hook模板替换在spec-vc init时动态计算路径；B6索引数组替代关联数组消除macOS兼容性问题。所有修复可独立回退。


## Post-Change Validation

全部6个致命缺陷已修复，89个测试全部通过：(1)B1删除死代码导入，change子系统22测试通过；(2)B2删除重复模板段，change子系统22测试通过；(3)B4添加plan_id正则校验+plan_path路径包含检查，全测试套件89通过；(4)B3用isinstance类型守卫替换bool()/list()/int()强制转换，全测试套件89通过；(5)B5 hooks/commit-msg模板化+_install_hook动态填充+_init_claude_hook动态计算路径，全测试套件89通过；(6)B6 check-refs.sh用索引数组+临时文件替代declare -A，脚本在仓库内正确运行并识别出2个孤儿ADR


## Closure Summary

修复6个致命缺陷：(B1)删除change.py死代码导入消除导入遮蔽；(B2)删除create_plan重复Risks and Rollback模板段；(B3)config.py用isinstance类型守卫替换bool()/list()/int()强制转换防止静默数据损坏；(B4)read_plan_content加plan_id正则校验+plan_path加路径包含检查堵住路径遍历；(B5)hooks/commit-msg模板化init时动态填充SPEC_VC_BIN消除硬编码路径；(B6)check-refs.sh用索引数组+临时文件替代declare -A兼容Bash 3.2。全部89个测试通过。


## References

- **Commits**: 待从 git 自动采集
- **Plan**: doc/arch/plans/ADR-014-plan-001.md


## Risks and Rollback

待补充

## Checkpoints

- [ ] 澄清完成
- [ ] 前置验证完成
- [ ] 实施完成
- [ ] 后置验证完成
- [ ] ADR 回填完成
