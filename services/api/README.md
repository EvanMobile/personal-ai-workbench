# Personal AI Workbench API

FastAPI 服务当前提供健康检查、Swagger UI，以及第一个客户端 Capture API。Capture 接收并确认客户端提交的知识来源；当前不持久化 Capture，也不执行 Fetch、Parse、Normalize 或后续 Ingestion。

## 环境要求

- Python 3.15.2
- 项目依赖由 `pyproject.toml` 管理

## 本地运行

从仓库根目录执行：

```bash
cd services/api
python3.15 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
uvicorn app.main:app --reload
```

服务默认监听 `http://127.0.0.1:8000`。Swagger UI 位于 `/docs`，健康检查位于 `/health`。

## API

### 提交 Capture

`POST /api/v1/ingestion/captures`（Audience：`CLIENT`）

请求示例：

```json
{
  "input_type": "url",
  "content": "https://x.com/example/status/123",
  "intent": "knowledge_capture",
  "metadata": {
    "platform": "x"
  }
}
```

`input_type` 支持 `url` 和 `text`；`content`、`intent` 为必填非空字符串，`metadata` 为可选对象。成功时返回 HTTP `200 OK`：

```json
{
  "capture_id": "cap_0123456789abcdef0123456789abcdef",
  "status": "received",
  "message": "Capture received successfully"
}
```

`capture_id` 是临时确认标识，不会持久化；它不代表已创建持久化 Capture 或 Ingestion Task。HTTP `200` 仅表示 API 已同步接收并确认客户端提交，不代表数据已持久化或创建了 Ingestion Task，也不代表来源已 Fetch、Parse、Normalize 或进入后续 Ingestion。

## 当前实现边界

- 已实现请求校验、临时确认 ID 生成和接收确认；不会持久化 Capture，也不会创建持久化任务。
- 不执行 Fetch、Parse、Normalize，不触发后续 Ingestion，也不实现 Provider 或异步 Ingestion 任务。
- 数据库、文档创建、Digest、Structure、Link、Publish 和 RAG 等能力尚未实现。
- 尚未接入 X/Twitter 或 FxTwitter，也不支持 PDF、Word、图片上传解析、Embedding、Vector Database、LangGraph 或 Agent Runtime。

## 测试

激活虚拟环境后执行：

```bash
pytest
```

`.env.example` 是无密钥的环境变量模板。目前应用不读取环境变量。
