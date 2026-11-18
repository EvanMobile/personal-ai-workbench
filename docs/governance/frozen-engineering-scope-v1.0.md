# Personal AI Workbench — Frozen Engineering Scope v1.0

**状态：DECIDED — Project Owner 已批准冻结。**

本文件记录本轮工程施工边界。施工中发现的新需求可以进入后续观察清单；超出七个模块及既定能力矩阵的工作，必须先经 Project Owner 明确批准，不自动扩大本轮范围。

## 一、七个施工模块

### 1. Product Showcase：完整产品呈现

**目标：**不是一个只有 API 的后端 Demo，而是一个能够实际使用的个人 AI 工作台。

- Web FE：主控制中心、对话入口、Card Library、Dossier、Workflow Monitor、Runtime Console。
- Android App：移动端展示、通知、任务状态。
- 钉钉外接：消息通知和必要的任务交互。
- Personal Knowledge：核心产品。
- Personal Arsenal、Project Replay：允许为空，不强行填充。

**验收：**能够从 Web 发起任务，在后端执行，通过移动端和钉钉看到任务状态及结果。

### 2. Personal Knowledge：Card Generation & Knowledge Workflow

这是整个产品的核心业务。

- Capture：知识输入，支持 URL、文本、文档等来源。
- Digest：内容解析、知识分析、结构化处理。
- Card Generation：生成 Evidence Card。
- Knowledge Administrator Agent：分类、相似卡发现、Dossier 匹配、待审核项。
- Dossier：物理 Chunking，扉页结论 Card + Supporting Cards。
- Synthesis：多个 Card 的集中消化、综合推理。
- Publish：生成独立、持久化、可追溯的结论资产。
- 版本快照：旧结论保留，新认知形成 V2，不覆盖历史。

### 3. RAG & Agent Harness：重点 Showcase

- Embedding。
- Vector Database。
- Chunking、Top-K、检索和必要的 Rerank。
- Context Engineering。
- RAG Retrieval Pipeline。
- Agent Harness：上下文、工具、状态、执行环境、权限边界、控制循环。
- 轻量化集成，不重新造一套 RAG 或 Agent 框架。
- 保留后续扩展空间。

重点是让 RAG 真正服务于知识卡片分类、检索、Dossier 消化，而不是单独做一个问答 Demo。

### 4. Agent Engineering

- Agent Workflow。
- Agent Loop。
- LangChain / LangGraph 轻量化应用。
- Tool Calling / Function Calling。
- Agent Skills：稳定、可复用的任务逻辑。
- Human-in-the-loop。
- 多模型协作和任务交接。
- 两步模型降级：GPT → DeepSeek。
- 结果质量验收与失败处理。

不制造一堆互相聊天的 Agent，不为了展示 Multi-Agent 而扩大系统。

### 5. Python Backend & Infrastructure

- Python 工程分层。
- FastAPI、Pydantic、API 设计。
- Async / Sync、Python threading。
- 数据持久化、任务状态管理。
- 定时任务、后台任务。
- Redis、MQ：根据真实场景选择性落地。
- 重试、超时、限流等必要机制。
- 日志、异常处理、可观测性。
- 文档解析、内容结构化、AI 内容生成。
- Provider Adapter 与统一模型调用接口。

这里明确遵守简历能力矩阵上限：复杂分布式架构、Kubernetes 运维等不作为实际施工目标。

### 6. Evaluation & Quality Engineering

- Prompt Engineering：
  - Zero-shot / Few-shot
  - Chain-of-Thought
  - Self-Consistency
  - Role-playing
- LLM Evaluation。
- RAG Retrieval Evaluation。
- Agent Workflow Evaluation。
- 准确性、一致性、效率、安全性。
- Benchmark、测试集、失败案例。
- Quality Threshold。
- Evaluation Run、Evaluation Card、Evaluation Snapshot。
- Human-in-the-loop 质量审核。

