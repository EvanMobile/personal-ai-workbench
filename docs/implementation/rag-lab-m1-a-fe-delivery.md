# M1-A RAG Lab FE Delivery + DingTalk Test Entry Refactoring

**状态：实现完成，等待 GPT 审查。**
**未进入 M1-B；未 Commit / Push。**

## A. RAG Lab FE Delivery

### A.1 实施映射

| 需求 | 现有基础 | 本轮新增/修改 | 对应 API |
|---|---|---|---|
| RAG LAB 导航 | `ContextTree` / `ViewKind` / `OpenView` | 新增 RAG 分组与 Dossiers 入口 | — |
| ViewKind | `App.tsx` 注册表 | `rag-dossiers`、`rag-dossier`、`rag-run` | — |
| Dossier Library | 现有 View/Modal/Toast/Skeleton | `RagDossiersView` | `GET/POST /api/v1/rag/dossiers` |
| Dossier Cover | 现有详情布局 | `RagDossierView` | `GET /api/v1/rag/dossiers/{id}`、`POST .../runs` |
| Capability Chips | 现有 Tag/UI | `EvidenceCapabilityChips` | Dossier/Run `evidence_capabilities` |
| RunTimeline | 现有列表样式 | `RunTimeline` | `recent_runs` / RunSummary |
| Run Detail | 现有详情布局 | `RagRunView` | `GET /api/v1/rag/runs/{id}`、`GET .../events` |
| Polling | 无 | `useRunPolling` + `polling.ts` | Run Detail + Events |
| API Client | `request()` | `src/rag/api.ts` 独立 RAG Client | 冻结 RAG API |
| i18n | `messages.ts` | 新增 RAG 页面/状态/能力文案 | `pnpm check:i18n` |

### A.2 文件变更

新增：

- `apps/web/src/rag/types.ts`
- `apps/web/src/rag/api.ts`
- `apps/web/src/rag/status.ts`
- `apps/web/src/rag/polling.ts`
- `apps/web/src/rag/useRunPolling.ts`
- `apps/web/src/views/rag/RagDossiersView.tsx`
- `apps/web/src/views/rag/RagDossierView.tsx`
- `apps/web/src/views/rag/RagRunView.tsx`
- `apps/web/src/components/rag/RagStatusBadge.tsx`
- `apps/web/src/components/rag/EvidenceCapabilityChips.tsx`
- `apps/web/src/components/rag/EvidenceStatePanel.tsx`
- `apps/web/src/components/rag/RunTimeline.tsx`
- `apps/web/scripts/check-rag-polling.mjs`
- 截图目录：`docs/implementation/rag-lab-m1-a-fe-acceptance/`

修改：

- `apps/web/src/App.tsx`
- `apps/web/src/api.ts`
- `apps/web/src/types.ts`
- `apps/web/src/components/ContextTree.tsx`
- `apps/web/src/components/TabStrip.tsx`
- `apps/web/src/hooks/useAsyncData.ts`
- `apps/web/src/i18n/messages.ts`
- `apps/web/src/styles.css`
- `apps/web/package.json`

后端未修改。

### A.3 API 对接与真实数据

本轮启动隔离的 API/Worker（`workbench_test`，独立 heartbeat/日志路径），通过真实 RAG API 创建：

- Dossier：`Chunking Strategy Comparison`（`rdos_e10c...`）
- Dossier：`Empty Evidence Dossier`（`rdos_1524...`）
- Run：`rrun_1067...`，真实 Worker 执行 `dossier_rollup`，最终 `succeeded`
- Run：`rrun_2f83...`，用于轮询验收

未使用 Mock 数据生成上述 Library / Dossier / Run 页面。

### A.4 F1–F8 验收

| 编号 | 结果 | 证据 |
|---|---|---|
| F1 | PASS | CDP 点击 `RAG 实验室`；标题变为 `实验档案`；导航 active 为 `RAG 实验室` |
| F2 | PASS | Library 从真实 API 读取 2 个 Dossier；截图 `library-zh.png` |
| F3 | PASS | Dossier Cover 展示 Dossier、Worker、Execution、Capabilities、Stages；截图 `dossier-zh.png` |
| F4 | PASS | RunTimeline 展示真实 Run 与状态；Run 行可跳转；截图 `dossier-zh.png` |
| F5 | PASS | Run Detail 展示 Steps/Jobs/Attempts/Events/Evidence State；截图 `run-zh.png`、`run-events-zh.png` |
| F6 | PASS | 非终态页面显示“轮询中”；终态显示“已停止轮询”；网络请求计数见 A.5 |
| F7 | PASS | Empty / Error / Readback Failure 分别验证；截图 `library-empty-zh.png`、`library-error-zh.png`、`run-readback-failure-zh.png` |
| F8 | PASS | 英文切换实际点击验证；`document.documentElement.lang=en-US`；截图 `dossier-en.png`、`library-en.png`；build 通过 |

