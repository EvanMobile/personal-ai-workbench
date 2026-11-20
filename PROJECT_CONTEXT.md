# Personal AI Workbench 工程上下文

> 本文件是 Personal AI Workbench 的综合工程上下文入口。它描述可验证的代码与文档事实、已确认的设计、候选方案和待解决差异。接手任务时仍必须检查当前代码和 Git 状态；本文件不替代实现证据。

## 状态标记

- **CONFIRMED**：由当前代码、测试、Git 历史或可靠文件证据验证。
- **DECIDED**：设计方向已确认，但不表示已经实现。
- **PENDING**：未完成、未验证、信息冲突或有待 Owner 确认。
- **PROPOSED**：候选方案，尚未批准为项目决策。
- **DEPRECATED**：已经废弃的方案或历史决策。

信息冲突时，最新明确的 Owner 决策优先；代码和可重复运行结果说明实现状态；本存档记录经核对后的上下文；历史讨论和 Agent 建议只作为参考。若实现事实与架构意图冲突，应同时记录两者并提交审查，不能静默改写其中一方。

## 治理文档入口与当前施工边界

- **DECIDED**：当前工程周期以 Project Owner 批准的 **Frozen Engineering Scope v1.0** 为施工边界；七个施工模块、产品级工程要求、最终交付标准和排除范围见 [`docs/governance/frozen-engineering-scope-v1.0.md`](docs/governance/frozen-engineering-scope-v1.0.md)。增加范围须经 Project Owner 明确批准。
- **DECIDED**：协作遵循 **Human-Owned Engineering, AI-Assisted Implementation**；职责、Knowledge Mastery、Learning Gate 和 Milestone Capability Review 见 [`docs/governance/human-owned-engineering.md`](docs/governance/human-owned-engineering.md)。
- **CONFIRMED**：Knowledge Mastery L1-L4 与本文件的 L1/L2/L3 Minimum Sufficient Review（CR Policy）是两套不同制度；前者评估人的知识能力，后者定义代码审查深度。
- **CONFIRMED**：Frozen Scope v1.0 已按 Project Owner 提供的完整批准文本记录于治理文档。施工不得自行缩减、重新解释或扩展该范围。

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

- **CONFIRMED**：Monorepo 包含 `apps/`、`products/`、`services/`、`docs/`、`scripts/`。`apps/web/` 已实现 React + TypeScript + Vite 工作台；`apps/android/` 仍为空。
- **CONFIRMED**：三个产品各有 README；Personal Knowledge 已具备 P1.M1 纵向切片实现，Project Replay 与 Personal Arsenal 仅保留目录入口。
- **CONFIRMED**：`services/api/` 使用 FastAPI、Pydantic、Uvicorn、PostgreSQL、SQLAlchemy 2.x、Alembic；`app/main.py` 注册 Capture、Knowledge、Dossier、Page、Artifact、Chat 路由。
- **CONFIRMED**：Capture 支持文本、URL（仅保存不抓取）与 UTF-8 文本文件上传；Raw Content 持久化到 PostgreSQL，含来源、hash 与 metadata。
- **CONFIRMED**：知识流程为 Capture → Mock Digest（六节 Draft）→ 人工修订 → 人工 Publish → Knowledge Asset + Visual Artifact；Publish 仅由显式接口触发。
- **CONFIRMED**：Dossier（共享标签生成 edges）、Page（版本化 JSON 内容）与 Artifact（PNG 渲染、文件缓存、来源 hash 校验）已实现。
- **CONFIRMED**：后端测试 21 项通过（2026-11-20 实际运行，PostgreSQL 测试库）；Web `pnpm build` 通过。
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
| PostgreSQL | **CONFIRMED（已实现）** | Owner 于 2026-11-19 决定采用；本地 PostgreSQL 17.12 已运行，迁移已应用，测试使用 `workbench_test`。 |
| SQLAlchemy 2.x + Alembic | **CONFIRMED（已实现）** | SQLAlchemy 2.1.9、Alembic 1.20.1、psycopg 3.3.9 已安装；迁移由 Alembic 管理。 |
| React + TypeScript + Vite | **CONFIRMED（已实现）** | `apps/web/` 工作台；构建通过（Vite 7.3）。 |
| Pillow（Visual Artifact） | **CONFIRMED（已实现）** | 知识卡片 PNG 渲染；无外部图片服务依赖。 |
| pgvector | **PROPOSED** | 仅作为未来向量检索的演进路径；当前不启用、不建表，P3 再评估。 |
| REST API | **CONFIRMED** | 当前 API 采用 HTTP 路径、JSON 请求/响应和状态码；该风格不代表全部资源契约已定。 |
| FxTwitter API | **PROPOSED** | 作为 X 内容提取实验候选接口；未接入、未验证，不得当作 Provider 决策或能力。 |
| LangGraph / Agent Runtime | **PROPOSED** | 作为未来多智能体工作流方向，尚未批准具体架构或加入依赖。 |