不追求证明 LLM 100% 正确，而是建立可解释、可复现的质量验收过程。

### 7. LLM Provider Integration & Usage Tracking

- GPT、DeepSeek 等 Provider 集成。
- 统一调用接口。
- 模型选择与简单路由。
- 两步降级机制。
- Prompt Package 跨模型交接。
- 统一 Usage 记录。
- Input / Output / Cached / Reasoning Tokens（Provider 支持时）。
- 模型价格表及版本。
- 单次调用费用估算。
- 累计 Token 和费用展示。
- 模型调用记录与 Card / Workflow 关联。

不建设多租户模型调度平台，不做复杂 FinOps。

## 二、产品级工程要求

这部分不是第八个功能模块，而是上述模块必须共同遵守的工程约束。

| 原则 | 冻结要求 |
|---|---|
| Portable by Design | 代码与数据分离，支持全量备份、恢复和迁移。 |
| Card-Centric | Card 是最小知识资产。 |
| Dossier Physical Chunking | Dossier 是知识组织与检索边界。 |
| Provenance-Aware | 重要结论保留来源、模型、时间和处理线索。 |
| Reuse First | 优先复用成熟框架与工具。 |
| Agent Governance | 遵守 `PROJECT_CONTEXT.md`、分层 CR、控制 Agent 施工范围。 |
| Extensibility | 保留合理扩展点，不提前建设不存在的需求。 |

特别强调：全量备份不等于只备份数据库。原始附件、知识资产、必要配置、数据库迁移信息和索引重建能力都要纳入恢复方案，最终必须做一次实际恢复演练。

## 三、最终交付标准

完成标准不是写了多少代码，而是 GitHub 上能够证明什么。交付物必须达到以下状态：

| 交付物 | 要求 |
|---|---|
| 源代码 | 结构清晰、可运行。 |
| README | 产品定位、架构、运行方式、功能说明。 |
| `PROJECT_CONTEXT.md` | Agent 施工上下文与治理规则。 |
| Architecture Docs | 核心架构和数据流。 |
| ADR | 重要技术选型和取舍。 |
| Tests | 核心业务逻辑和关键流程有测试。 |
| Demo | 能够实际演示核心业务闭环。 |
| Evaluation Records | 有真实测试结果和失败案例。 |
| Recovery Test | 异机或干净环境恢复验证。 |
| Showcase | Web + Android + 钉钉联动。 |

## 四、明确冻结的范围边界

以下内容不进入本轮施工：

- Coding Agent / Coding Harness 自研。
- 多租户 SaaS 平台。
- 多级复杂模型路由与自动调度。
- 为了展示而构造 Multi-Agent 群聊。
- 完整企业级 FinOps。
- 复杂分布式一致性体系。
- Kubernetes 生产运维体系。
- 没有真实业务价值的技术栈堆叠。
- 为了填充产品而强行建设 Personal Arsenal 和 Project Replay。

施工中可以产生新的 Spark，但必须先判断是否落在这七个模块及既定能力矩阵内。超出范围的，进入后续观察清单，不自动扩大本轮施工。

## 五、关于 90% 面试覆盖的判断

对于 Senior AI Application Engineer、Senior Agent Engineer、AI Application Architect 这几个目标方向，这套项目范围已经覆盖了非常高比例的核心能力考察面。

但有个区别：

- 做出来：证明你具备实现能力。
- 有架构文档：证明你能解释设计。
- 有 Evaluation：证明你理解质量管理。
- 有取舍记录：证明你具备架构判断力。
- 能现场演示：证明这些不是简历上的概念堆砌。

它不能替代所有企业生产经验，也不能保证每个面试官都认可，但足以成为一套有说服力的个人工程作品。

本轮施工范围自 v1.0 起冻结。只有在实际施工遇到问题、发现能力缺口时，才允许针对性调整；任何范围调整仍须 Project Owner 明确批准。施工顺序应依据模块依赖关系制定。
