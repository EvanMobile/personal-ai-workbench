# Personal Arsenal

Personal Arsenal 是一个可移植、可独立版本控制的工程资产库，用于保存可复用、可执行、可验证或可作为工程证据的内容，例如代码、脚本、工具、提示词、Agent 技能与工作流、MCP 集成、技术方案和故障排查案例。

它与 **Personal Knowledge** 职责不同。Personal Knowledge 保存知识解释、概念、专业经验和整理后的知识；Personal Arsenal 保存可复用的工程能力及其证据。两者可以相互引用，但不能互相替代。

## Topic

Topic 是资产库的一级主题目录。全局注册入口为 [`CATALOG.yaml`](CATALOG.yaml)，Topic 名称不应硬编码在代码中。每个已初始化的 Topic 都有稳定 ID、README、Manifest，以及共享[Topic 目录契约](schemas/topic-manifest-standard.md)规定且实际需要的目录。

当前和计划中的 Topic 见 [Topic 注册表](CATALOG.yaml)。

## 资产类型

- **Documentation（文档）**：技术说明、架构说明和工程指南。
- **Troubleshooting（故障排查）**：基于证据的调查、根因分析、修复过程和经验总结。
- **Code（代码）**：可复用实现。
- **Scripts（脚本）**：可重复执行的工具与操作。
- **Tests（测试）**：验证代码和测试用例。
- **Examples（示例）**：演示和使用示例。
- **Config（配置）**：不含敏感信息的配置模板。
- **Evidence（证据）**：经过检查和脱敏的真实工程证据。

可长期维护的文档应遵循统一的[资产文档规范](schemas/asset-document-standard.md)。Manifest 只登记已知资产；计划中的资产必须明确标记为 planned，不得让人误以为其内容已经存在。

## 目录约定

已初始化的 Topic 遵循以下外部契约：

```text
topics/<topic-id>/
├── README.md
├── manifest.yaml
├── docs/
├── src/
├── tests/
├── examples/
├── config/
├── scripts/
├── evidence/
├── history.yaml
└── requirements.txt   # 仅当该 Topic 实际使用 Python 依赖时创建
```

不需要的目录可以暂不创建。不要为了让 Git 显示空目录而添加占位文件。Topic 内部结构可随实际需求扩展，但顶层目录职责保持一致。

## 新增 Topic

1. 由 Owner 确认 Topic。
2. 在 `CATALOG.yaml` 注册稳定 ID、名称、路径、状态、资产类型和简短描述。
3. 按共享目录契约创建 `topics/<topic-id>/`；不要为尚未初始化的 planned Topic 创建空目录。
4. 添加 Topic README 和 Manifest，只创建实际需要的目录，并在 `history.yaml` 记录初始化事件。
5. 通过注册表将 Topic 纳入本入口索引；无需重构其他 Topic。

共享的 [Topic Manifest 规范](schemas/topic-manifest-standard.md)和[资产文档规范](schemas/asset-document-standard.md)定义了最低元数据与文档结构要求。

## 资产生命周期

资产状态可使用 `draft`、`active`、`deprecated` 或 `archived`。在 Topic 历史中记录可理解的生命周期变化。这是一份轻量记录，不是审批系统。确有归档原因时，可将废弃或迁移的资产放在对应 Topic 或 `archive/` 中；不要虚构历史记录。

## 安全

不得保存 API Key、Webhook URL、Secret、代理凭据、含凭据日志、未脱敏截图或 `.env` 文件。配置示例使用占位符。添加证据前，检查其中是否含凭据、个人信息或系统敏感信息。

## 仓库布局

- `topics/`：已注册并初始化的 Topic 资产。
- `shared/`：确实由多个 Topic 共用的资产。
- `schemas/`：共享元数据与文档规范。
- `archive/`：有明确归档原因的废弃或迁移资产。

该资产库可移植，并可独立于 PAW 应用进行版本管理。在本 Monorepo 中，它位于仓库根目录，与作为产品定义保留的 `products/personal-arsenal/` 分开。