依赖版本以当前 `pyproject.toml` 与已安装环境为准；新增第三方依赖须有明确授权和理由。架构设计须区分“决定使用”与“已经实现”。

## 06. 工程推进历史（Development History）

### 可由 Git 识别的两个后端施工动作

Git 历史中可确认两个后端实现提交，均记录于 **2026-11-13（+08:00）**（`e123255`、`5148ecf`）；同期及之后另有若干文档与治理提交，索引见下节「相关文档动作」。核对本文档时当前日期为 **2026-11-19**，仓库证据仍不能证明这两个实现提交发生在用户所指的“昨天”。它们是目前能确认的两个具体后端施工动作；是否就是用户所指“昨天的两个动作”继续标记为 **PENDING**，不伪造日期。

#### 动作 A：FastAPI 工程骨架 — `e123255`

- **目标**：建立可运行、可测试的共享 API 工程基础。
- **实施与文件**（`git show --name-only e123255`）：新增 `services/api/.env.example`、`services/api/README.md`、`services/api/app/__init__.py`、`services/api/app/api/__init__.py`、`services/api/app/api/v1/__init__.py`、`services/api/app/api/v1/shared/__init__.py`、`services/api/app/core/__init__.py`、`services/api/app/main.py`、`services/api/app/schemas/__init__.py`、`services/api/app/services/__init__.py`、`services/api/pyproject.toml`、`services/api/tests/test_health.py`。
- **技术决策**：当次施工任务要求使用本地 Python 3.15.2、FastAPI/Pydantic、独立 `.venv` 与 Pytest；提交中 `pyproject.toml` 声明 `>=3.15,<3.16`。这证明当次实现环境/工程约束，不证明 Owner 已确定长期 Python 基线。没有数据库或 ORM 实现。
- **验证**：历史施工报告记载 2 项健康/Swagger 测试通过且依赖安装成功；提交包含 `test_health.py`。当前没有独立 CI 测试日志，故通过结果属于历史报告，不能由 Git 提交本身独立验证。
- **遗留**：SQLite 被提供的历史信息称为讨论方向，但仓库没有数据库实现；Python 最终基线仍为 **PENDING**。（2026-11-19 Owner 已决定改用 PostgreSQL，见 §05 与 §10。）
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

### 文档与治理提交索引（2026-11-13 至 2026-11-19）

**CONFIRMED**：以下提交由 `git log`、`git show --stat` 直接核实；五项均未改变后端实现，故不计入上述两个后端施工动作。

| 提交 | 日期（+08:00） | 变更文件 | 说明 |
|---|---|---|---|
| `594dec5` | 2026-11-13 | `PROJECT_CONTEXT.md` | 首次建立本主存档（+189 行） |
| `05b2ecd` | 2026-11-13 | `README.md` | README 治理规范补充（+98/−48） |
| `3a2e59d` | 2026-11-14 | `skills/knowledge-analysis/SKILL.md` | ContentParser Skill v1.1（+370 行） |
| `12d119e` | 2026-11-19 | `docs/governance/` 两份新文档、`PROJECT_CONTEXT.md`、`README.md` | Frozen Scope v1.0 与 Human-Owned Engineering 落地 |
| `29e895f` | 2026-11-19 | `docs/governance/multi-model-engineering-collaboration.md` | 多模型协作约定 |

**CONFIRMED**：`12d119e` 对本文档为增量修改（+9 行），未重写既有章节；当前 `HEAD` 即 `29e895f`。

## 07. 当前项目状态（Current Project Status）

- **CONFIRMED — 已完成**：P1.M1 第一阶段纵向切片：PostgreSQL 基础设施、Capture 持久化、Mock Digest、Draft 修订、人工 Publish、Dossier、Page、Visual Artifact、Web 三栏工作台、启动/停止/健康检查脚本、备份与恢复脚本。
- **CONFIRMED — 已验证（2026-11-20）**：后端 `pytest` 21 passed（真实 PostgreSQL 测试库）；前端 `pnpm build` 通过；`./scripts/workbench.sh start` 可启动三项服务并输出 URL；备份 → 空库恢复演练行数一致（7 assets / 7 raw / 7 captures）且附件恢复成功。
- **CONFIRMED — 现场**：`HEAD` 仍为 `29e895f`；工作区有大量未提交新增/修改（后端模块、迁移、Web、脚本、文档），**未 Commit / Push**。
- **PENDING — 未开始**：真实外部 LLM Provider 调用；URL 抓取与 PDF/Word 解析；RAG/Embedding/pgvector 实现；Android；钉钉；完整评测。
- **CONFIRMED**：`docs/decisions/` 当前无文件；没有 LangGraph、Agent Runtime、FxTwitter Provider 或 RAG 实现。

