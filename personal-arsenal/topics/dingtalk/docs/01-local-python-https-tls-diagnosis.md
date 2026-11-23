# PAW DingTalk：本地 Python HTTPS / TLS 故障排查与修复

## 1. 资产元信息

| 字段 | 内容 |
|---|---|
| Asset ID | DINGTALK-001 |
| 名称 | 本地 Python HTTPS / TLS 故障排查与修复 |
| Topic | DingTalk |
| 类型 | Troubleshooting / Engineering Case |
| 状态 | active |
| 创建日期 | 2026-11-24 |
| 关联项目 | Personal AI Workbench |
| 关联技术 | FastAPI、Python、OpenSSL、TLS、CA、Clash Verge、Webhook |

**资产定位：**

记录 PAW 首次接入钉钉自定义机器人时，从功能实现、API 运行环境、网络出口、DNS、TLS 证书信任到真实消息送达的完整故障排查过程。

本案例重点沉淀本地 Python 服务访问外部 HTTPS 服务时的诊断方法、根因判断、最小修复策略和验收方法。

---

## 2. 案例概述

### 2.1 项目背景

Personal AI Workbench（以下简称 PAW）需要验证一条外部消息发送链路。

用户希望能够在 PAW 最右侧的 FE 功能区域输入测试消息，并通过本机 FastAPI 将消息发送到自己的钉钉群。

最终采用钉钉群自定义机器人作为接收端。

整体链路：

```text
PAW FE
   |
   v
Local FastAPI
   |
   v
DingTalk Service
   |
   v
HTTPS Webhook
   |
   v
DingTalk Custom Robot
   |
   v
Personal AI Workbench Group
```

PAW 当前采用本地优先架构：

| 模块 | 技术与运行方式 |
|---|---|
| FE | React / TypeScript / Vite，本机运行 |
| API | Python / FastAPI / Uvicorn，本机运行 |
| Database | PostgreSQL 17，本机运行 |
| External Service | DingTalk Custom Robot |
| Network | Clash Verge |
| Runtime | macOS |

PAW 没有公网 API，也没有部署到云端。

本次需要的只是本机 API 主动访问公网钉钉服务的能力。

### 2.2 最终结果

本次故障排查最终完成了：

- PAW FE 到本地 FastAPI 的请求链路。
- FastAPI 到独立 DingTalk Service 的调用。
- Python 对钉钉公共 HTTPS 主机的正常访问。
- Python TLS 证书链验证。
- TLS 主机名验证。
- 钉钉 Webhook 真实消息发送。
- 用户在钉钉群中确认实际收到消息。

最终定位的主要根因：

**PAW API 使用的 Python 3.15 虚拟环境没有可用的默认 CA 信任集合，导致 HTTPS 证书验证失败。**

最终修复方式：

在 API 进程启动环境中设置：

```bash
SSL_CERT_FILE=/etc/ssl/cert.pem
```

没有关闭 TLS 验证，没有新增 Python 依赖，没有修改 Clash，也没有改变 PAW 本地部署架构。

---

## 3. 故障排查时间线

整个过程分为四个阶段。

| 阶段 | 目标 | 结果 |
|---|---|---|
| Phase 1 | 功能实现与 Mock 测试 | 完成 |
| Phase 2 | 真实环境与网络诊断 | 发现 TLS 信任问题 |
| Phase 2.1 | CA / DNS / Proxy 深入评估 | 根因基本确认 |
| Phase 3 | Python CA 信任配置修复 | 验证通过 |
| Phase 4 | 真实消息发送 | 用户确认送达 |

### 3.1 Phase 1：功能实现

首先完成独立的钉钉发送链路。

FE 侧：

- 在 ChatPanel 中增加独立钉钉测试区域。
- 默认消息为“钉钉测试”。
- 支持编辑消息。
- 空白内容校验。
- 发送中禁用重复操作。
- 成功与失败反馈。
- 支持中英文 i18n。

API 侧新增：

```text
POST /api/v1/integrations/dingtalk/messages
```

调用链路：

```text
FE ChatPanel
    |
    v
DingTalk API Router
    |
    v
DingTalk Service
    |
    v
HTTPS Webhook Request
```

关键设计：

