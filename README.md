# Personal AI Workbench

Personal AI Workbench 是一个由多个独立产品组成的个人 AI 工作台，聚焦工程经验复现、可复用工程能力与技术知识资产。Workbench 提供统一入口、共享基础设施和跨产品协作基础；三个产品保持平级，拥有各自独立的业务边界和演进空间。

## 项目目标

- 建立 Web、Android 客户端与 Python API 服务的统一工程基础。
- 为 Project Replay、Personal Arsenal 和 Personal Knowledge 建立清晰、独立的产品边界。
- 支持工程经验、工程能力和认知资产的持续积累与演进。
- 逐步完善文档、开发规范与部署方式，保持项目易于维护和扩展。

## 三大产品

- **Project Replay**：以真实历史项目和原始工程问题为基础，使用现代技术重新设计和实现，形成可审查、可运行、可验证的工程成果。详见 [产品说明](products/project-replay/README.md)。
- **Personal Arsenal**：沉淀和复用代码、脚本、工具、工程方法，以及 Prompt、Agent、Workflow、Tool 等工程能力。详见 [产品说明](products/personal-arsenal/README.md)。
- **Personal Knowledge**：接收原始知识来源，并以 Capture、Digest、Link、Publish 为内容处理方向，形成可关联、可检索、可维护的知识资产。详见 [产品说明](products/personal-knowledge/README.md)。

三个产品是 Workbench 下的平级业务产品，可以通过明确接口和共享能力协作；具体协作流程尚未确定。

## Monorepo 结构与当前状态

```text
personal-ai-workbench/
├── apps/
│   ├── web/                              # 空目录，尚无客户端实现
│   └── android/                          # 空目录，尚无客户端实现
├── products/
│   ├── project-replay/README.md
│   ├── personal-arsenal/README.md
│   └── personal-knowledge/README.md
├── services/api/
│   ├── app/api/v1/client/ingestion/captures.py
│   ├── app/api/v1/shared/                # 共享路由预留目录
│   ├── app/schemas/capture.py
│   ├── app/services/capture_service.py
│   ├── app/main.py
│   ├── tests/test_capture.py
│   ├── tests/test_health.py
│   ├── pyproject.toml
│   └── README.md
├── docs/
│   ├── architecture/overview.md
│   └── decisions/                        # 当前为空，决策文档待补充
├── PROJECT_CONTEXT.md
├── .gitignore
└── README.md
```

- `apps/` 是 Web 和 Android 客户端入口，不等同于产品业务模块；当前目录尚无客户端代码或构建配置。
- `products/` 定义三个产品各自的业务边界，并在各自 README 中维护产品说明。
- `services/` 承载共享后端能力，不承载所有产品业务逻辑。
- `docs/` 保存总体架构与专项设计。目前已有 [总体架构文档](docs/architecture/overview.md)，`docs/decisions/` 尚无决策文档。
- `services/api/` 已建立 FastAPI 工程、健康检查、Swagger UI 和第一个 CLIENT Capture API。Capture 通过 `POST /api/v1/ingestion/captures` 同步返回 HTTP 200 与临时确认 ID；当前不持久化 Capture，也不执行 Fetch、Parse、Normalize 或后续 Ingestion。运行方式和接口示例见 [API README](services/api/README.md)。

目录存在不代表功能已实现。当前尚未施工的能力包括客户端实现、Capture 持久化、数据库接入、异步 Ingestion、Document 创建及后续知识处理。

## 架构原则

- 三个产品业务平级、边界独立；Workbench 提供统一入口与共享基础设施。
- 产品通过明确接口和共享能力协作，避免隐式耦合；不预设尚未确认的调用流程。
- 当前采用 Monorepo 不代表未来必须采用微服务；是否拆分服务应由实际需求驱动。
- 当前架构状态为 **Active Baseline**，通过 **Audit → Decision → Card → Construction** 持续演进。

## PROJECT_CONTEXT.md：工程上下文主存档

[PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) 是整个 Workbench 唯一的项目级综合工程上下文主存档（Engineering Context Source of Truth）。它不是普通项目介绍，也不重复 README 的公开入口职责。

本项目会跨不同开发会话、模型和 Coding Agent 协作，也可能经历长时间中断和跨产品、跨模块施工。聊天记录、单次任务 Prompt 和 Git Commit 各自只能保存局部信息，难以持续保留设计意图、决策依据、当前状态与未决事项。主存档把这些上下文作为项目资产维护，减少信息丢失、重复分析、错误假设和架构偏移。

主存档覆盖整个 Workbench，包括所有产品、Web/Android 客户端、Python API 服务、共享基础设施及跨产品工程活动，记录：

