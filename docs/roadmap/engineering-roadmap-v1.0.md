# Personal AI Workbench 1.0 工程路线图

**状态：PROPOSED — 提交 Project Owner 审阅。**

> 状态说明：本路线图保留其规划语境。后续已单独交付 DingTalk 手动 Webhook 消息测试及真实送达验证（`99463fa`），但这不等同于 P4 所述 Web + Android 的任务状态展示闭环；当前实现记录见 [`PROJECT_CONTEXT.md`](../../PROJECT_CONTEXT.md)。

本路线图承接 Frozen Engineering Scope v1.0 和 M0.2 明确的七模块职责，不增加模块或产品范围。Page、Working Session 等是 Owner 在 M0.2 中给出的 M02 产品定义细节，本路线图不据此修改冻结文件。路线以尽早形成可用的 Personal Knowledge Web 纵向切片为先；高级 RAG、Android、DingTalk 和完整评测能力按依赖逐步补齐。数据库、ORM、模型/Provider、Web 技术栈等未决项不在本路线图中擅自选定。

## Phase 总览

| Phase | 目标 | 完成标志 |
|---|---|---|
| **P1 — Knowledge Vertical Slice** | 从文本接入到显式 Publish 的端到端知识闭环，提供最小 Web Card Library。 | 用户能提交文本、审阅/讨论 Card Draft、明确 Publish，并在 Card Library 查看持久化 Card；Raw Content 与 Card 分别保存。Owner 在 Milestone Task Brief 批准时确认 Learning Gate 等级与证据。 |
| **P2 — Dossier, Page & Working Session** | 建立知识组织、独立学习会话和版本化 Page 消化体验。 | Dossier 能组织 Card；Working Session 与 Main Context 分离；Page 能加载、追溯来源、提示变化并经用户确认后生成新版本。各 Milestone 的 Learning Gate 由 Owner 在对应 Task Brief 中确认。 |
| **P3 — Retrieval, Agent & Evaluation Quality** | 让 RAG/Agent 支撑真实知识任务，并建立可复现的质量验证。 | 检索、Skill/Workflow、Evaluation Run 与质量结论能关联；人工审核和失败记录有效。各 Milestone 的 Learning Gate 由 Owner 在对应 Task Brief 中确认。 |
| **P4 — Full Showcase & Portable Delivery** | 补齐 Android、DingTalk、运行态呈现及完整备份恢复。 | Web + Android + DingTalk 展示任务状态和结果；干净环境/异机 Restore Drill 恢复完整工作状态。各 Milestone 的 Learning Gate 由 Owner 在对应 Task Brief 中确认。 |

Phase 顺序优先保障可用业务闭环。P2 的 Page 生成可采用经批准的轻量上下文组织方式，不要求先建完整 RAG 平台；P3 再按已观察到的检索与质量需求深化 M03/M04/M06。Portable by Design 从 P1 的资产/文件边界考虑，完整备份与真实恢复验收在 P4 完成。

## Phase → Milestone → Task

### P1 — Knowledge Vertical Slice

| Milestone | 结果 | 依赖 / 决策门 |
|---|---|---|
| **P1.M1 — Text Ingestion & Card Generation v0.1** | 完成下文 Task Brief 的知识接入、Card Draft、人工讨论/修订、显式 Publish 和 Web Card Library 闭环。 | Owner 先确认持久化/迁移方案、Provider/模型调用方案及 Web 技术基线；不得由施工 Agent 暗选。 |
| **P1.M2 — Provenance & Version Baseline** | Raw Content、Card 版本和 Publish 记录具备可追溯关系；旧版本不被覆盖。 | P1.M1 的实际资源语义和用户体验。 |
| **P1.M3 — Minimal Workflow Visibility** | Web 能展示接入/生成/待人工处理/完成等用户需要的任务状态。 | 使用 P1 已有任务状态，不预建通用 Runtime Console。 |

近期执行顺序建议：先完成 P1.M1 前置决策 Task，再实施 v0.1 纵向切片；P1.M2 和 M3 在实现中若已有必要证据可并入，不扩大到通用平台能力。

### P2 — Dossier, Page & Working Session

- **P2.M1 — Dossier & Card Organization：**用户可建立 Dossier 并组织正式 Card，Dossier 成为 Page 的 Context Boundary。
- **P2.M2 — Working Session：**独立保存会话历史、上下文清单、执行记录和必要 Sparks；支持围绕 Dossier 复习、讨论和提出 Change Set；知识修订须用户确认并 Publish。
- **P2.M3 — Versioned Dossier Page：**一个 Dossier 对应一个主 Page；优先加载最近有效 Page，保留页面版本和来源 Card/版本、Renderer Skill/Prompt、模型及生成信息；源 Card 变化时显示醒目提示，用户确认后才生成新版本。1.0 不做可视化 Page 编辑器。