## 08. 当前施工位置（Current Working Position）

- **CONFIRMED**：项目总体架构为 Active Baseline；P1.M1 第一阶段实现已落盘并通过本地端到端验证。
- **CONFIRMED — 当前阶段**：Owner 已授权 P1.M1 第一阶段施工；PostgreSQL、后端、Visual Artifact、Web 与运维脚本已实现，服务可通过 `./scripts/workbench.sh start` 启动。
- **CONFIRMED — 边界**：真实外部 LLM 调用仍未授权，默认 Mock Provider；URL 不抓取；PDF/Word/图片/视频不支持；RAG/pgvector/Redis 未实现。
- **CONFIRMED — 门禁**：**Git Commit / Push 未获授权**；首次真实 Provider 调用须单独报告并等待 Owner 授权。
- **下一步**：Owner / GPT 验收；根据反馈修复；获得单独授权后再 Commit。

## 09. 遗留问题与技术债务（Pending Issues & Technical Debt）

1. **PENDING**：项目最终 Python 基线尚未决定；当前本地为 3.15.2，`pyproject.toml` 要求 `>=3.15,<3.16`。Python 3.12 是 Assistant 曾建议的候选，未获用户最终批准。
2. **CONFIRMED（已实现）**：PostgreSQL 17 已作为基础关系数据库运行；Schema 由 Alembic 管理；备份/恢复脚本已完成一次空库演练。剩余债务：索引与查询优化、pgvector 评估。
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
- **DECIDED / CONFIRMED**：采用 PostgreSQL 作为基础关系数据库；数据访问采用 SQLAlchemy 2.x、迁移采用 Alembic；已实现并通过测试。
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
2. 需要决策或范围不清时，暂停受影响的工作并提交 Project Owner 决定；Chief Architect / GPT 可以提供分析、方案比较和 Review 意见，但不拥有独立的 Owner 决策或授权权力。
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

0. **CONFIRMED**：Frozen Engineering Scope v1.0 和 Human-Owned Engineering 治理文档已落入 `docs/governance/`；后续施工应按 Phase → Milestone → Task 依赖关系规划，并遵守学习门槛、Milestone Review 和既有 CR Policy。

1. **PENDING**：Project Owner 审阅本上下文与 README，确认项目 Python 基线；3.12 仅为曾提出的候选，3.15.2 是本地环境，工程声明为 `>=3.15,<3.16`。
2. **DECIDED / PENDING（实现）**：数据库基线已定为 PostgreSQL（2026-11-19）；持久化目标、数据模型、迁移与事务边界仍待基础设施 Task 明确后再派发业务施工。
3. **PENDING**：针对 Capture 是否创建持久化资源或后续 Ingestion Task 形成明确契约；保持当前 API 同步确认语义，直到变更获批。
4. **PROPOSED**：在 Provider 选择获批后，单独设计 X 内容提取实验；不得直接把 FxTwitter 接入生产路径。
5. **PENDING**：Web、Android 与 LangGraph/GPT Review Callback 仅在需求和架构获批后排期。

6. **CONFIRMED**：Owner 已受理 D1（本文档事实性修订）与 D2（四份规划文档审查与授权机制）。本轮**不批准 P1.M1 编码、不批准 Commit / Push**。本文档修订依据 D1 方案 E1–E6 及 §12.2 决策归属修正完成；未新增任何技术选型批准。

7. **CONFIRMED（2026-11-19）**：Owner 批准七模块职责与依赖、Personal Knowledge 对象生命周期两份文档为当前架构基线；Owner 决定采用 PostgreSQL 作为基础关系数据库（SQLAlchemy 2.x + Alembic 方向）。P1.M1 实施准备已收敛为 v0.3。

8. **CONFIRMED（2026-11-20）**：P1.M1 第一阶段实际施工完成并通过本地端到端验证（后端 21 tests、前端 build、启动脚本、备份恢复演练）。真实外部 LLM 调用与 Commit / Push 仍未获授权。

## 15. 规划文档基座与审批状态（Planning Document Baseline）

**本节只记录 2026-11-19 核对所得事实与并存差异；除 Owner 本轮明确的 PostgreSQL 决定及由此同步的 §05/§09/§10/§14 事实状态外，不改变其他既有状态判定，也不构成对未决事项的裁决。**

### 15.1 未提交规划文档（CONFIRMED）