1. 不将钉钉消息发送逻辑混入普通 Chat Service。
2. Webhook URL 由服务端环境变量提供。
3. FE 不接触真实 Webhook 凭据。
4. 强制检查消息包含自定义关键词“钉钉测试”。
5. 发送超时或结果未知时不自动重试。
6. 异常信息不泄露 Webhook URL 或钉钉原始错误正文。
7. 保持 HTTPS 证书验证。

Mock 测试共 10 项，通过。

FE i18n 检查、FE Build、Python Compileall 等检查通过。

但是：

**Mock 测试通过只证明代码逻辑符合预期，不代表真实网络请求已经成功。**

### 3.2 第一次真实发送：API 返回 Not Found

用户配置好本地 Webhook 环境变量后，通过 FE 进行第一次真实发送。

结果：

```text
Not Found
```

进一步检查发现：

运行中的 API 进程没有加载新增加的钉钉路由。

因此，问题并不在钉钉服务器或 Webhook，而是当前运行进程与最新代码之间存在状态差异。

处理方式：

- 检查 API 进程。
- 确认新增路由在代码中存在。
- 确认运行中的 OpenAPI 尚未注册该路由。
- 在 Owner 授权后，仅重启 API。

重启时没有调用可能触发数据库准备和迁移的完整 Workbench 启动流程。

重新启动后：

- API 路由已经注册。
- `/openapi.json` 能看到新增 POST 路由。
- API Health 与 Readiness 正常。
- FE 保持运行。
- PostgreSQL 保持运行。

### 3.3 第二次真实发送：API 返回 502

第二次发送只执行一次。

结果：

```text
Could not connect to DingTalk
```

钉钉群没有收到消息。

API 日志出现：

```text
SSLCertVerificationError
```

此时问题已经从 API 路由层转移到外部 HTTPS 请求阶段。

需要重点检查：

- Python HTTP 客户端。
- Python SSL 环境。
- CA 信任来源。
- DNS 解析。
- 代理路径。
- TLS 证书验证。

没有进行自动重试，避免出现未知结果下的重复消息。

### 3.4 Phase 2：区分应用问题与网络问题

当时观察到一个关键现象：

同一台 Mac 上，curl 可以正常访问钉钉公共 HTTPS 主机，而 Python 请求失败。

这说明不能简单地认为：

```text
curl 请求成功
    =
Python 请求一定成功
```

不同客户端可能使用不同的 TLS 实现、证书信任来源、代理配置和 DNS 解析路径。

因此，第一轮只读诊断要求检查：

1. API 实际使用的 Python 解释器。
2. Python 版本和 OpenSSL 版本。
3. Python 默认 CA 文件与目录。
4. Python CA Store。
5. API 进程环境变量。
6. curl 使用的 TLS 后端。
7. curl 使用的 CA 来源。
8. Clash Verge 的运行状态和代理模式。
9. Python 与 curl 的 DNS / Proxy 行为。

### 3.5 第一轮诊断结果

API 使用：

```text
services/api/.venv/bin/python
```

基础解释器：

```text
Python 3.15.2
```

OpenSSL：

```text
OpenSSL 3.5.9
```

检查结果：

| 项目 | Python | curl |
|---|---|---|
| TLS 实现 | OpenSSL | Apple SecureTransport |
| 默认 CA 文件 | 空 | 报告 `/etc/ssl/cert.pem` |
| 默认 CA 目录 | 空 | 系统信任机制 |
| CA Store | 0 个 CA | 证书验证成功 |
| HTTPS | 证书验证失败 | HTTP 200 |

这一结果让排查重点进一步集中到 Python CA 信任来源。

同时，Clash Verge 正在运行：

- System Proxy 已启用。
- Rule Mode。
- Mihomo 正在运行。

当时还观察到 Python 和 curl 的 DNS 行为存在差异。

因此，不能立即排除代理和 DNS 路径的影响。

### 3.6 Phase 2.1：深入检查 CA 与 DNS

第二轮只读诊断进一步寻找现有可信 CA 来源。

发现两个可用文件：

| CA 来源 | 证书数量 | Python 实测 |
|---|---:|---|
| `/etc/ssl/cert.pem` | 128 | 验证成功 |
| pip vendored certifi | 120 | 验证成功 |
| Python 默认 CA Store | 0 | 验证失败 |