### P3 — Retrieval, Agent & Evaluation Quality

- **P3.M1 — Retrieval Support：**按 M02 已出现的分类、检索、Dossier 消化场景建设必要的 Chunking、Embedding、Vector DB、Top-K/Rerank 与 Context Engineering。
- **P3.M2 — Agent/Skill Runtime：**实现必要的 Workflow/Loop、Tool Calling、Human-in-the-loop、公共 Skill 加载/版本解析/执行和失败处理；业务 Skill 仍归 M02 或 M06。
- **P3.M3 — Evaluation Baseline：**建设独立 Evaluation Cabinet/Dossier、Testset、Evaluation Run、指标/阈值、失败案例与 Human Review；有价值的结论经用户确认 Publish 成 M02 Card。
- **P3.M4 — Provider Usage Visibility：**统一 Provider 调用记录及可获得的 Token、Cost、Latency；基础选择/Fallback 按实际需要实施，不建设复杂动态路由或完整 FinOps。

这些 Milestone 可按真实调用依赖交错推进；不要求先完成所有 M03/M04/M07 能力再做业务。P1 未验证的高级 RAG/Agent/Evaluation 能力不提前施工。

### P4 — Full Showcase & Portable Delivery

- **P4.M1 — Android & DingTalk Showcase：**围绕已运行的知识工作流提供任务状态、通知和必要交互；核心业务逻辑仍留在业务/API 服务。
- **P4.M2 — Workflow Monitor & Runtime Console：**根据已有任务、模型调用和运行记录呈现必要状态，不重复建设已有业务审计。
- **P4.M3 — Backup & Restore Readiness：**备份覆盖数据库、原始附件、知识资产、必要 Skills/Prompts/配置、迁移信息和索引重建能力。
- **P4.M4 — Restore Drill & End-to-End Acceptance：**在干净环境或异机 Clone 仓库、恢复备份、启动服务，验证完整工作状态；演示 Web 发起任务并在 Android 与 DingTalk 查看状态/结果。

## 首个业务施工 Task Brief（待 Owner 批准）

### 标题

**P1.M1 — Knowledge Ingestion & Card Generation Pipeline v0.1**

### 目标与范围

实现 Personal Knowledge 的第一个可用文本纵向切片：用户提交标准化可读文本与来源元数据；系统分别持久化 Raw Content 与 Card；运行基础 Capture/语义分析和 Digest Skill/LLM，产出 Card Draft；用户可在 Draft 范围内与 LLM 讨论并修正；只有用户明确执行 Publish 才形成正式 Card；Web Card Library 展示已发布 Card。该讨论能力只服务于 Card Draft，不提前实现完整的独立 Working Session（Dossier 上下文、通用复习/探索及 Sparks 工作流属于 P2）。

v0.1 只接收文本。Raw Content 与 Card 分开保存；所有生成/讨论/修订路径均不能自动 Publish。保持精简，复用仓库现有结构和资产。

### Task 范围与前置决策

**前置决策 Task（编码前由 Owner 决定）：**

1. 确定持久化数据库、迁移策略和原始文本/附件存储边界。当前项目无数据库或 ORM 实现，`PROJECT_CONTEXT.md` 将 SQLite 标记为 PENDING；本 Brief 不预选技术。
2. 确定 Provider、模型配置和调用凭证的管理方式。当前无 Provider Adapter 或模型依赖；此决定不得将密钥写入仓库。
3. 确定 Web 技术基线和开发/运行方式。当前 `apps/web/` 无客户端代码或构建配置。
4. 确认 Skill 执行方案：`skills/knowledge-analysis/SKILL.md` 是现存知识分析指令文档，不等同于已实现的 Skill Runtime；可复用其内容，但公共加载/版本解析/执行入口尚未实现。
5. 在 Milestone 批准时确认 Learning Gate 的 Knowledge Mastery 等级及证据要求；Agent 不得依据代码完成或测试通过自行判定 Gate 已通过。

Owner 确认以上选择后，施工 Task 可按 Backend persistence/API、Digest/LLM draft 与讨论、Web submission/review/Library 三条协作子任务执行；各子任务共享本 Milestone 的资源契约，不各自另建模型或运行时。

### 相关现有文件与模块

- Capture API：`services/api/app/api/v1/client/ingestion/captures.py`、`services/api/app/schemas/capture.py`、`services/api/app/services/capture_service.py`。当前只校验请求并返回临时 `capture_id`，不持久化或执行处理。
- API 入口和测试：`services/api/app/main.py`、`services/api/tests/test_capture.py`、`services/api/tests/test_health.py`。
- API 依赖/运行约定：`services/api/pyproject.toml`、`services/api/README.md`。当前没有数据库、Web、LLM Provider 或 Agent Runtime 依赖。
- 可复用的知识分析指令材料：`skills/knowledge-analysis/SKILL.md`；不能把它描述为已执行的 Skill。
- 产品语义：`products/personal-knowledge/README.md`；M02 Page/Working Session 细节见本次对象生命周期文档。