- **CONFIRMED**：截至 `29e895f`，以下 4 个文件存在于工作区但未纳入 Git，无提交历史；仓库内没有正式 Review 或审批记录。两份架构文档的 Owner 批准结论仅记录于本节，尚未形成独立档案：
  - `docs/architecture/module-responsibilities-and-dependencies.md`
  - `docs/architecture/personal-knowledge-object-lifecycle.md`
  - `docs/roadmap/engineering-roadmap-v1.0.md`
  - `docs/roadmap/p1-m1-implementation-preparation.md`
- **CONFIRMED**：未提交状态只表示未纳入版本管理。七模块职责与依赖、Personal Knowledge 对象生命周期两份文档已于 2026-11-19 获 Owner 批准为架构基线；工程路线图与 P1.M1 实施准备仍为 **PROPOSED**。
- **PENDING**：是否提交、以何粒度提交、何时提交均未获授权。**未获授权前不得 Commit / Push。**

### 15.2 审批状态

| 文档 | 角色 | 文档自述状态 | Owner 审批状态 | Git 状态 |
|---|---|---|---|---|
| 七模块职责与依赖 | M01–M07 协作边界 | 未标注 | **Owner 已批准（2026-11-19）**，当前架构基线 | 未提交（待提交授权） |
| Personal Knowledge 对象生命周期 | M02 对象归属与生命周期 | 未标注 | **Owner 已批准（2026-11-19）**，当前架构基线 | 未提交（待提交授权） |
| 工程路线图 v1.0 | P1–P4 与首个 Task Brief | **PROPOSED** | 保持 PROPOSED | 未提交 |
| P1.M1 实施准备 | 基础设施与业务方案、接口草案、测试要求 | **PROPOSED** | 保持 PROPOSED；第一阶段实现已落盘（2026-11-20），待验收 | 未提交 |

### 15.3 技术选型授权口径

- **PROPOSED — 待 Owner 确认**：曾讨论的“折中授权制”（涉及数据外发、费用、第三方服务、长期数据格式与外部契约的事项由 Owner 决定；局部实现方案由 Agent 提出论证、经 Owner 授权后执行）目前仍是建议，**不是已批准的项目制度**。
- **CONFIRMED — Owner（2026-11-19）**：DSH 是 Implementation Agent，可在明确授权范围内自主分析、编码、测试和处理普通实现细节。该原则不改变“折中授权制”整体仍为 PROPOSED 的状态。
- **CONFIRMED**：该建议不构成对 Provider、Web 技术基线或其他未决选型的批准；PostgreSQL 已由 Owner 单独决定（§05），相关事项保持本文件既有状态不变。
- **CONFIRMED**：`docs/roadmap/p1-m1-implementation-preparation.md` 已按 v0.3 修订（2026-11-19）：采用 PostgreSQL 基线，不再包含“不需要 Owner 决策”“本次已解决”表述；路线图门禁措辞保持原文，见 15.4 CF-1。

### 15.4 口径冲突记录（含已解决与未决，不得静默改写）

| 编号 | 冲突内容 | 现状 | 处理约束 |
|---|---|---|---|
| **CF-1** | 路线图 P1.M1 依赖列要求 Owner 先确认持久化/迁移、Provider/模型、Web 基线，“不得由施工 Agent 暗选”；`human-owned-engineering.md` 允许 Agent 做可逆实现选择 | 实施准备已修订（v0.3），不再声称“不需要 Owner 决策”；路线图门禁措辞与 `human-owned-engineering.md:22` 的解释仍未统一 | 以更严格者为准；两份文本的措辞统一须 Owner 授权 |
| **CF-2** | ~~SQLite：本文件 §05/§09 为 PENDING；实施准备默认采用标准库 `sqlite3` 方案~~ | **已解决（2026-11-19）**：Owner 决定采用 PostgreSQL；本文件 §05/§09/§10 与实施准备已同步，SQLite 不再作为当前方案 | — |
| **CF-3** | Provider：实施准备曾称 Owner 已明确允许 OpenAI，仓库内无独立授权记录；初始模型 `gpt-6.2-sol` 未经仓库证据验证 | 未决；实施准备 v0.3 保持“待核实”，但授权本身仍未确认 | 保持待确认；不得把转述当作已核实授权 |
| **CF-4** | 术语 `M0.2` / `M02` 在路线图与对象生命周期文档中混用，仓库无其定义 | 未决 | 先确认指代，再统一写法；不得自行补定义 |
| **CF-5** | Frozen Scope 交付标准要求 ADR；`docs/decisions/` 为空且无模板、编号或审批人 | 未决 | 不得以其他文档替代 ADR 交付标准 |

### 15.5 当前门禁（CONFIRMED）

- P1.M1 第一阶段已获 Owner 授权并完成实现，等待验收；后续阶段未授权。
- Git Commit / Push 未获授权。
- 真实外部 LLM Provider 调用未获授权，默认 Mock。
- Owner 已受理 D1、D2；其余决策事项未表决。