关键实验：

使用 PAW API 实际运行的 Python 环境，显式加载：

```text
/etc/ssl/cert.pem
```

然后访问钉钉公共 HTTPS 主机。

结果：

- DNS 解析成功。
- HTTPS 建立成功。
- HTTP 200。
- 证书验证成功。
- 主机名验证成功。

同时保持：

```text
CERT_REQUIRED
Hostname Checking = Enabled
```

使用默认 SSL Context 时，证书验证失败，错误指向无法获取本地 issuer。

这确认了：

**Python 默认 CA 信任源缺失，是此前 TLS 验证失败的直接原因。**

为什么没有选择 pip vendored certifi？

虽然它也能正常验证目标主机，但它位于 pip 内部 vendor 路径，直接依赖该内部实现容易受到 pip 版本和内部组织方式变化的影响。

因此优先选择已经存在、可读取、并且由实际 API Python 验证通过的系统 CA Bundle。

### 3.7 DNS 与 Clash 的调查结论

第一轮受限执行环境中：

- Python 无法解析 `oapi.dingtalk.com`。
- curl 解析到了 `198.18.1.19`。

`198.18.0.0/15` 属于保留地址段，常见于 Fake-IP DNS 机制。

这提示需要关注 Clash 的 DNS 行为。

但第二轮进一步发现：

- 在可用的外层执行环境中，Python 与 curl 均能解析到 `198.18.1.19`。
- 两者都能完成正常 HTTPS 请求。
- API Python 的 urllib 代理映射为空。
- API 进程常见代理环境变量未设置。
- Clash 原始 DNS 配置无法读取。
- 无法直接确认实际命中的 Clash 规则。

最终判断：

DNS 和代理路径的调查结果不足以证明 API 运行时存在独立 DNS 故障。

因此没有修改：

- Clash Verge 配置。
- macOS DNS。
- 系统代理。
- TUN 模式。
- 代理绕行规则。

这是一次重要的工程取舍：

**已经通过实验确认的 CA 问题优先修复，尚未证实的 DNS / Proxy 假设不扩大施工范围。**

---

## 4. Phase 3：CA 信任配置修复

### 4.1 修复决策

最终决定使用：

```text
/etc/ssl/cert.pem
```

作为 PAW API 进程的 CA Bundle。

配置：

```bash
SSL_CERT_FILE=/etc/ssl/cert.pem
```

选择依据：

- 文件已经存在。
- 文件可读取。
- 包含 128 个 PEM 证书。
- API Python 可以加载。
- 钉钉公共 HTTPS 主机验证成功。
- 不需要安装依赖。
- 不需要修改系统证书。
- 不需要修改 Clash。

### 4.2 修改范围

本次只修改：

```text
scripts/workbench.sh
```

在 API 子进程启动时注入：

```bash
SSL_CERT_FILE=/etc/ssl/cert.pem
```

这样后续通过项目启动脚本启动 API 时，子进程能够继承该配置。

这是一项 API 进程级配置，不修改：

- 全局 shell 环境。
- macOS 系统环境。
- 系统证书。
- `.env`。
- Clash Verge。
- FE。
- PostgreSQL。

### 4.3 API 重启

重启前：

```text
API PID: 63184
```

重启后：

```text
API PID: 66552
```

监听地址：

```text
127.0.0.1:8000
```

为了避免完整启动流程触发数据库准备或迁移，本次沿用独立 Uvicorn 启动方式。

其他服务没有重启：

```text
FE PID: 89016
PostgreSQL PID: 83946
```

### 4.4 修复后验证

使用 API 实际 Python 环境验证。

| 检查项 | 结果 |
|---|---|
| SSL_CERT_FILE | 正确设置 |
| CA 路径 | `/etc/ssl/cert.pem` |
| CA 数量 | 128 |
| Verify Mode | CERT_REQUIRED |
| Hostname Checking | Enabled |
| DNS | 成功 |
| HTTPS | HTTP 200 |
| TLS Certificate | Verified |
| Hostname | Verified |
| API Health | OK |
| API Readiness | Ready |
| DingTalk Route | Registered |
| FE | 正常 |
| PostgreSQL | 正常 |

