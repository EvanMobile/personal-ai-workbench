# Personal AI Workbench API

FastAPI 服务 + PostgreSQL，承载 P1.M1 的 Capture、Digest、Draft、Publish、Dossier、Page，
以及跨业务共享的 Visual Artifact Service。

## 环境要求

- Python 3.15.2（`pyproject.toml` 约束 `>=3.15,<3.16`）
- PostgreSQL 17（本地 Homebrew 安装）
- 依赖：FastAPI、Pydantic、SQLAlchemy 2.x、Alembic、psycopg 3、Pillow

## 本地运行

从仓库根目录推荐使用统一脚本：

```bash
./scripts/workbench.sh start     # 启动 PostgreSQL / API / Web
./scripts/workbench.sh status
./scripts/workbench.sh stop      # 停止 API 与 Web（PostgreSQL 保留）
./scripts/workbench.sh stop --all
```

手动运行：

```bash
cd services/api
python3.15 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env             # 按需修改 DATABASE_URL
alembic upgrade head
uvicorn app.main:app --reload
```

默认监听 `http://127.0.0.1:8000`。Swagger UI：`/docs`；健康检查：`/health`、`/health/ready`。

## 配置

`services/api/.env` 被 Git 忽略，参考 `.env.example`：

| 变量 | 说明 |
|---|---|
| `DATABASE_URL` | PostgreSQL 连接串，默认 `postgresql+psycopg://127.0.0.1:5432/workbench` |
| `LLM_PROVIDER` | `mock`（默认）或 `openai`；真实 Provider 默认禁止 |
| `LLM_MODEL` | 模型标识；Mock 默认 `mock-digest-v1`，不在业务代码硬编码 |
| `ALLOW_REAL_LLM` | 默认 `false`；首次真实调用须 Owner 授权 |
| `WORKBENCH_DATA_DIR` | 上传文件与生成图片目录，默认 `.data` |
| `MAX_UPLOAD_BYTES` | 上传大小上限，默认 2 MB |

## 主要 API

### Capture

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/ingestion/captures` | 文本或 URL；持久化 Raw Content，不触发 Digest |
| POST | `/api/v1/ingestion/captures/files` | 上传 UTF-8 文本类文件（txt/md/csv/json/log/yaml/yml） |
| GET | `/api/v1/ingestion/captures/{id}` | Capture 记录 |
| GET | `/api/v1/ingestion/raw-contents` | Raw Content 列表 |

URL 输入只保存原值并标记 `needs_fetch`，P1.M1 不抓取外部网页。

### Knowledge

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/knowledge/raw-contents/{id}/digest` | 生成 Card Draft（默认 Mock Provider） |
| GET | `/api/v1/knowledge/drafts` `/drafts/{id}` | 查看 Draft |
| POST | `/api/v1/knowledge/drafts/{id}/revisions` | 人工触发修订，不自动发布 |
| POST | `/api/v1/knowledge/drafts/{id}/publish` | **人工确认发布**，生成 Asset 与 Artifact |
| GET | `/api/v1/knowledge/assets` `/assets/{id}` | 已发布 Card |
| PATCH | `/api/v1/knowledge/assets/{id}` | 分类、标签、归档、归入 Dossier |
| GET | `/api/v1/knowledge/stats` | 计数 |

### 来源追溯（Provider provenance）

Draft、Knowledge Asset、Draft Revision 与 Artifact 均返回以下字段：

| 字段 | 说明 |
|---|---|
| `provider` | 实际执行方：`mock` / `openai` / `unknown` |
| `model` | 具体模型标识；Mock 固定为 `mock-digest-v1`，不受 `LLM_MODEL` 影响 |
| `prompt_version` | Prompt 版本 |
| `processing_mode` | `rule_based` / `llm` / `unknown` |
| `is_mock` | `true` = 规则模拟；`false` = 真实 Provider；`null` = 历史来源未知 |

Mock 的 `Accuracy` 固定说明"未执行语义分析或外部事实核验"；Artifact 图片带 `MOCK` 徽标。
历史记录无法判断来源时保留 `unknown` / `null`，不会标记为真实 LLM。

### Dossier / Page

`/api/v1/knowledge/dossiers`（列表、创建、详情、加/移 Card），
`/api/v1/knowledge/pages`（列表、从 Dossier 生成、详情、重新生成版本）。

### Visual Artifact

`/api/v1/artifacts`、`/{id}`、`/{id}/regenerate`、`/{id}/validate`、`/{id}/file`（PNG）。
Artifact 不是知识资产本身；生成失败不会使 Publish 失败，也不会返回 ready。

### Chat

`/api/v1/chat/conversations`、`/messages`、`/suggestions`。P1.M1 助手回复由本地规则生成，
不调用外部模型。

## 数据库迁移

```bash
alembic upgrade head          # 应用迁移
alembic current               # 当前版本
alembic revision --autogenerate -m "message"
```

所有 Schema 变更必须由 Alembic 管理；不要手工建表。

## 测试

```bash
cd services/api
.venv/bin/pytest -q
```

测试使用独立 PostgreSQL 数据库 `workbench_test`，通过 Alembic 建库；不使用 SQLite 替身，
不调用真实外部 Provider。

## 当前实现边界

- 只支持文本类文件；PDF/Word/图片/视频未实现。
- URL 不抓取。
- LLM 使用确定性 Mock；真实 Provider 受双重开关保护且尚未实现调用。
- 无 Redis、无独立向量数据库、无 pgvector 实现、无 RBAC。