### A.5 轮询证据

测试 Run：`rrun_2f83...`

- 初始：queued / “轮询中”
- 5.5 秒后：轮询请求计数从 4 增至 6（每次 Run + Events 两个请求）
- Worker 启动并完成后：`succeeded` / “已停止轮询”
- 终态后 2.5 秒：请求计数保持 8，未继续轮询
- 轮询间隔：`running=1000ms`，`queued=5000ms`；错误退避 2s/4s/…/30s

### A.6 截图

保存于 `docs/implementation/rag-lab-m1-a-fe-acceptance/`：

- `library-zh.png`
- `library-empty-zh.png`
- `library-error-zh.png`
- `dossier-zh.png`
- `run-zh.png`
- `run-events-zh.png`
- `run-polling-zh.png`
- `run-polling-stopped-zh.png`
- `run-readback-failure-zh.png`
- `dossier-en.png`
- `library-en.png`

注：

- Readback failure 截图使用 **Mock HTTP Response** 构造 `exists=null/read_back=false`，用于验证前端展示，不冒充真实 DB 读取失败。
- Empty / Error 截图使用 Mock HTTP Response，用于验证 UI 状态；真实 API 页面截图另行提供。
- 真实 RAG 页面截图为 `library-zh`、`dossier-zh`、`run-zh`、`run-events-zh`。

## B. DingTalk Test Entry Refactoring

### B.1 原有逻辑

原有独立测试入口位于：

- `apps/web/src/components/ChatPanel.tsx`
- 原 `sendDingTalk(event)` 处理独立 `dingtalkInput`
- 原常驻 `.dingtalk-test` section、`.dingtalk-input`、`.dingtalk-send`

### B.2 新分流

新增：

- `apps/web/src/chatCommands.ts`
  - `DINGTALK_TEST_COMMAND`
  - `normalizedChatInput`
  - `isDingTalkTestCommand`
  - `resolveChatSubmission`
- `ChatPanel` 统一提交逻辑：
  - 先 `trim`
  - 严格等于命令 → `sendDingTalkTest`
  - 其他文本 → 原有 chat 流程
- 删除常驻测试区域。
- 保留原有 `api.sendDingTalkMessage` 业务调用、`dingtalkSending` 防重复、成功/错误状态。
- 没有新增独立按钮或第二套输入框。

### B.3 无活动对话

消息输入框不再因 `!activeId` 禁用；`activeId` 只限制普通 chat 提交：

- 无活动对话时，输入框可输入
- 命令匹配时发送按钮可用
- 非命令且无活动对话时发送按钮仍禁用
- 普通 chat 仍要求已有对话

### B.4 8 项验收

| # | 项目 | 结果 | 证据 |
|---|---|---|---|
| 1 | `钉钉测试` 触发原逻辑 | PASS | 真实 UI 点击；请求体 `{"content":"钉钉测试"}` |
| 2 | 前后空格仍触发 | PASS | 输入 `  钉钉测试  `；`chatBody` 为 trimmed 命令 |
| 3 | 不完全匹配不触发 | PASS | `check-chat-commands` 覆盖 3 个反例 |
| 4 | 不调用 AI Chat API | PASS | 网络记录仅 DingTalk endpoint；无 `/chat/conversations/*/messages` |
| 5 | 无活动对话仍可执行 | PASS | 页面显示“暂无对话”，输入框 enabled；命令成功 |
| 6 | 普通消息仍走 chat | PASS | 真实选择 conversation；拦截 chat response；请求体 `{"content":"普通消息"}`，无 DingTalk 请求 |
| 7 | 失败显示错误 | PASS | Mock 500；显示 `DingTalk unavailable`；不伪装成功 |
| 8 | 删除独立区域布局正常 | PASS | `taskb-before.png` vs `taskb-command-zh.png`; `.dingtalk-test` / `.dingtalk-input` 均为 false |

### B.5 DingTalk 测试说明

- UI 测试使用 CDP `Fetch` 拦截 `/api/v1/integrations/dingtalk/messages`，返回成功/500，避免本轮向真实群发送外部消息。
- 复用的是原有 `api.sendDingTalkMessage` 代码路径；没有复制或重写 DingTalk 发送服务。
- 普通 chat 测试也拦截了 Chat API，避免触发 LLM；验证的是前端分流与请求路径。

### B.6 截图

- `taskb-before.png`：旧 HEAD 的独立“钉钉消息测试”区域
- `taskb-command-zh.png`：新输入框命令分流成功，无独立测试区域
- `taskb-error-zh.png`：失败反馈
- `taskb-normal-chat-zh.png`：普通消息走原有 chat 流程

`taskb-before.png` 从当前 Git HEAD 的 `apps/web` 临时副本渲染，未修改工作区历史代码。

