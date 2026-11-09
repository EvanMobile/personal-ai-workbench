# Personal AI Workbench

Personal AI Workbench 是一个由多个独立产品组成的个人 AI 工作台，旨在整合工程经验复现、可复用工程能力与技术知识资产。Workbench 提供统一入口、共享基础设施和跨产品协作基础；三个产品保持平级，拥有各自独立的业务边界和演进空间。

## 项目目标

- 建立 Web、Android 客户端与 Python API 服务的统一工程基础。
- 为 Project Replay、Personal Arsenal 和 Personal Knowledge 建立清晰、独立的产品边界。
- 支持工程经验、工程能力和认知资产的持续积累与演进。
- 逐步完善文档、开发规范与部署方式，保持项目易于维护和扩展。

## 三大产品

- **Project Replay**：历史项目重演与工程经验复现，以真实项目背景和原始工程问题为基础，利用现代技术重新设计和实现，并形成可验证的工程成果。
- **Personal Arsenal**：个人工程武器库，沉淀可复用的代码、脚本、工具、工程方法，以及 Prompt、Agent、Workflow、Tool 等工程能力。
- **Personal Knowledge**：个人技术知识库，接收和保存原始知识来源，并通过 Capture、Digest、Link、Publish 工作流形成可关联、可检索和可维护的知识资产。

三个产品是 Workbench 下的平级业务产品。它们可以通过明确接口和共享能力协作；具体协作流程尚未确定。

## Monorepo 目录结构

```text
personal-ai-workbench/
├── apps/
│   ├── web/                    # Web 客户端入口
│   └── android/                # Android 客户端入口
├── products/
│   ├── project-replay/         # 产品定义与实现
│   ├── personal-arsenal/       # 产品定义与实现
│   └── personal-knowledge/     # 产品定义与实现
├── services/
│   └── api/                    # 共享后端能力
├── docs/
│   ├── architecture/           # 总体架构说明
│   └── decisions/              # 架构决策文档
├── .gitignore
└── README.md
```

`apps` 是客户端入口，不等同于产品业务模块；`products` 定义业务产品边界，并在各自目录的 `README.md` 中维护产品说明；`services` 承载共享后端能力，不承载所有产品业务逻辑。更详细的说明见 [Workbench 总体架构](docs/architecture/overview.md) 和 [各产品目录](products/)。

## 技术架构原则

- 三个产品业务平级、边界独立；Workbench 提供统一入口和共享基础设施。
- 产品通过明确接口和共享能力协作，避免隐式耦合；不预设具体调用流程。
- 当前采用 Monorepo 不代表未来必须采用微服务。先建立清晰的模块边界，再根据真实需求决定是否拆分服务。
- 当前架构状态为 **Active Baseline**，通过 **Audit → Decision → Card → Construction** 持续演进。

## 当前建设阶段

当前处于工程骨架与总体架构定义阶段：已建立 Web、Android、API 服务和文档的基础目录布局，已建立三大产品的定义和 Workbench 架构基线。尚未引入应用框架、依赖或业务实现。