### 预期行为

1. Web 提交文本和来源元数据；API 创建 Raw Content 与可追踪的接入/处理状态。
2. Digest 读取 Raw Content，生成 Card Draft，并记录必要的来源、Skill/Prompt、模型和时间信息。
3. 用户在 Web 查看 Draft，可请求 LLM 协助讨论/修订；每次结果仍是 Draft/候选变更。
4. 未经用户显式 Publish，不创建正式 Card、不出现在 Card Library。
5. Publish 后保存正式 Card 和版本/Publish 记录；Raw Content 保留且可追溯，Card 内容不覆盖原始输入。
6. Web Card Library 能查看已发布 Card；至少能打开 Card 并回到对应来源信息。
7. 失败或待人工处理状态可见；不得把模型调用成功等同于发布成功。

### 验收标准

- 从 Web 提交一段文本及来源元数据，获得可查看的处理状态。
- Raw Content 与 Card Draft/正式 Card 独立持久化；应用重启后记录仍可读取。
- Digest 输出形成 Draft，并能说明其来源 Raw Content 与所用 Skill/Prompt、模型等可用生成信息。
- 用户能够审阅 Draft，并进行至少一轮 LLM 辅助讨论或修订；修订不会静默覆盖已发布版本。
- 未点击/确认 Publish 时，Card Library 中没有该正式 Card；明确 Publish 后出现对应 Card 和可追溯版本记录。
- 失败路径有明确状态/错误反馈，不误报成功或自动 Publish。
- 完成一次 Web → API/Service → 持久化 → Digest/LLM → 人工确认 → Card Library 的端到端演示。
- 达到 Project Owner 为本 Milestone 确认的 Knowledge Mastery 等级，并由 Owner 根据相应证据完成 Learning Gate 与 Milestone Capability Review。

### 测试要求

- 单元测试覆盖 Raw Content 与 Card 分离、Draft 生成/修订、显式 Publish、版本保留及来源追踪关键规则。
- API/集成测试覆盖文本提交、状态查询、Draft 获取/修订和 Publish；验证“模型完成但未人工确认”不会产生已发布 Card。
- Web 验收覆盖提交、审阅/讨论、明确 Publish、Library 展示及错误状态。
- 持久化测试验证应用重启后 Raw Content、Card 和 Publish 记录仍可读取。
- 不得声称未执行的测试通过；新增测试遵循相关代码 Review 深度和现有测试规范。

### 文档更新要求

- 更新 API README 与 Web 运行说明，记录实际可用功能、配置和限制。
- 更新 Personal Knowledge 产品/架构文档，说明 Raw Content、Draft、Card、Publish 的真实生命周期及来源链。
- 对 Owner 批准的数据库、Provider、Web 基线等重要选型记录 ADR；未批准的选择不得写成决定。
- 按实际实现更新 `PROJECT_CONTEXT.md` 状态；区分已实现、已决定和未决内容。

### 明确排除项

- URL、PDF、Word、视频及其他内容适配器。
- RAG/Vector DB、复杂 Chunking/Reranking、通用 Agent Harness 或多 Agent 群聊。
- Knowledge Administrator 的自动分类、相似卡推荐或自动 Dossier 匹配。
- Dossier Page 生成、独立 Page 编辑器、Android、DingTalk。
- 完整独立 Working Session；本 Milestone 仅包含围绕 Card Draft 的讨论/修订交互。
- 自动 Publish、自动覆盖历史版本、未经确认的知识修改。
- 多租户、复杂分布式架构、复杂模型路由/调度和完整 FinOps。
- 在 Owner 决策前选定数据库/ORM/Provider/Web 框架或加入相关依赖。

本 Task Brief 仅供 Owner 审阅与批准；本次 M0.2 规划任务不启动上述编码施工。

## 待决事项

- Python 基线、数据库/ORM/迁移、附件存储仍遵循 `PROJECT_CONTEXT.md` 的 PENDING 状态。
- Provider、模型、凭证配置、Web 技术栈和 Skill Runtime 尚无批准选型。
- Capture 是否单独持久化、任务失败重试/幂等、Card 字段与版本模型需由 P1 决策 Task 在不扩展本范围的前提下明确。
- Page 的图文组件表达、来源变化影响判断、Skill/Prompt 版本固定方式属于 P2 设计任务；本规划不提前设计其实现。
- Evaluation Cabinet 与普通 Personal Knowledge 的授权/发布边界已确认；实验数据具体保留策略待后续设计。
