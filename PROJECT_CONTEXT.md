# Personal AI Workbench 工程上下文

> 本文件是 Personal AI Workbench 的综合工程上下文入口。它描述可验证的代码与文档事实、已确认的设计、候选方案和待解决差异。接手任务时仍必须检查当前代码和 Git 状态；本文件不替代实现证据。

## 状态标记

- **CONFIRMED**：由当前代码、测试、Git 历史或可靠文件证据验证。
- **DECIDED**：设计方向已确认，但不表示已经实现。
- **PENDING**：未完成、未验证、信息冲突或有待 Owner 确认。
- **PROPOSED**：候选方案，尚未批准为项目决策。
- **DEPRECATED**：已经废弃的方案或历史决策。

信息冲突时，最新明确的 Owner 决策优先；代码和可重复运行结果说明实现状态；本存档记录经核对后的上下文；历史讨论和 Agent 建议只作为参考。若实现事实与架构意图冲突，应同时记录两者并提交审查，不能静默改写其中一方。

## 01. 项目背景（Project Background）

**CONFIRMED**：Personal AI Workbench 是一个由多个独立产品组成的个人 AI 工作台，聚焦工程经验复现、可复用工程能力和技术知识资产。Workbench 提供统一入口、共享基础设施和跨产品协作基础；各产品保持平级并拥有自己的业务边界。

**PENDING**：尚无正式 Persona 文档。基于“个人 AI 工作台”的定位，项目所有者及其开发协作者是目标用户假设，待 Owner 确认。

项目要解决的问题包括：工程经验难以复现和验证、工程工具与方法缺乏系统沉淀、技术知识来源与整理结果难以关联和维护。产品定义分别见 `products/project-replay/README.md`、`products/personal-arsenal/README.md` 和 `products/personal-knowledge/README.md`。

## 02. 项目愿景与目标（Project Vision & Goals）

**DECIDED**：长期方向是建设 Web、Android 和 Python API 的统一工程基础，并支持 Project Replay、Personal Arsenal、Personal Knowledge 持续积累与演进。Workbench 采用 Monorepo，但不预先决定必须拆成微服务。

阶段目标：

1. **CONFIRMED**：建立仓库基线、三个平级产品的定位、总体架构说明和 API 工程基础。
2. **CONFIRMED**：API 提供健康检查和第一条客户端 Capture 接口；Capture 当前只同步确认提交。
3. **PENDING**：逐步实现客户端和真实知识摄取/处理能力。各步骤须先有明确契约并经授权，不把产品目标当作已交付功能。

## 03. 架构上下文（Architecture Context）

### 已实现架构

- **CONFIRMED**：Monorepo 包含 `apps/`、`products/`、`services/`、`docs/`。Web 与 Android 目录目前为空，无客户端代码或构建配置。
- **CONFIRMED**：三个产品各有 README 产品说明，定义各自定位和边界；没有产品业务实现。
- **CONFIRMED**：`services/api/` 使用 FastAPI、Pydantic 和 Uvicorn。`app/main.py` 注册 `/health` 和客户端 Capture Router。
- **CONFIRMED**：Capture 流程是客户端 `POST /api/v1/ingestion/captures` → Pydantic 请求校验 → Router 调用 Service → 生成 `cap_<uuid-hex>` 临时确认标识 → HTTP 200 同步响应。当前不持久化 Capture，不创建持久化任务，也不触发 Fetch、Parse、Normalize 或后续 Ingestion。
- **CONFIRMED**：API 基础与 Capture 测试共 9 项；最近验收结果为 9 passed。API README 描述当前运行方式、契约和限制。
- **CONFIRMED**：总体架构文档为 `docs/architecture/overview.md`。`docs/decisions/` 当前没有决策文档。

### 规划架构