Git 检查：

- `git diff --check` 通过。
- 本次启动脚本改动为 1 行新增、1 行删除。
- 没有增加凭据。
- 没有提交或推送。

Phase 3 验收通过。

---

## 5. Phase 4：真实消息端到端验收

本地 HTTPS 验证成功后，才进入真实业务验收。

用户通过 PAW FE 发送：

```text
钉钉测试
```

最终用户在 Personal AI Workbench 钉钉群中确认收到机器人消息。

因此，完整消息链路通过真实接收端验证。

### 5.1 为什么需要单独的端到端验收？

以下结果只能证明部分链路：

| 结果 | 能证明什么 |
|---|---|
| FE 显示发送成功 | FE 收到了 API 响应 |
| API 返回 200 | API 认为请求处理成功 |
| HTTPS 返回 200 | 外部 HTTP 请求得到成功响应 |
| Webhook 接受消息 | 钉钉接口接受了请求 |
| 群里实际出现消息 | 真实消息投递已完成 |

本案例最终采用最后一项作为验收标准。

### 5.2 超时与重复发送风险

消息发送是具有外部副作用的操作。

如果请求超时，客户端可能无法判断：

- 请求没有到达钉钉。
- 请求已经到达，但响应丢失。
- 钉钉已经处理，只是本地没有收到结果。

因此，不能将所有超时简单视为发送失败并立即重试。

本项目采用：

- 超时或结果未知时不自动重试。
- 先检查实际消息状态。
- 真实发送需要 Owner 明确授权。
- 由接收端确认消息是否实际送达。

---

## 6. 核心技术知识解释

### 6.1 本地 API 与公网 API

本地 API 是指服务运行在本机，例如：

```text
127.0.0.1:8000
```

这表示 API 监听本机回环网络接口。

它不代表 API 不能访问互联网。

需要区分两个网络方向。

**入站连接（Inbound）：**

```text
Internet → Local API
```

外部服务主动访问本机。

**出站连接（Outbound）：**

```text
Local API → Internet
```

本机服务主动访问外部服务。

本次钉钉消息发送使用的是出站连接。

所以不需要：

- 公网 API。
- 端口映射。
- 云服务器。
- 将 FastAPI 暴露到公网。

### 6.2 Webhook

Webhook 是一种通过 HTTP 请求主动向指定地址发送事件或消息的机制。

本案例中：

```text
PAW FastAPI
    |
    | HTTPS POST
    v
DingTalk Webhook
```

钉钉接收到请求后，将消息发布到关联群聊。

Webhook URL 通常包含访问凭据或签名参数，必须视为 Secret。

工程实践：

- Webhook URL 仅保存在服务端。
- FE 不接触真实凭据。
- 日志不打印完整 URL。
- 错误信息不返回 Secret。
- `.env` 不提交 Git。
- 配置示例只使用占位符。

### 6.3 TLS

TLS（Transport Layer Security）是用于保护网络通信的安全协议。

HTTPS 可以理解为 HTTP over TLS。

TLS 不仅负责通信加密，还负责验证通信对端的身份。

客户端需要检查：

1. 服务端证书是否可信。
2. 证书链是否完整有效。
3. 证书是否处于有效期。
4. 证书中的主机名是否匹配访问目标。

本案例中，Python 能够发起外部请求，但缺少可用的默认 CA 信任源，无法验证服务器证书。

这不是通过关闭 TLS 验证就应该解决的问题。

### 6.4 CA 与 CA Bundle

CA 是 Certificate Authority，即证书颁发机构。

CA Bundle 是包含多个可信 CA 证书的文件集合。

客户端使用这些可信证书建立信任链。

典型结构：

```text
DingTalk Server Certificate
          |
          v
Intermediate CA
          |
          v
Trusted Root CA
```

客户端必须能够找到可信的根证书，才能验证服务器提供的证书链。

本案例中的：

```text
/etc/ssl/cert.pem
```

包含 128 个 PEM 证书，已经通过实际 API Python 环境验证。

### 6.5 CA Store

CA Store 是 TLS 实现用于保存或加载可信证书的集合。

本案例中：