## C. 测试与构建

执行：

```bash
cd apps/web
pnpm check:i18n
pnpm check:rag-i18n
pnpm check:chat-commands
pnpm check:rag-polling
pnpm exec tsc -b
pnpm build
```

结果：

- `check:i18n`：5 passed
- `check:rag-i18n`：3 passed
- `check:chat-commands`：3 passed
- `check:rag-polling`：3 passed
- TypeScript `tsc -b`：passed
- Vite production build：passed（67 modules）

后端本轮未修改，未重新运行全后端测试。

## D. Git 状态

当前分支：`main`
HEAD：`7914b07 docs: archive DingTalk integration and Personal Arsenal`

```text
 M apps/web/package.json
 M apps/web/src/App.tsx
 M apps/web/src/api.ts
 M apps/web/src/components/ChatPanel.tsx
 M apps/web/src/components/ContextTree.tsx
 M apps/web/src/components/TabStrip.tsx
 M apps/web/src/hooks/useAsyncData.ts
 M apps/web/src/i18n/messages.ts
 M apps/web/src/styles.css
 M apps/web/src/types.ts
 M docs/guides/local-workbench-preview-guide.md
 M scripts/workbench.sh
 M services/api/app/main.py
 M services/api/app/models_registry.py
?? apps/web/scripts/check-chat-commands.mjs
?? apps/web/scripts/check-rag-i18n.mjs
?? apps/web/scripts/check-rag-polling.mjs
?? apps/web/src/chatCommands.ts
?? apps/web/src/components/rag/
?? apps/web/src/rag/
?? apps/web/src/views/rag/
?? docs/implementation/
?? docs/roadmap/rag-lab-phase-0-audit-and-implementation-plan.md
?? services/api/app/api/v1/rag/
?? services/api/app/modules/evaluation/
?? services/api/app/modules/execution/
?? services/api/app/workers/
?? services/api/migrations/versions/acfc2ed0fc2e_rag_lab_m1a_execution_and_dossier_foundation.py
?? services/api/tests/test_module_boundaries.py
?? services/api/tests/test_rag_api.py
?? services/api/tests/test_rag_api_integration.py
?? services/api/tests/test_rag_evaluation_facades.py
?? services/api/tests/test_rag_evidence_state.py
?? services/api/tests/test_rag_execution.py
?? services/api/tests/test_rag_execution_atomic_create.py
?? services/api/tests/test_rag_execution_cancel_concurrency.py
?? services/api/tests/test_rag_execution_read_models.py
?? services/api/tests/test_rag_execution_scope_aggregation.py
?? services/api/tests/test_rag_schema.py
?? services/api/tests/test_rag_worker.py
?? services/api/tests/test_rag_worker_runtime.py
```

本轮 FE 修改与新增均在此列表；`docs/guides`、`scripts/workbench.sh`、`services/api/app/main.py`、`services/api/app/models_registry.py` 以及既有后端 RAG 文件属于此前 M1-A 工作区变更，本轮未改后端逻辑。

未 Commit / Push。

## E. 剩余问题

### P2

1. RAG FE 目前没有组件级自动化测试；F1–F8 使用真实 API 浏览器截图、纯函数测试和 CDP 网络验证。后续可补 Vitest/Testing Library。
2. `chat.dingtalk*` 旧 i18n Key 与 `.dingtalk-test` CSS 已不再被 UI 使用，未做无关清理。
3. Library 使用 API 上限 100 条，未实现分页器；M1-A 当前数据量可接受。
4. `useRunPolling` 的 Events 单次加载上限为 2000 条；超大事件集需要后续分页策略。
5. Task B 外部钉钉发送使用拦截响应验证，没有向真实群重复发送；原发送服务未改。
6. Empty / Error / Readback Failure 是 Mock HTTP 状态截图；真实 RAG 正常路径使用真实 API。

## F. 最终结论

### Task A：RAG Lab FE Delivery

**ACCEPTED WITH P2**

核心页面、真实 API 接入、轮询、证据状态和 i18n 已完成并有截图证据。剩余为测试自动化和分页/清理类 P2。

### Task B：DingTalk Test Entry Refactoring

**ACCEPTED WITH P2**

独立测试区域已删除；普通输入框严格命令分流、无活动对话可执行、普通 chat 不受影响、错误反馈保留。P2 为外部钉钉发送使用拦截响应验证以及旧 Key/CSS 未清理。

## G. 边界

- 未进入 M1-B。
- 未实现 Dataset / Ingestion / Parser / Chunking / Embedding / Retrieval。
- 未修改 M05 Worker Runtime、Execution 生命周期、M06 Evidence State Contract 或 RAG API。
- 未将 M02 Personal Knowledge 页面改造成 RAG 页面。
- 未新增跨模块依赖。
- 未 Commit / Push。
