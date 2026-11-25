# M1-A RAG Lab FE Delivery

**状态：RAG Lab FE 交付验收记录。**

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

## B. 测试与构建

```bash
cd apps/web
pnpm check:i18n
pnpm check:rag-i18n
pnpm check:rag-polling
pnpm exec tsc -b
pnpm build
```

结果：

- `check:i18n`：5 passed
- `check:rag-i18n`：3 passed
- `check:rag-polling`：3 passed
- TypeScript `tsc -b`：passed
- Vite production build：passed（67 modules）

真实 RAG 页面使用隔离 API/Worker 和 `workbench_test` PostgreSQL；
Readback Failure / Empty / Error 使用 Mock HTTP Response，已在上方明确区分。

## C. 范围与限制

- 未进入 M1-B；未实现 Dataset / Ingestion / Parser / Chunking /
  Embedding / Retrieval。
- 未修改 M05 Worker Runtime、Execution 生命周期或 M06 Evidence State
  Contract。
- 未将 M02 Personal Knowledge 页面改造成 RAG 页面。
- 已知 P2：RAG FE 无组件级自动化测试；Library 上限 100；Events
  单次轮询上限 2000；Library 无分页器。
- DingTalk Test Entry Refactoring 属于独立变更，不在本 RAG-only
  文档提交范围内。