```text
Python Default CA Store = 0
```

意味着默认 SSL Context 没有加载可用的默认 CA 信任集合。

这解释了为什么 curl 成功而 Python 失败。

需要注意：

CA Bundle 是证书文件，CA Store 是 TLS 实现使用的可信证书集合。两者相关，但并不是同一个概念。

### 6.6 OpenSSL 与 SecureTransport

OpenSSL 是常见的 TLS 实现库。

本案例中：

- Python 使用 OpenSSL 3.5.9。
- curl 使用 Apple SecureTransport。

不同 TLS 实现可能使用不同的证书信任来源、默认配置和系统集成方式。

因此：

```text
curl HTTPS Success
```

不能直接推导出：

```text
Python HTTPS Success
```

对于 Python FastAPI 服务，应当使用实际 API Python 解释器进行验证。

### 6.7 SSL_CERT_FILE

`SSL_CERT_FILE` 是用于指定 CA 证书文件路径的环境变量。

本案例：

```bash
SSL_CERT_FILE=/etc/ssl/cert.pem
```

它让 Python/OpenSSL 能够找到明确的 CA Bundle。

需要注意：

环境变量应当在 Python 进程启动之前设置。

已经运行的 API 进程不会因为外部 shell 环境发生变化而自动获得新变量。

因此本案例需要重新启动 API。

### 6.8 Hostname Verification

证书链可信，不代表访问目标主机名一定正确。

例如访问：

```text
oapi.dingtalk.com
```

服务端证书必须覆盖这个主机名。

Hostname Verification 用于检查证书身份是否与目标主机名匹配。

本案例始终保持：

```text
CERT_REQUIRED
Hostname Checking = Enabled
```

不能为了绕过错误而关闭这两项检查。

### 6.9 Clash Verge 与 Fake IP

Clash Verge 是代理客户端，Mihomo 是其代理核心。

常见概念：

| 名称 | 含义 |
|---|---|
| System Proxy | 系统代理 |
| Rule Mode | 根据规则选择代理或直连 |
| Global Mode | 流量统一使用指定代理策略 |
| TUN Mode | 通过虚拟网络接口接管流量 |
| Fake-IP DNS | 使用虚拟 IP 表示域名，再由代理核心映射目标地址 |

本案例中观察到：

```text
198.18.1.19
```

该地址属于 `198.18.0.0/15` 保留地址段，符合 Fake-IP DNS 常见地址特征。

但没有直接取得 Clash 完整 DNS 配置，因此不能确认具体的 Fake-IP 设置。

重要经验：

不能仅凭 Clash UI 显示 System Proxy 已启用，就认定所有 Python 进程一定经过相同代理路径。

应该检查：

- 系统代理。
- TUN 状态。
- 进程代理环境变量。
- DNS resolver。
- 实际网络请求结果。

### 6.10 Uvicorn 与进程环境

Uvicorn 是 Python ASGI Server，用于运行 FastAPI 应用。

环境变量通常由父进程传递给子进程。

例如：

```text
workbench.sh
    |
    v
Uvicorn Process
    |
    v
FastAPI Application
```

如果启动脚本没有将 CA 配置传给 API 进程，API 仍可能使用错误的默认信任配置。

本案例在 API 启动时注入 `SSL_CERT_FILE`，而不是修改全局 shell 或 macOS 系统环境。

### 6.11 PID

PID 是 Process Identifier，即进程标识符。

操作系统通过 PID 区分正在运行的进程。

例如：

```text
API PID: 63184
```

重启后：

```text
API PID: 66552
```

通过 PID 可以确认重启前后的进程身份。

对本地开发环境尤其重要：

- 不要误杀 PostgreSQL。
- 不要误杀其他 Python 服务。
- 不要因为 API 启动失败就重启整个系统。
- 先确认端口占用和进程身份。

### 6.12 Health Check 与 Readiness

Health Check 用于判断服务是否处于正常运行状态。

Readiness 用于判断服务是否具备提供服务的条件。

本案例检查：

```text
/health
/health/ready
/openapi.json
```

这些检查分别提供服务状态、就绪状态和 API 路由注册信息。

但：

```text
API Health = OK
```

不等于：

```text
DingTalk Message Delivered
```

