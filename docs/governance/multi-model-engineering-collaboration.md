# 多模型工程协作约定

## 目的与原则

多模型协作是提升工程生产力的手段，不是 Personal AI Workbench 的产品目标。按需委派，不要求每项任务都由多个模型重复处理。职责清晰，避免重复分析、重复施工和无效上下文传递。

关键架构决策、产品范围和优先级由 Project Owner 掌握。所有模型均须遵循 [Frozen Engineering Scope v1.0](frozen-engineering-scope-v1.0.md) 和 [Human-Owned Engineering](human-owned-engineering.md)。模型建议不构成 Owner 批准。

## 工程协作约束

- **唯一最终决策方**：Project Owner 是项目唯一最终决策方，拥有范围、架构、优先级和验收的最终决定权。
- **授权范围内执行**：Agent 只能在明确授权的任务范围内执行；授权范围之外的工作须先取得 Owner 授权。
- **输出不代替批准**：Agent 的建议、分析、Task Brief、Review 结论和实施结果，均不能代替 Owner 批准。
- **冲突即暂停**：发现任务范围、架构或授权冲突时，暂停受影响的工作并向 Owner 汇报，不自行裁定或继续推进。
- **交付须区分信息性质**：交付报告必须区分实际事实、建议、待决事项、实施结果和测试证据。

## 角色与职责

### ChatGPT — Architecture & Project Coordination

- 讨论产品方向、整体架构和工程规划。
- 讨论技术方案，拆解任务，并为关键决策提供建议。
- 解释技术原理并引导学习。
- Review 施工结果，把关工程质量；Review 不代替 Project Owner 验收。
- 作为技术顾问，负责分析、架构建议、任务规划和技术 Review；不拥有独立的 Owner 授权权力。

### Codex — Primary Engineering Execution

- 检查仓库、实施代码与文档施工，并运行授权范围内的测试。
- 按明确的 Task Brief 执行任务，不擅自扩大范围。
- 提供施工报告、变更文件清单、测试结果和必要的技术说明。
- 未经明确授权不得 Commit 或 Push。
- Codex、DSH 等 Implementation Agent 可在授权范围内自主分析、编码、测试和处理普通实现细节。

### Independent Model — On-demand Specialist

- 独立评估复杂架构方案，诊断疑难问题，交叉审查关键技术方案。
- 必要时对现有方案提出反证、风险和替代意见。
- 按需参与，不作为常规任务的默认参与者；独立意见用于辅助判断，不直接覆盖主方案。

### Project Owner — Final Authority

- 拥有产品目标、范围、优先级和架构决策的最终决定权。
- 决定是否委派 Independent Model。
- 负责关键工程判断、个人 Knowledge Mastery 和最终验收。
- 掌握 Commit / Push 与范围变更的授权权。

## Independent Model 委派条件

**可考虑委派：**

- 涉及多个模块的复杂架构决策。
- 技术方案有重大不确定性或明显争议。
- 常规分析仍无法定位的疑难 Bug。
- 需要独立视角验证的关键技术设计。

**通常不需要委派：**

- README 或普通文档修改。
- 简单 API、业务逻辑实现或常规测试补充。
- 已有明确技术方案的重复性施工。

## 协作与交接

- 委派 Brief 应说明问题、背景、范围和期望输出。
- 委派模型基于收到的材料独立判断，提供分析意见，不直接覆盖主方案或修改授权范围外的内容。
- 模型意见冲突时，整理其差异、证据和取舍，交由 Project Owner 决策。
- 重要结论应回收到项目文档、ADR 或对应 Task 记录，避免只留在聊天历史。
- 只传递完成当前任务所需的信息，不要求所有模型共享完整上下文。
- 模型不得扩大产品范围或改变已批准的架构决策。

## 额度与资源

- 普通任务优先使用经济型模型；复杂推理和高风险技术决策可使用高能力模型。
- 只有在独立验证有明确价值时才调用 Independent Model，避免无意义的多模型重复审查。
- 额度是工程资源，应按实际价值使用，不以消耗额度为目标。

## 与现有治理规则的关系

本文档补充多模型协作约定，不取代 Frozen Engineering Scope v1.0 或 Human-Owned Engineering；不改变既有 Minimum Sufficient Review L1/L2/L3 和 Knowledge Mastery L1-L4 规则；不改变 Project Owner 的最终决策权。
