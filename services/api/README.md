# Personal AI Workbench API

最小 FastAPI 服务工程，当前提供健康检查接口和 Swagger UI，供后续真实 API 开发使用。

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

## 测试

激活虚拟环境后执行：

```bash
pytest
```

`.env.example` 是无密钥的环境变量模板。目前应用不读取环境变量。