只有接收端实际确认，才能完成端到端验收。

---

## 7. 本次排查中的重要工程判断

### 7.1 不要把所有问题归因于代理

最初因为 Clash Verge 正在运行，很容易认为 TLS 失败一定来自代理。

但最终证据表明：

- Python 默认 CA Store 为 0。
- 显式加载可信 CA 后，Python HTTPS 验证成功。
- curl 与 Python 的 DNS 差异没有证明 API 运行时存在独立 DNS 故障。

因此，最终优先修复了 CA 信任源，而没有修改 Clash。

### 7.2 不要用 curl 替代 Python Runtime 验证

curl 和 Python 可能使用不同 TLS 实现、不同 CA 来源和不同代理行为。

对于 Python 服务，必须使用实际 API Python 环境进行验证。

### 7.3 不要关闭 TLS 验证

以下做法属于绕过安全检查，不是修复信任链：

```python
ssl._create_unverified_context()
```

或者：

```python
requests.get(url, verify=False)
```

正确方向是提供可信 CA Bundle。

### 7.4 不要一次修改太多变量

本次没有同时修改：

- Clash。
- macOS DNS。
- 系统证书。
- Python 依赖。
- FE。
- PostgreSQL。

而是先通过实验确认 CA 信任问题，再做最小修改。

这样可以让故障原因与修复结果保持可验证关系。

### 7.5 不要把 HTTP 200 等同于业务成功

本案例出现了两种 HTTP 200：

1. 钉钉公共 HTTPS 主机返回 HTTP 200：证明公共 HTTPS 请求成功。
2. 钉钉 Webhook 接收请求并在群内出现消息：证明业务链路成功。

只有第二种才完成了真实消息验收。

---

## 8. 错误路径与风险控制

| 现象 | 容易出现的错误判断 | 正确处理 |
|---|---|---|
| FE 返回 Not Found | FE 组件或路由错误 | 先检查 API 是否加载新路由 |
| API 返回 502 | API 整体不可用 | 检查服务层与外部请求错误 |
| Python TLS 失败 | 钉钉服务器故障 | 检查 CA 信任源 |
| curl 成功 | Python 网络也正常 | 使用实际 API Python 独立验证 |
| Clash 正在运行 | 一定是代理导致 | 比较真实网络路径和证书来源 |
| DNS 解析失败 | 必须修改系统 DNS | 先确认执行环境和 API 进程上下文 |
| 发送超时 | 再发送一次即可 | 先确认实际消息状态 |
| API Health 正常 | 钉钉已经送达 | 仍需接收端实际确认 |

### 安全约束

- 不输出真实 Webhook URL。
- 不输出代理凭据。
- 不提交 `.env`。
- 不关闭 TLS 验证。
- 不自动重试未知结果。
- 不重启 PostgreSQL。
- 不执行无关数据库迁移。
- 未经 Owner 授权，不发送真实消息。

---

## 9. 可复用的排障流程

以后遇到 Python 服务访问外部 HTTPS 失败，可以采用以下流程。

### 第一层：应用与服务层

1. 确认 FE 到 API 的本地请求是否正常。
2. 确认 API 是否加载目标路由。
3. 确认 API 是否进入预期 Service。
4. 检查 API 日志中的实际错误类型。

### 第二层：Python Runtime

5. 确认 API 实际使用的 Python 解释器。
6. 检查 Python 和 OpenSSL 版本。
7. 检查默认 CA 文件与目录。
8. 检查 CA Store 是否加载证书。

### 第三层：网络与代理

9. 检查 DNS 解析。
10. 对比 curl 和 Python 的代理路径。
11. 检查系统代理、TUN 和进程环境变量。
12. 判断是否存在 Fake-IP 或其他 DNS 行为。

### 第四层：TLS

13. 验证证书链。
14. 验证证书有效期。
15. 验证 Hostname。
16. 检查可信 CA 来源。

### 第五层：修复与验收

17. 提供最小 CA 信任修复。
18. 在必要时重启目标进程。
19. 使用相同 Runtime 验证。
20. 检查 API Health / Readiness。
21. 最后进行真实业务请求。
22. 由接收端确认最终结果。

原则：