- **DECIDED**：Workbench 共享服务不承载所有产品业务逻辑；产品通过明确接口和共享能力协作。
- **DECIDED**：Personal Knowledge 的概念流程包含 Capture、Digest、Link、Publish，原始知识与整理后的知识需要可追溯关联。
- **PENDING**：未来 Capture 持久化、Ingestion Fetch/Parse/Normalize、Document 持久化及后续知识整理/检索的实体、接口、执行方式和数据流尚未确定或实现。
- **PROPOSED**：FxTwitter API 可用于 X 内容提取实验。仓库没有 Provider、FxTwitter 接入或相关实验结果。
- **PROPOSED**：LangGraph 多智能体工作流和 GPT Review Callback 是后续可研究方向；目前没有相关依赖或实现。

## 04. 架构不变量（Architecture Invariants）

以下不变量来自现有 `docs/architecture/overview.md`、产品文档和用户明确约束：

1. **DECIDED**：三个产品是平级业务产品，边界独立，不将一个产品作为另一个的子模块。
2. **DECIDED**：`apps/` 是客户端入口，`products/` 定义业务边界，`services/` 提供共享后端能力，`docs/` 保存架构与工程治理材料。
3. **DECIDED**：产品只通过明确接口和共享能力协作；没有确认的协作流程不得被实现成隐含依赖。
4. **DECIDED**：Monorepo 不等同于微服务承诺；是否拆分服务应基于实际需求另行决策。
5. **CONFIRMED**：Capture API 当前只同步接收并确认提交，不代表持久化资源或后台任务；不得把现状文案扩展为已抓取或已入库。
6. **DECIDED**：不得以删除测试、放宽校验或隐藏异常制造虚假的通过结果。

## 05. 技术栈与选型理由（Technology Stack & Rationale）

| 技术/方向 | 状态 | 依据与边界 |
| --- | --- | --- |
| Python 3.15.2 | **CONFIRMED（本地环境）** | 用户当前本地解释器为 3.15.2；`services/api/pyproject.toml` 声明 `requires-python = ">=3.15,<3.16"`。该声明是当前工程事实，不等同于正式确定项目长期基线。 |
| Python 3.12 | **PROPOSED（曾由 Assistant 建议）** | 曾作为生态成熟度较高的候选版本提出；用户未批准为项目最终基线。 |
| 项目 Python 基线 | **PENDING** | 尚未正式决定。应在项目实际依赖引入并完成兼容性验证后评估；不得将本地版本或当前声明单独升级为不可变架构决策。 |
| FastAPI、Pydantic、Uvicorn | **CONFIRMED** | API 实际依赖与代码使用；FastAPI 提供 HTTP/OpenAPI，Pydantic 校验契约，Uvicorn 启动服务。 |
| SQLite | **PENDING** | 历史上下文提到 SQLite 方向，但当前没有可核验的最终批准记录；没有数据库连接、Schema、ORM 或 SQLite 代码。 |
| REST API | **CONFIRMED** | 当前 API 采用 HTTP 路径、JSON 请求/响应和状态码；该风格不代表全部资源契约已定。 |
| FxTwitter API | **PROPOSED** | 作为 X 内容提取实验候选接口；未接入、未验证，不得当作 Provider 决策或能力。 |
| LangGraph / Agent Runtime | **PROPOSED** | 作为未来多智能体工作流方向，尚未批准具体架构或加入依赖。 |

依赖版本以当前 `pyproject.toml` 与已安装环境为准；新增第三方依赖须有明确授权和理由。架构设计须区分“决定使用”与“已经实现”。

## 06. 工程推进历史（Development History）

### 可由 Git 识别的两个后端施工动作

Git 历史中的两个后端实现提交均记录于 **2026-11-13（+08:00）**。另有一次根 README 文档提交。因当前日期也是 2026-11-13，仓库证据不能证明这两个实现提交发生在“昨天”。它们是目前能确认的两个具体后端施工动作；是否就是用户所指“昨天的两个动作”标记为 **PENDING**，不伪造日期。

#### 动作 A：FastAPI 工程骨架 — `e123255`