- 项目背景、愿景和阶段目标；
- 已实现架构、规划架构、模块职责与架构不变量；
- 技术栈、选择依据及决策状态；
- 有证据支持的工程历史、当前项目状态和施工位置；
- 遗留问题、技术债务、待验证假设与后续行动；
- Agent 施工契约、变更审查和工程交接规范。

主存档使用 `CONFIRMED`、`DECIDED`、`PENDING`、`PROPOSED`、`DEPRECATED` 区分代码事实、设计决策、候选方案和未决事项。建议、推测或历史报告不会被写成已验证事实；信息冲突应并列记录并请求核实。

### Agent 如何使用和维护

所有 AI Coding Agent（包括 Codex、Gemini 及其他工具）在施工前必须读取当前版本的 `PROJECT_CONTEXT.md`，再检查实际代码、Git 状态和相关文档。Agent 必须在授权范围内工作，遵守已有架构与依赖约束；发现存档与代码不一致、设计冲突或需求歧义时，应报告而非自行裁决。重要工程状态变化后，按授权及时更新主存档。

交付时应提供修改摘要、文件清单、关键位置、测试/验证证据、未完成事项、架构偏差和下一步。Commit/Push 仅在任务明确授权后执行。

### 与其他项目资料的关系

| 资料 | 职责 |
| --- | --- |
| `README.md` | 项目公开入口、整体介绍和导航。 |
| `PROJECT_CONTEXT.md` | 项目级完整工程上下文与 Agent 协作依据。 |
| `docs/` | 总体架构、技术设计和专项工程文档。 |
| `products/*/README.md` | 各产品自身的定位、业务边界和产品说明。 |
| Git | 保存代码与文档的完整变更历史、Commit 和 Diff。 |

主存档可记录重要变更的背景、目的、结果和 Commit 索引，但不替代 Git 版本管理。专项文档与主存档冲突时，Agent 不得假设任一方已废弃，应标明冲突并提交审查。

## AI Agent 协作规范

本项目采用多智能体协作，以保持跨会话、跨模型和跨 Agent 的工程连续性。**Project Owner** 拥有最终决策、授权和验收权；**Chief Architect（ChatGPT）** 负责架构指导、上下文治理、任务设计和 Review；**Implementation Agents（Codex、Gemini 等）** 只在授权范围内实施。Review 提供审查意见，不代替 Owner 批准。

所有 Agent 必须先阅读 `PROJECT_CONTEXT.md`，检查真实代码与工作区；不得擅自扩大范围、改变已确认架构或增加依赖。交付必须可审查、可验证、可回滚，并提供测试证据。发现冲突应暂停并报告；Commit/Push 遵守明确授权和变更隔离要求。完整契约见 [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md)。

#### 14 条工程治理规则

1. **项目背景**：理解 Workbench 的目标、问题和三个平级产品边界。
2. **项目愿景与目标**：区分当前阶段与长期方向，不把目标当成已交付。
3. **架构上下文**：了解已实现和规划中的架构、职责与数据流。
4. **架构不变量**：不得擅自改变产品关系、模块边界或未定流程。
5. **技术栈与选型**：区分已采用、已决定和候选技术；依赖变更须授权。
6. **工程推进历史**：依据证据记录施工、验证、偏差和遗留，不补造历史。
7. **当前项目状态**：准确区分已完成、进行中和未开始事项。
8. **当前施工位置**：交接阶段、最近完成点、当前任务和下一动作。
9. **遗留问题与技术债务**：记录风险、冲突、假设及待确认事项。
10. **重要架构决策**：记录依据、影响与状态，并区分候选方案。
11. **Agent 施工契约**：先读上下文，只改授权范围，核验代码、提供测试证据；未经授权不提交或推送。
12. **变更与审查协议**：架构问题先说明原因和方案；Review 不取代 Owner 决策。
13. **工程交接协议**：报告目标、修改文件、代码位置、验证、未完成项和下一步。
14. **下一步行动**：按真实状态规划，未经授权不提前施工。

### Minimum Sufficient Review（CR Policy）

审查深度与变更风险匹配，默认采用 L1；依据实际风险升级。避免无目的全仓扫描、默认输出完整 Diff 或重复可靠验证。

- **L1 — Lightweight Review**：用于文档、README 和低风险配置。检查文件清单、Diff 摘要、政策符合性、重要内容准确性及明显遗漏/不一致。
- **L2 — Targeted Code Review**：用于 API、Service、Schema、业务逻辑和数据库变更。检查相关代码与上下游、架构边界、异常/边缘情况及相关测试；默认只运行相关测试。
- **L3 — Deep Architecture Review**：用于核心架构、依赖体系、跨模块和安全敏感变更。检查调用链/数据流、边界与依赖影响、架构一致性、安全稳定性及回归风险；按具体风险扩展范围。

完整 Review Policy 和治理细则以 [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) 为准。