**沿着真实请求路径逐层排查，不要根据单个错误信息直接修改多个系统组件。**

---

## 10. 最终架构经验

本案例证明：

本地运行的 AI Application Runtime 完全可以通过安全的出站 HTTPS 访问外部服务。

不需要为了访问外部 API 而把本地 FastAPI 部署到公网。

推荐的本地优先网络模型：

```text
Local AI Application
        |
        v
Local API Runtime
        |
        v
Local Network / Proxy
        |
        v
Outbound HTTPS
        |
        v
External AI / SaaS / Webhook Services
```

对于 Personal AI Workbench、Agent Runtime、MCP Client 和 LLM Application，这种本地优先架构具有实际价值。

但需要明确：

- 本地服务的安全边界。
- 外部服务的认证方式。
- 代理与 DNS 行为。
- TLS 证书信任来源。
- Secret 的存放与日志边界。
- 请求超时与重复执行风险。

---

## 11. 后续可继续研究的知识点

本案例涉及的知识点可以进一步拆分为独立的学习资产：

| 知识主题 | 后续研究方向 |
|---|---|
| Python SSL | Python `ssl` 模块与 SSL Context |
| OpenSSL | CA Store、证书链验证 |
| macOS TLS | SecureTransport 与系统信任机制 |
| CA Bundle | PEM 格式、根证书和中间证书 |
| Python Runtime | Python 3.15 的证书配置机制 |
| Clash Verge | System Proxy、TUN、Rule Mode |
| Mihomo DNS | Fake-IP DNS 与域名解析 |
| HTTP Client | urllib、Requests、HTTPX 的代理行为 |
| Uvicorn | 进程生命周期与环境变量继承 |
| Webhook | 幂等性、超时与重复投递 |
| Agent Runtime | 外部工具调用的网络安全 |

这些属于后续学习方向，不代表本次已经完成所有主题的深入研究。

---

## 12. 证据与可信度边界

本案例依据本轮 PAW 故障排查过程、Codex 阶段报告和 Owner 对真实消息送达的确认整理。

### 12.1 已确认事实

- API Python 默认 CA Store 为 0。
- `/etc/ssl/cert.pem` 包含 128 个 PEM 证书。
- API Python 使用该文件后 TLS 和 Hostname 验证成功。
- pip vendored certifi Bundle 也通过过目标主机验证。
- Phase 3 仅修改 `scripts/workbench.sh`。
- API 重启后 CA 配置生效。
- 公共 HTTPS 请求返回 HTTP 200。
- API Health / Readiness 正常。
- FE 和 PostgreSQL 保持运行。
- Owner 最终确认钉钉群收到消息。

### 12.2 有依据但未完全确认

- `198.18.1.19` 符合 Clash Fake-IP 地址段特征。
- 受限执行环境中的 DNS 失败与实际 API 运行环境不同。
- 当时 Python 与 curl 的网络路径可能存在差异。

### 12.3 没有证据支持，不应写成事实

- Clash 一定拦截了 HTTPS。
- Clash 一定导致了 TLS 错误。
- Python API 一定绕过了 Clash。
- 本次故障需要修改 macOS DNS。
- 本次故障需要安装 certifi。
- 本次故障需要关闭 TLS 验证。

### 12.4 敏感信息处理

本案例不包含：

- 真实 Webhook URL。
- Webhook Secret。
- 代理节点凭据。
- 订阅地址。
- 其他敏感配置。

---

## 13. 案例结论

这次问题不是 FastAPI 本身的故障，也不是 DingTalk Webhook 实现逻辑的问题。

真正的问题出现在本机 Python Runtime 的默认 TLS 信任配置。

最终通过给 API 进程提供一个已经验证可用的 CA Bundle，解决了证书验证问题。

整个过程：

- 没有关闭 TLS 验证。
- 没有增加 Python 依赖。
- 没有修改 Clash。
- 没有修改 macOS 系统证书。
- 没有改变 PAW 的本地部署架构。
- 没有重启 PostgreSQL。
- 最终通过真实钉钉群消息完成端到端验收。

**最值得保留的工程经验：不要只看应用层错误，要沿着实际请求路径逐层验证运行时、网络、DNS、TLS 信任和业务送达。**