- **目标**：建立可运行、可测试的共享 API 工程基础。
- **实施与文件**（`git show --name-only e123255`）：新增 `services/api/.env.example`、`services/api/README.md`、`services/api/app/__init__.py`、`services/api/app/api/__init__.py`、`services/api/app/api/v1/__init__.py`、`services/api/app/api/v1/shared/__init__.py`、`services/api/app/core/__init__.py`、`services/api/app/main.py`、`services/api/app/schemas/__init__.py`、`services/api/app/services/__init__.py`、`services/api/pyproject.toml`、`services/api/tests/test_health.py`。
- **技术决策**：当次施工任务要求使用本地 Python 3.15.2、FastAPI/Pydantic、独立 `.venv` 与 Pytest；提交中 `pyproject.toml` 声明 `>=3.15,<3.16`。这证明当次实现环境/工程约束，不证明 Owner 已确定长期 Python 基线。没有数据库或 ORM 实现。
- **验证**：历史施工报告记载 2 项健康/Swagger 测试通过且依赖安装成功；提交包含 `test_health.py`。当前没有独立 CI 测试日志，故通过结果属于历史报告，不能由 Git 提交本身独立验证。
- **遗留**：SQLite 被提供的历史信息称为讨论方向，但仓库没有数据库实现；Python 最终基线仍为 **PENDING**。
- **治理审查**：施工范围与当次授权一致，添加依赖是为满足 FastAPI/测试要求且当次获得授权；未实现未授权业务。该动作发生时没有 `PROJECT_CONTEXT.md`，因此无法遵守“开工前阅读统一上下文”以及“施工后同步上下文”的流程；历史中也没有记录当时的 14 项治理协议。其余过程证据以提交内容和当时测试报告为限，不推断未留痕的审查步骤。

#### 动作 B：CLIENT Capture API — `5148ecf`

- **目标**：提供首个可通过 Swagger 验证的 Capture 请求入口。
- **实施与文件**（`git show --name-only 5148ecf`）：新增/修改 `services/api/README.md`、`services/api/app/api/v1/client/__init__.py`、`services/api/app/api/v1/client/ingestion/__init__.py`、`services/api/app/api/v1/client/ingestion/captures.py`、`services/api/app/main.py`、`services/api/app/schemas/capture.py`、`services/api/app/services/capture_service.py`、`services/api/tests/test_capture.py`。之后经独立 Review 将状态码对齐到 HTTP 200，并补充空白字符串校验与测试；最终状态包含在该提交中。
- **实际结果**：URL/text 请求通过 Pydantic 校验后，Service 生成临时 ID，API 返回 `200 OK`；缺字段、非法 `input_type`、纯空白 `content`/`intent` 返回 `422`。没有写数据库、创建 Ingestion Task 或抓取内容。
- **验证**：历史施工报告记载提交前 Pytest 为 9 passed、`pip check` 无依赖问题、`git diff --check` 通过；测试文件包含 URL/text、422 校验、Audience 与 OpenAPI 200 断言。当前没有独立 CI 测试日志，因此运行通过结果属于历史报告，不是 Git 可独立证明的事实。
- **技术决策与原因**：同步生成确认标识对应 HTTP 200，不使用暗示异步受理的 202；Audience 为 CLIENT；输入仅支持 `url`/`text`；没有新增依赖。
- **遗留**：提交内容不持久化，Capture ID 仅为临时标识；Fetch、Parse、Normalize、Provider、后台任务等未实现。请求的业务意图及 Capture 持久化模型尚未深化。
- **治理审查**：实现与授权范围相符、未改变产品边界、未新增依赖，有测试和独立 Review，提交/推送获得了明确授权。施工当时仍没有 `PROJECT_CONTEXT.md`，上下文前置读取和后续存档要求未能满足；因此不能宣称完全符合后来建立的全部治理流程。其他未被提交、测试或会话证据覆盖的过程细节标为 **PENDING**。

### 相关文档动作

提交 `b5c3421`（`docs: update workbench project overview`，2026-11-13）仅修改 `README.md`。Git Diff 显示其更新项目总览、目录状态及文档导航；这是 README 项目介绍更新，不是 AI Agent 治理规范提交，也不计为上述两个后端施工动作。随后本任务要求 README 加入协作规范并创建本文件。

