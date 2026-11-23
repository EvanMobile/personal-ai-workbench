# Topic Manifest 与目录规范

## 用途

本规范定义 Personal Arsenal Topic 的最小可移植契约。全局 `CATALOG.yaml` 用于注册 Topic；每个已初始化 Topic 的 `manifest.yaml` 描述该主题及其实际资产。

## Topic 目录契约

已初始化的 Topic 使用以下结构：

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
└── requirements.txt   # 仅当实际使用 Python 依赖时创建
```

各 Topic 的顶层目录职责保持稳定。只创建有实际用途的目录；空目录无需占位文件。Topic 内部结构和技术选型可以不同。不要为注册表中仅处于计划状态的 Topic 创建完整目录。

## Manifest 结构

使用以下最小 YAML 结构，仅在有实际需要时增加字段：

```yaml
schema_version: "1.0"

topic:
  id: <稳定的-kebab-case-ID>
  name: <展示名称>
  description: <简短用途说明>
  status: active # active、planned、deprecated、archived

metadata:
  created_at: "YYYY-MM-DD"
  updated_at: "YYYY-MM-DD"
  owner: user

capabilities: []
asset_types: []

runtime:
  languages: []
  dependencies: []

assets: []
```

`assets` 只包含已知资产。每项至少包含 `asset_id`、`name`、`type`、`path`、`description`、`status` 和 `created_at`。路径使用 Topic 内相对路径。资产状态使用 `draft`、`active`、`deprecated` 或 `archived`。不得声称存在尚未添加或验证的代码、依赖、测试或运行环境支持。

全局注册表是 Topic 的统一注册入口，应记录 Topic ID、名称、路径、状态、资产类型和简短描述。已初始化 Topic 的注册表状态应与其 Manifest 状态一致。planned Topic 在 Owner 批准初始化前只出现在注册表中。

## 历史记录

`history.yaml` 记录有意义的 Topic 初始化和资产演进。文件以 schema 版本和 `entries` 列表开始。只记录有仓库证据支持的事件；不要还原或编造先前历史。

```yaml
schema_version: "1.0"
entries:
  - date: "YYYY-MM-DD"
    type: initialized
    summary: <经验证的事件>
```

## 安全与可移植性

Manifest 仅保存元数据，不保存凭据。不得存放 API Key、Webhook URL、Secret、代理凭据、`.env` 文件或未脱敏证据。配置示例使用占位符。路径使用相对路径；除非资产明确记录本地专用要求，否则避免使用机器专属绝对路径。
