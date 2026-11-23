# DingTalk 主题

本主题用于沉淀可复用的 DingTalk 工程资产，包括自定义机器人 Webhook 集成、FastAPI 消息发送、HTTP 客户端、TLS / 证书信任、DNS / 代理诊断，以及基于证据的故障排查案例。

## 资产索引

| 资产 | 类型 | 状态 | 路径 |
|---|---|---|---|
| 本机 Python HTTPS/TLS 诊断 | 故障排查 | active | [`docs/01-local-python-https-tls-diagnosis.md`](docs/01-local-python-https-tls-diagnosis.md) |

该案例记录本机 Python 访问 DingTalk HTTPS 服务时的 TLS 信任排查和修复。内容依据工程诊断记录与 Owner 对真实送达的确认整理，并遵循共享的[资产文档规范](../../schemas/asset-document-standard.md)。

## 目录说明

- `docs/`：技术文档和故障排查案例。
- `src/`：可复用实现。
- `tests/`：验证代码和测试用例。
- `examples/`：有实际示例时存放可运行示例。
- `config/`：不含敏感信息的配置模板。
- `scripts/`：可重复执行的工具。
- `evidence/`：仅存放经过检查和脱敏的工程证据。

本主题不得存放凭据、Webhook URL、Secret、代理凭据或未脱敏日志。