## 07. 当前项目状态（Current Project Status）

- **CONFIRMED — 已完成**：总体架构基线、三份产品定位文档、FastAPI 工程骨架、健康检查、CLIENT Capture 同步确认 API、对应测试和 API README。
- **CONFIRMED — 已验证**：最近 API 验收为 9 项测试通过；当前 HEAD 为 `5148ecf`，分支 `main` 与 `origin/main` 同步，开始本次文档任务时工作区干净。
- **PENDING — 未开始**：Web/Android 实现；Capture 持久化；数据库连接；Fetch、Parse、Normalize 与异步 Ingestion；Document 和后续知识处理。
- **CONFIRMED**：`docs/decisions/` 当前无文件；没有 LangGraph、Agent Runtime、FxTwitter Provider 或 RAG 实现。

## 08. 当前施工位置（Current Working Position）

- **CONFIRMED**：项目总体架构为 Active Baseline；API 工程基础和第一个 Capture 接口已交付。
- **CONFIRMED**：最近有效代码施工完成于 `5148ecf`。当前 API 成功响应为 HTTP 200，且不持久化、不触发后续处理。
- **PENDING**：本次正在建立工程上下文档案和根 README 多智能体治理规范；交付后等待 Project Owner 审阅。
- **下一步**：Owner 确认本文记录的 Python 版本冲突与“昨天两项动作”的时间归属；之后再授权下一项工程任务。不要自行开始数据库或 Ingestion Pipeline 施工。

## 09. 遗留问题与技术债务（Pending Issues & Technical Debt）

1. **PENDING**：项目最终 Python 基线尚未决定；当前本地为 3.15.2，`pyproject.toml` 要求 `>=3.15,<3.16`。Python 3.12 是 Assistant 曾建议的候选，未获用户最终批准。
2. **PENDING**：SQLite 是否为最终数据库选择尚待确认；数据模型、迁移、事务和访问模式均未设计或实现。
3. **PENDING**：无法由提交时间验证两项后端动作是“昨天”发生的；Git 记录日期均为 2026-11-13。
4. **PENDING**：Capture 是否在同步确认后持久化、后续任务如何产生以及幂等/重试语义尚未设计。
5. **PENDING**：输入类型扩展、URL 规范化、Provider 选择、来源证据及错误契约待需求确认。未来实现 URL Fetch 时按风险核对目标地址、重定向、超时和响应大小；当前不引入额外安全架构或基础设施。
6. **PENDING**：apps 目录为空；docs/decisions 没有正式决策文档。
7. **PROPOSED**：FxTwitter 是候选实验接口，不代表其可用性、合规性或项目采纳已验证。

## 10. 重要架构决策（Important Decisions）

- **DECIDED**：三大产品平级、边界独立；共享服务不得吞并产品业务逻辑。
- **DECIDED**：现阶段采用 Monorepo，不承诺微服务拆分。
- **CONFIRMED**：当前 API 使用 FastAPI/Pydantic 与 REST 风格 HTTP 接口。
- **CONFIRMED**：Capture 当前是同步确认接口，成功状态为 200；Capture ID 临时生成，不等于持久化资源。
- **PROPOSED（曾由 Assistant 建议）**：Python 3.12 曾作为候选方案提出，用户未批准为最终基线。
- **PENDING**：项目 Python 基线尚未正式决定；当前本地为 3.15.2，工程声明为 `>=3.15,<3.16`。应在依赖引入并验证兼容性后由 Owner 决定。
- **PENDING**：SQLite 为历史讨论方向，最终决策待确认，当前未实施。
- **PROPOSED**：FxTwitter、LangGraph/GPT Review Callback 是待评估方向，不得当作批准或已实现。

## 11. AI Agent 施工契约（Agent Engineering Contract）

### 角色

