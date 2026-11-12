# Personal AI Workbench

Personal AI Workbench 是一个由多个独立产品组成的个人 AI 工作台，旨在整合工程经验复现、可复用工程能力与技术知识资产。Workbench 提供统一入口、共享基础设施和跨产品协作基础；三个产品保持平级，拥有各自独立的业务边界和演进空间。

## 项目目标

- 建立 Web、Android 客户端与 Python API 服务的统一工程基础。
- 为 Project Replay、Personal Arsenal 和 Personal Knowledge 建立清晰、独立的产品边界。
- 支持工程经验、工程能力和认知资产的持续积累与演进。
- 逐步完善文档、开发规范与部署方式，保持项目易于维护和扩展。

## 三大产品

- **Project Replay**：历史项目重演与工程经验复现，以真实项目背景和原始工程问题为基础，利用现代技术重新设计和实现，并形成可验证的工程成果。详见 [Project Replay 产品说明](products/project-replay/README.md)。
- **Personal Arsenal**：个人工程武器库，沉淀可复用的代码、脚本、工具、工程方法，以及 Prompt、Agent、Workflow、Tool 等工程能力。详见 [Personal Arsenal 产品说明](products/personal-arsenal/README.md)。
- **Personal Knowledge**：个人技术知识库，接收和保存原始知识来源，并通过 Capture、Digest、Link、Publish 工作流形成可关联、可检索和可维护的知识资产。详见 [Personal Knowledge 产品说明](products/personal-knowledge/README.md)。

三个产品是 Workbench 下的平级业务产品。它们可以通过明确接口和共享能力协作；具体协作流程尚未确定。

## Monorepo 目录结构

以下目录树按当前工作区实际目录整理。标注“空目录”表示目录存在但目前没有文件；此类空目录不会由 Git 单独跟踪。

```text
personal-ai-workbench/
├── apps/
│   ├── web/                    # 空目录；尚无 Web 客户端代码
│   └── android/                # 空目录；尚无 Android 客户端代码
├── products/
│   ├── project-replay/
│   │   └── README.md           # 产品定位与边界
│   ├── personal-arsenal/
│   │   └── README.md           # 产品定位与边界
│   └── personal-knowledge/
│       └── README.md           # 产品定位与边界
├── services/
│   └── api/
│       ├── app/
│       │   ├── api/v1/shared/  # 共享 API 路由预留目录
│       │   ├── core/
│       │   ├── schemas/
│       │   ├── services/
│       │   └── main.py         # FastAPI 入口，含 /health
│       ├── tests/
│       │   └── test_health.py
│       ├── .env.example
│       ├── pyproject.toml      # Python 工程与依赖配置
│       └── README.md           # API 工程运行说明
├── docs/
│   ├── architecture/
│   │   └── overview.md         # Workbench 总体架构
│   └── decisions/              # 空目录；架构决策文档待补充
├── .gitignore
└── README.md
```

- `apps` 是客户端入口，不等同于产品业务模块。当前 Web 和 Android 目录尚无客户端实现。
- `products` 定义业务产品边界，并在各自的 `README.md` 中维护产品说明。
- `services` 承载共享后端能力，不承载所有产品业务逻辑。
- `docs` 维护总体架构、架构决策和工程规范；目前已有总体架构文档，决策文档目录尚为空。

## 技术架构原则

- 三个产品业务平级、边界独立；Workbench 提供统一入口和共享基础设施。
- 产品通过明确接口和共享能力协作，避免隐式耦合；不预设具体调用流程。
- 当前采用 Monorepo 不代表未来必须采用微服务。先建立清晰的模块边界，再根据真实需求决定是否拆分服务。
- 当前架构状态为 **Active Baseline**，通过 **Audit → Decision → Card → Construction** 持续演进。

更多架构说明见 [Workbench 总体架构文档](docs/architecture/overview.md)。架构决策文档尚未建立，待补充。

## 当前建设状态

| 状态 | 当前内容 |
| --- | --- |
| **已建立** | 三个平级产品的定位和边界说明；总体架构基线；FastAPI 工程骨架、依赖配置和基础测试。本地 `.venv` 已建立并由 Git 忽略。 |
| **已实现** | API 提供 `/health` 健康检查和 FastAPI 默认 `/docs` Swagger UI；目前没有产品业务 API。 |
| **规划中** | Web、Android 客户端实现；Personal Knowledge 的 Capture、Digest、Link、Publish 工作流及对应业务接口。 |
| **尚未施工** | Capture API 和其他真实业务接口、数据库连接及产品业务实现。 |

客户端目录已在当前工作区建立，但尚无代码或构建配置，不能视为客户端功能已实现。三个产品 README 描述的是产品定位、目标和能力范围，不代表对应业务能力已经完成。API 工程的安装、启动和测试方式见 [API 服务说明](services/api/README.md)。