- **Project Owner**：项目所有者，拥有最终决策权、授权权和验收权。
- **Chief Architect**：ChatGPT，负责架构指导、上下文治理、施工任务设计和 Review；不取代 Owner 的决定。
- **Implementation Agents**：Codex、Gemini、DeepSeek 等，按任务授权实施代码、测试与文档变更。

### 所有 Agent 必须遵守

1. 开工前阅读本文件，并检查当前实际代码、Git 状态和相关文档；存档不能代替代码核实。
2. 只修改授权文件和范围；不得自行扩展需求或改变核心架构。
3. 不擅自增加第三方依赖；发现冲突或需求歧义应暂停并报告。
4. 遵循现有风格和模块职责，提供可复核的测试/验证证据。
5. 报告每个修改文件、原因、关键位置、测试结果、遗留事项和架构偏差。
6. 按授权同步必要上下文；上下文与代码不一致时记录差异并请求审查。
7. 未获 Owner 明确授权不得 Commit 或 Push。
8. 不得删测试、降低校验、吞掉异常或伪造成功结果。

## 12. 变更与审查协议（Change & Review Protocol）

1. 发现架构问题时先提出问题、原因、影响和可选方案；未经授权不实施架构变更。
2. 需要决策或范围不清时暂停依赖该决策的工作，并请 Owner/Chief Architect 审查。
3. 实施后提供完整 Diff、验证命令与结果、范围检查和未解决风险。
4. GPT Review 检查实现与设计的一致性、模块职责、依赖变化、异常处理、测试质量和技术债务；Review 是建议与证据，不是 Owner 批准。
5. 核心架构变更由 Project Owner 最终确认。提交、推送、发布等操作遵循每项任务的明确授权。
6. 所有工程变更应可审查、可验证、可回滚；不得通过隐藏变更或改写历史规避审查。

### Minimum Sufficient Review（CR Policy）

审查深度与改动风险匹配，默认 L1；仅在具体风险需要时升级。不得无理由扫描全仓、重复可靠验证或默认要求完整 Diff。

- **L1 — Lightweight Review**：适用于文档、README、`PROJECT_CONTEXT.md` 和低风险配置。检查修改文件、Diff 摘要、政策符合性、重要内容准确性及明显遗漏/不一致；不做无关全仓扫描，不复现完整 Diff。
- **L2 — Targeted Code Review**：适用于 API、Service、Schema、业务逻辑和数据库改动。检查变更代码及必要上下游、架构边界、异常与边缘情况、相关测试；默认只运行相关测试。
- **L3 — Deep Architecture Review**：适用于核心架构、依赖体系、跨模块或安全敏感改动。检查相关调用链与数据流、系统边界和依赖影响、架构一致性、安全/稳定性及回归风险；按具体疑点扩展范围。
- **升级原则**：按实际风险自动选择级别；说明扩大审查范围的理由。优先给出简洁摘要、验证证据和关键代码位置；仅在必要时展开完整 Diff。

## 13. 工程交接协议（Handover Protocol）

每个 Agent 交付时应提供：任务目标、完成内容、修改文件、关键代码位置、测试/验证证据、未完成事项、遗留问题、架构偏差和下一步建议。交接记录必须区分事实、决策、候选方案和未知事项，使新 Agent 无须依赖原始聊天即可从本文件与代码继续工作。

## 14. 下一步行动（Next Actions）

1. **PENDING**：Project Owner 审阅本上下文与 README，确认项目 Python 基线；3.12 仅为曾提出的候选，3.15.2 是本地环境，工程声明为 `>=3.15,<3.16`。
2. **PENDING**：若 Owner 确认 SQLite 决策，另行明确持久化目标、模型和事务边界后再派发施工任务。
3. **PENDING**：针对 Capture 是否创建持久化资源或后续 Ingestion Task 形成明确契约；保持当前 API 同步确认语义，直到变更获批。
4. **PROPOSED**：在 Provider 选择获批后，单独设计 X 内容提取实验；不得直接把 FxTwitter 接入生产路径。
5. **PENDING**：Web、Android 与 LangGraph/GPT Review Callback 仅在需求和架构获批后排期。
