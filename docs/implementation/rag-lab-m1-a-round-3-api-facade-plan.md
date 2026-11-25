# RAG Lab M1-A Round 3 — API / Facade 施工计划

**状态：REVISED PROPOSED — 已吸收 GPT Review Corrections；等待最终审查与 R3.1 施工授权。本轮只做计划，不编码。**

- 编制依据：`docs/roadmap/rag-lab-phase-0-audit-and-implementation-plan.md`（当前仓库实际文件名；任务描述中的 `...plan(3).md` 不存在，见 §12）
- 已验收基线：M1-A Round 1 Schema/Migration；M1-A Round 2 Execution Engine & Worker
- 当前基线测试：77 passed（Schema 16 + Execution 9 + Worker 14 + 既有 38）
- 本轮禁止：修改业务代码、Schema、Migration、API、Facade、FE；不得 Commit/Push
- 依赖方向：`M01 → M06 → M05`（M1-A 不使用 M03）

---

## 0. 计划范围

Round 3 只补齐 M1-A 的 **M01 产品 API + M06 用例 Facade + M05 公共读取/原子创建边界**，使 API Client 或后续 FE 可以：

1. 创建/列出/读取 RAG Dossier。
2. 读取 Dossier Cover 的组合读模型与执行状态。
3. 触发 `dossier_rollup` Run。
4. 读取 Run / Step / Job / Attempt 的执行信息。
5. 按游标读取 Execution Event。
6. 取消 Run。
7. 读取 Worker 进程可用性。

**不包含：** M1-B Dataset/文件/PDF、Chunking/Embedding/Retrieval/Evaluation、Artifact/Verification、FE、鉴权/多租户。

### 0.1 已批准决策（不再作为待决事项）

以下四项已经 GPT 正式批准，施工必须按此执行，不得重新讨论：

| ID | 已批准决策 | 施工落点 |
|---|---|---|
| **D1** | `pipeline="dossier"`、`stage="dossier_rollup"` | M06 `start_dossier_rollup`；R3.1 同步修正现有测试夹具中的 `pipeline="dataset"` 构造值 |
| **D2** | Worker 不在线仍持久化创建 Run + Step + Job；新建请求返回 **202**；响应 `worker_available=false` + `WORKER_UNAVAILABLE` warning；202 不代表已执行 | M05 原子创建不检查 Worker 在线；M06 返回 WorkerSnapshot/warning；不返回 503 |
| **D3** | `POST /dossiers/{id}/runs` 的 `Idempotency-Key` 必填；同 Key 同 Payload 返回已有 Run；同 Key 不同 Payload 返回 409 | M05 原子创建 + canonical payload hash + 唯一约束；M06 映射 409 |
| **D4** | M1-A 不提供独立 Stage API；Stage 状态内嵌 Dossier Detail | 不新增 `GET /dossiers/{id}/stages/{stage}`；DossierFacade 组合 M05 聚合 |

**注意：** D1 的测试夹具修正必须在 R3.1 编码阶段执行；本任务只修改计划，不修改测试代码。

---

## 1. 当前代码结构与职责审计

### 1.1 已落地能力

| 模块 | 现状 | 位置 |
|---|---|---|
| M05 Execution | 六张表、Claim/Lease/Heartbeat/Recovery/Fencing、状态聚合、Cancel、Worker | `services/api/app/modules/execution/` |
| M05 写路径 | `create_run()` / `create_step()` / `create_job()` / `claim_job()` / `finish_job()` / `fail_job()` / `request_cancel()` | `execution/service.py:63,134,157,212,429,492,684` |
| M05 Worker | `Worker`、`JobContext`、`JobHeartbeat`、`ProcessHeartbeat` | `execution/worker.py` |
| M06 Dossier | `RagDossier` 模型 | `evaluation/models.py:14` |
| M06 Handler | `dossier_rollup` 真实 Handler | `evaluation/handlers/dossier_rollup.py:13` |
| Worker CLI | `python -m app.workers.rag_worker` | `app/workers/rag_worker.py` |
| 脚本 | `workbench.sh` 已支持 worker 启停/status/logs | `scripts/workbench.sh` |
| 测试 | 77 passed | `tests/test_rag_schema.py`、`test_rag_execution.py`、`test_rag_worker.py` |

### 1.2 当前缺口

1. **没有 `/api/v1/rag` Router**；`main.py:45-51` 只注册既有 7 个 Router。
2. **M06 没有 Facade / read model / Dossier service**；当前只有 `RagDossier` 模型和 `dossier_rollup` Handler。
3. **M05 没有公共读取 DTO**；Run/Step/Job/Attempt/Event 只能由测试或 Handler 直接查询 ORM。
4. **M05 的创建函数分开 commit**：`create_run`、`create_step`、`create_job` 各自提交。若 Facade 依次调用，可能留下“Run 已创建但没有 Step/Job”的部分状态；相同 Idempotency-Key 重试会返回这个不完整 Run。
5. **没有原子 `Run + Step + Job` 创建入口**，API 无法在不复制 M05 逻辑的前提下安全触发一次 Job。
6. **Worker 进程心跳只写文件**（`.run/worker.heartbeat`），没有 API 读取；FE 无法判断 Worker 是否在线。
7. **没有统一 RAG API 错误 envelope**；既有 Router 使用 `HTTPException(detail=...)`，而 Phase 0 要求稳定 `{code, message, recoverable}`。
8. **没有 Dossier read model**；Dossier 状态、最近 Run、Stage 状态、统计、阻塞原因、下一步动作均未定义。
9. **`dossier_rollup` 的结果包含全局 `dossier_count`**，不是 Dossier 维度统计；Dossier Cover 不能直接照搬 Handler result。
10. **Cancel 的幂等语义未定义**：已有 `request_cancel()` 会重复写 `cancel_requested_at` 和 Event；必须由 M05 在锁内保证并发幂等，M06 不得复制取消状态机。

### 1.3 依赖边界审计

| 检查 | 结果 |
|---|---|
| M05 是否 import M06/M03 | 否；`execution/*` 只 import `app.core` 和 execution 自身 |
| M06 是否可调用 M05 | 是；`dossier_rollup` Handler 已 import M05 Handler 契约/模型，方向合法 |
| M03 是否参与 M1-A | 否 |
| M01 是否已有直接 ORM 写入 | 现有 Router 通过 Service 写；新 `/rag` 不得引入直接写 |
| 是否存在跨模块直接写表 | 当前无；Round 3 必须保持 |

**结论：现有边界基本正确；Round 3 的 Facade 必须只调用 M05 公开 Service，不得在 M06 直接写 `execution_*`。**

---

## 2. Phase 0 要求映射

| Phase 0 要求 | Round 3 落点 |
|---|---|
| §12.6 `GET/POST /rag/dossiers` | `DossierFacade` + `api/v1/rag/dossiers.py` |
| §12.6 `GET /rag/dossiers/{id}` | Dossier Cover read model |
| §12.6 `POST /rag/dossiers/{id}/runs` | `ExecutionFacade.start_dossier_rollup` + M05 原子创建 |
| §12.6 `GET /rag/runs/{id}` | RunDetail read model |
| §12.6 `GET /rag/runs/{id}/events` | Event cursor API |
| §12.6 `POST /rag/runs/{id}/cancel` | M05 `request_cancel` + M06 error mapping |
| §12.6 `GET /rag/runtime/worker` | M05 heartbeat 文件读取 + M06 WorkerSnapshot |
| §12.6 Idempotency | `Idempotency-Key` + canonical payload hash |
| §12.6 `evidence_capabilities` | 固定 N/A 能力常量，不伪造 Artifact/Verified |
| §12.7 FE/i18n 契约 | 稳定枚举/错误码/UTC 时间；不写中文状态 |
| §10 E1–E3/E9 | API 集成测试复用/覆盖；执行引擎测试不回退 |
| §10 E13/W6 | 属于 Round 1/2 或 M1-B，不在 Round 3 重复实现 |

---

## 3. API Inventory

所有路径前缀 `/api/v1/rag`；无鉴权，沿用项目本地单用户假设。响应 JSON 使用 UTF-8；时间为 UTC ISO 8601（`2026-11-25T23:00:00+00:00`）。

### 3.1 Dossier

| # | 方法与路径 | 业务动作 | Request | Response | Facade/Service |
|---|---|---|---|---|---|
| A1 | `GET /dossiers` | 列表 | `limit` 1–100（默认 50）、`offset` ≥0（默认 0） | `DossierListResponse` | `DossierFacade.list` |
| A2 | `POST /dossiers` | 创建 | `{title: string(1..200), description?: string(0..2000)}` | 201 `DossierSummary` | `DossierFacade.create` |
| A3 | `GET /dossiers/{dossier_id}` | Dossier Cover | — | `DossierDetail` | `DossierFacade.detail` |

**请求约束：**

- `title` 必填、去首尾空白后非空。
- `description` 默认 `""`。
- 不接受客户端传入 `status`、`id`、时间戳。
- `POST /dossiers` 不使用 Idempotency-Key；重复标题允许（Dossier 不是唯一命名资产）。

### 3.2 Run 触发

| # | 方法与路径 | 业务动作 | Request | Response | Facade/Service |
|---|---|---|---|---|---|
| R1 | `POST /dossiers/{dossier_id}/runs` | 触发 `dossier_rollup` | Header `Idempotency-Key`；body `{kind:"dossier_rollup", params?:{}}` | 202 新建 / 200 复用 `StartRunResponse` | `ExecutionFacade.start_dossier_rollup` → M05 `create_run_with_step_job` |

**约束：**

- `kind` 仅允许 `dossier_rollup`。
- `params` 必须为空对象；M1-A 无参数。未知字段返回 422。
- `Idempotency-Key` 必填、1–128 字符。
- Dossier 必须存在且 `status='active'`；归档 Dossier 返回 409。
- 新 Run 返回 `202 Accepted`；相同 key + 相同 payload 返回 `200 OK` 且 `reused=true`。
- 不因 Worker 不在线而拒绝入队；响应通过 `worker_available` / `warnings` 暴露（已批准决策 D2）。
- 不创建 Artifact/Verification；响应固定 `artifact_persisted=not_available`、`verified=not_implemented`。

### 3.3 Run 读取与事件

| # | 方法与路径 | 业务动作 | Request | Response | Facade/Service |
|---|---|---|---|---|---|
| R2 | `GET /runs/{run_id}` | RunDetail | — | 200 `RunDetail`；404 | `ExecutionFacade.get_run` → M05 read service |
| R3 | `GET /runs/{run_id}/events` | 增量事件 | `after_id` ≥0（默认 0）、`limit` 1–200（默认 50） | 200 `EventPage`；404 | `ExecutionFacade.list_events` |
| R4 | `POST /runs/{run_id}/cancel` | 请求取消 | — | 200 `CancelRunResponse`；404/409 | `ExecutionFacade.cancel_run` → M05 `request_cancel` |
| R5 | `GET /runtime/worker` | Worker 可用性 | — | 200 `WorkerSnapshot` | `ExecutionFacade.worker_status` |

**取消语义：**

- Run 处于 `queued/running` 且尚未 cancel → 200，`already_requested=false`。
- 已请求取消但未终态 → 200，`already_requested=true`；并发判断与写入由 **M05 `request_cancel()` 在锁内完成**，M06 只做前置资源/终态映射。
- Run 已终态 → 409 `RAG_RUN_NOT_CANCELLABLE`。
- 取消不删除 Job/Event；运行中 Job 由 Worker 在安全点转为 `cancelled`。
- 两个并发 Cancel 不得重复写 Event；测试使用两个独立 Session。

**事件游标：**

- 请求：`after_id` 为上一页最后一条 Event 的 `id`；`limit` 有上限。
- 查询必须使用 **`limit + 1`**：若返回 `limit+1` 条，则 `has_more=true`，只返回前 `limit` 条。
- 响应：`items`、`next_after_id`、`has_more`。
- `next_after_id` 为最后一条实际返回 item 的 id；无 item 时为 `after_id`。
- Event 按 `id ASC`；连续翻页不得重复、不得遗漏。

**不新增的接口：**

- 不新增独立 `GET /dossiers/{id}/runs`；Dossier Detail 内嵌 `recent_runs`。
- 不新增 `GET /runs` 全局列表。
- M1-A 不新增 `GET /dossiers/{id}/stages/{stage}`；Stage 状态内嵌在 Dossier Detail（见 §12 差异 D4）。
- 不新增 Dossier 更新/归档/删除 API（Phase 0 未定义）。

### 3.4 状态枚举

```text
RunStatus      = queued | running | succeeded | partial | failed | cancelled | skipped
StageStatus    = not_started | active | RunStatus
JobStatus      = queued | running | succeeded | partial | failed | cancelled | skipped
AttemptStatus  = running | succeeded | failed | abandoned | cancelled
StageKey       = dossier_rollup
RunKind        = dossier_rollup
```

`not_started` 与 `active` 只属于 Stage 读模型，不是 Run 状态；不得写入 `execution_runs.status`。

**Stage 状态判定（已批准修正）：**

- 任意同 Stage Run 为 `queued` 或 `running` → Stage `active`。
- 不存在活跃 Run 时，才使用最近一次终态 Run 的 `status`。
- 没有历史 Run → `not_started`。
- `active_run_count` 由 M05 按 scope/stage 真实聚合；不得由 M06 用最近 Run 推算。
- M1-A 允许同一 Dossier 有多个不同 Idempotency-Key 的活跃 Run；不增加同 Stage 单活跃 Run 互斥规则。

### 3.5 列表/分页/启动响应包络

**`DossierListResponse`：**

```json
{"items":[{"id":"rdos_...","title":"...","status":"active","last_run":{"id":"rrun_...","status":"succeeded"},"run_count":1,"active_run_count":0,"updated_at":"..."}],"total":1,"limit":50,"offset":0}
```

**`StartRunResponse`：**

```json
{"run":{"id":"rrun_...","pipeline":"dossier","stage":"dossier_rollup","status":"queued","created_at":"...","updated_at":"...","cancel_requested_at":null,"error_code":null},"reused":false,"worker_available":true,"warnings":[]}
```

**`CancelRunResponse`：**

```json
{"run":{"id":"rrun_...","status":"running","cancel_requested_at":"..."},"cancel_requested":true,"already_requested":false}
```

**`EventPage`：**

```json
{"items":[],"next_after_id":0,"has_more":false}
```

**`warning` 对象：**

```json
{"code":"WORKER_UNAVAILABLE","message":"No fresh worker heartbeat; the Run is queued."}
```

- `warnings` 只用于非致命运行提示；`code` 稳定，`message` 仅兜底。
- `DossierListResponse` 的 `items` 不含 `stages`/`recent_runs`，避免列表 N+1；run_count/active_run_count 必须由 M05 批量 scope 聚合查询提供。
- `StartRunResponse.run` 为 RunSummary，不返回完整 Step/Job；需要详情时再 `GET /runs/{id}`。

---

## 4. M06 Facade 设计

### 4.1 文件与职责

```text
services/api/app/modules/evaluation/
  facades/
    dossiers.py       # DossierFacade
    execution.py      # ExecutionFacade
  read_models.py      # DossierSummary / DossierDetail / StageSummary / RunDetail 等 DTO
  models.py           # RagDossier（既有）
  handlers/
    dossier_rollup.py # 既有 Handler
```

### 4.2 DTO

| DTO | 主要字段 |
|---|---|
| `DossierSummary` | `id,title,description,status,created_at,updated_at,last_run,run_count,active_run_count` |
| `DossierDetail` | `dossier,stages,execution,recent_runs,worker,evidence_capabilities,blocking,next_actions` |
| `StageSummary` | `stage_key,status,active_run_count,latest_run,latest_terminal_run,run_count,failed_run_count,last_activity_at,latest_result,last_error,next_actions` |
| `RunSummary` | `id,scope_type,scope_id,pipeline,stage,status,created_at,updated_at,cancel_requested_at,error_code` |
| `RunDetail` | `run,steps,evidence_capabilities,evidence_state` |
| `StepView` | `id,step_key,ordinal,status,progress,processed_count,failed_count,error,created_at,updated_at,jobs` |
| `JobView` | `id,job_key,kind,status,attempts,max_attempts,available_at,locked_by,last_heartbeat_at,lease_expires_at,cancel_requested_at,processed_count,failed_count,error,created_at,updated_at,attempts_history` |
| `AttemptView` | `id,attempt_no,status,worker_id,started_at,finished_at,error_code,error_detail,metrics` |
| `EventView` | `id,run_id,step_id,job_id,type,level,message,payload,created_at` |
| `WorkerSnapshot` | `available,worker_id,pid,last_seen,age_seconds,current_job_id,stale_after_seconds,reason_code` |

**不暴露：** `lease_token`、`fencing_token`、完整内部锁字段。`locked_by` 只作为可读 Worker 标识；不用于客户端写入。

### 4.3 DossierFacade

| 方法 | 输入 | 输出 | 事务 |
|---|---|---|---|
| `create(session,title,description)` | 用户输入 | DossierSummary | M06 拥有；`session.add` + commit |
| `list(session,limit,offset)` | 分页 | DossierListResponse | 只读 |
| `detail(session,dossier_id)` | id | DossierDetail | 只读；组合 M05 全量 Stage 聚合与最近 Run |

实现约束：

- Dossier 基础信息只从 `rag_dossiers` 读取。
- `last_run` / `recent_runs` / `run_count` / `active_run_count` 从 M05 公共读服务获取，不直接查 `execution_*` ORM。
- Stage 状态必须使用 **同 Stage 全量 Run 聚合**：任一 `queued/running` → `active`；否则取最近终态 Run；无历史 → `not_started`。
- `active_run_count` 必须来自 M05 `COUNT(status IN ('queued','running'))`，不得由 `latest_run` 推断。
- Dossier List 必须使用 M05 批量 scope 聚合，避免逐 Dossier 查询造成 N+1。
- `blocking` / `next_actions` 由完整聚合状态派生，不落库；不能因最近一个 Run `succeeded` 忽略其他活跃 Run。
- Dossier `updated_at` 不因 Run 执行而自动修改；`last_activity_at` 取最近 Run 的 `created_at/updated_at`，不伪造 Dossier 更新时间。

### 4.4 ExecutionFacade

| 方法 | 输入 | 输出 | 事务 |
|---|---|---|---|
| `start_dossier_rollup(session,dossier_id,idempotency_key,params)` | Dossier、key、空 params | StartRunResponse | 校验 Dossier（M06），调用 M05 原子创建；M05 拥有提交 |
| `get_run(session,run_id)` | id | RunDetail | 只读 |
| `list_events(session,run_id,after_id,limit)` | 游标 | EventPage | 只读 |
| `cancel_run(session,run_id)` | id | CancelRunResponse | M05 拥有事务与并发幂等；M06 仅做资源/终态映射，不复制锁或状态机 |
| `worker_status()` | — | WorkerSnapshot | 读文件，只读 |

**跨模块事务边界：**

- `start_dossier_rollup` 先在 M06 Session 中校验 Dossier；然后调用 M05 `create_run_with_step_job`。
- M05 的原子创建函数负责 Run+Step+Job 的单次提交；M06 不 `commit`、不 `rollback` 跨模块写。
- 若 Dossier 校验通过但 M05 创建失败，不留下部分执行记录；错误由 M05 抛出，M06 映射。
- `cancel_run` 的 M06 前置读取只用于 404/409 映射；并发幂等、锁顺序、重复 Event 判断均在 M05 内完成。
- 读模型不写任何表。

**禁止：**

- M06 直接写 `execution_runs/steps/jobs/attempts/events`。
- M06 复制 Claim/Lease/Recovery/Cancel 逻辑。
- M01 直接 import M05 Execution ORM 或写表。

---

## 5. M01 产品 API / Read Model 设计

### 5.1 DossierSummary

```json
{
  "id": "rdos_...",
  "title": "三国演义 RAG 实验",
  "description": "……",
  "status": "active",
  "created_at": "2026-11-25T23:00:00+00:00",
  "updated_at": "2026-11-25T23:00:00+00:00",
  "last_run": {
    "id": "rrun_...",
    "stage": "dossier_rollup",
    "status": "succeeded",
    "updated_at": "2026-11-25T23:01:00+00:00"
  },
  "run_count": 1,
  "active_run_count": 0
}
```

来源：

- `id/title/description/status/created_at/updated_at`：M06 `rag_dossiers`。
- `last_run/run_count/active_run_count`：M05 `list_run_summaries_for_scopes()` 批量 scope 聚合；Dossier List 不得逐条查询。
- `run_count`/`active_run_count` 是 M05 真实聚合，不是从 `last_run` 推断。

### 5.2 DossierDetail

```json
{
  "dossier": { "...": "DossierSummary 的 dossier 基础信息" },
  "stages": [
    {
      "stage_key": "dossier_rollup",
      "status": "succeeded",
      "latest_run": { "id": "rrun_...", "status": "succeeded" },
      "latest_terminal_run": { "id": "rrun_...", "status": "succeeded" },
      "run_count": 1,
      "active_run_count": 0,
      "failed_run_count": 0,
      "last_activity_at": "2026-11-25T23:01:00+00:00",
      "latest_result": {"dossier_count": 1, "run_count": 1},
      "last_error": null,
      "next_actions": ["VIEW_RUN", "RETRY_DOSSIER_ROLLUP"]
    }
  ],
  "execution": {
    "run_count": 1,
    "active_run_count": 0,
    "failed_run_count": 0,
    "last_success_at": "2026-11-25T23:01:00+00:00"
  },
  "recent_runs": [
    {
      "id": "rrun_...",
      "stage": "dossier_rollup",
      "status": "succeeded",
      "created_at": "2026-11-25T23:00:30+00:00",
      "updated_at": "2026-11-25T23:01:00+00:00",
      "error_code": null
    }
  ],
  "worker": {
    "available": true,
    "worker_id": "host:123",
    "pid": 123,
    "last_seen": "2026-11-25T23:01:05+00:00",
    "age_seconds": 2,
    "current_job_id": null,
    "stale_after_seconds": 20,
    "reason_code": null
  },
  "evidence_capabilities": {
    "generated": true,
    "db_persisted": true,
    "artifact_persisted": "not_available",
    "verified": "not_implemented"
  },
  "blocking": [],
  "next_actions": ["RETRY_DOSSIER_ROLLUP", "VIEW_RUN"]
}
```

字段来源与判定：

| 字段 | 来源 | 判定 |
|---|---|---|
| `stages` | DossierFacade + M05 run summaries | M1-A 只有 `dossier_rollup`；无 Run → `not_started` |
| `stage.status` | 同 Stage 全量 Run 聚合 | 任一 `queued/running` → `active`；否则最近终态 Run 状态；无历史 → `not_started` |
| `stage.active_run_count` | M05 按 scope/stage 聚合 | `COUNT(status IN ('queued','running'))`；真实 DB |
| `latest_run` | M05 最近一次任意状态 Run | 用于展示最近活动，不单独决定 Stage 状态 |
| `latest_terminal_run` | M05 最近一次终态 Run | 仅在无活跃 Run 时用于确定 Stage 状态 |
| `latest_result` | 最近一次 `succeeded/partial` **终态** Run 的 `result` | 原样返回；不代表 Dossier 统计，不重新计算、不由 LLM 生成 |
| `last_error` | 最近终态失败 Run 的 `error_code/error_detail` | 只返回安全摘要；无失败为 null |
| `execution` | M05 按 scope 聚合 | 真实 DB 计数；`active_run_count` 覆盖所有 queued/running Run，不由前端推算 |
| `recent_runs` | M05 `list_run_summaries_for_scope(limit=5)` | 按 created_at DESC |
| `worker` | M05 heartbeat | 文件年龄；不参与 Run 状态 |
| `evidence_capabilities` | 固定契约 | M1-A 的 Artifact/Verified 明确 N/A |
| `blocking` | 派生 | `ACTIVE_RUN` / `WORKER_UNAVAILABLE` / `LAST_RUN_FAILED` / `NO_RUN` |
| `next_actions` | 派生 | `RUN_DOSSIER_ROLLUP` / `RETRY_DOSSIER_ROLLUP` / `CANCEL_RUN` / `VIEW_RUN` / `WAIT` |

**并发示例：**

同一 Dossier 的 `dossier_rollup` 有两个 Run：

- Run A：`succeeded`
- Run B：`running`

结果：`stage.status="active"`，`active_run_count=1`，`latest_run` 可能是 B，`latest_terminal_run` 是 A；`blocking` 包含 `ACTIVE_RUN`，`next_actions` 包含 `CANCEL_RUN`/`WAIT`，不能因为 A 成功而显示 `succeeded`。

**禁止：**

- 不根据 HTTP 200 推断 Run `succeeded`。
- 不把 `latest_result` 标成 Verified；`latest_result` 是 Handler 结果，不是 Dossier 统计。
- 不把 Worker 可用性写进 Run 状态。
- 不把 `stage.status` 存到 `rag_dossiers` 冗余字段。
- 不因最近一个 Run `succeeded` 忽略其他仍在 `queued/running` 的 Run。
- 同一 Dossier 可有多个活跃 Run；Stage 必须显示 `active`，直到全部活跃 Run 结束。

### 5.3 RunDetail

```json
{
  "run": {
    "id": "rrun_...",
    "scope_type": "rag_dossier",
    "scope_id": "rdos_...",
    "pipeline": "dossier",
    "stage": "dossier_rollup",
    "status": "succeeded",
    "config_hash": "sha256:...",
    "config_snapshot": {"run_kind": "dossier_rollup"},
    "result": {"dossier_count": 1},
    "error_code": null,
    "error_detail": null,
    "cancel_requested_at": null,
    "created_at": "...",
    "updated_at": "..."
  },
  "steps": [
    {
      "id": "rstp_...",
      "step_key": "dossier_rollup",
      "ordinal": 1,
      "status": "succeeded",
      "progress": 100,
      "processed_count": 4,
      "failed_count": 0,
      "error": null,
      "created_at": "...",
      "updated_at": "...",
      "jobs": [
        {
          "id": "rjob_...",
          "job_key": "dossier_rollup",
          "kind": "dossier_rollup",
          "status": "succeeded",
          "attempts": 1,
          "max_attempts": 3,
          "processed_count": 4,
          "failed_count": 0,
          "attempts_history": [
            {"id": "ratt_...", "attempt_no": 1, "status": "succeeded", "worker_id": "host:123", "started_at": "...", "finished_at": "...", "error_code": null, "error_detail": null, "metrics": {}}
          ]
        }
      ]
    }
  ],
  "evidence_capabilities": {"generated": true, "db_persisted": true, "artifact_persisted": "not_available", "verified": "not_implemented"},
  "evidence_state": {"db_persisted": true, "readback_session": "new"}
}
```

**约定：**

- `config_snapshot` 返回只读快照；不是可修改配置；返回前必须做安全字段检查。
- `error_detail` 只返回安全摘要，不返回堆栈/凭证/完整 Prompt/敏感文件路径。
- `attempts_history` 不返回 `fencing_token`、`lease_token`。
- `evidence_state.db_persisted=true` **只表示执行记录能通过新 Session 从 DB 读回**；不代表 Artifact 已生成，也不代表业务结果已独立验证。
- `artifact_persisted=not_available`、`verified=not_implemented` 是 M1-A 固定值；不得把 Completed 写成 Verified。
- `Run.result`、Event `payload`、`error_detail`、`config_snapshot` 必须经过安全字段检查；详见 §8.4。

---

## 6. M05 Execution API 调用边界

### 6.1 新增 M05 公共函数

| 函数 | 用途 | 事务 |
|---|---|---|
| `create_run_with_step_job(...)` | 原子创建 Run + Step + Job，处理幂等键 | 单事务 commit |
| `list_run_summaries_for_scope(session,scope_type,scope_id,limit)` | 单个 Dossier 的最近 Run | 只读 |
| `list_run_summaries_for_scopes(session,scope_type,scope_ids,limit_per_scope)` | Dossier List 批量聚合，避免 N+1 | 只读 |
| `get_scope_execution_summary(session,scope_type,scope_id,stage)` | `run_count/active_run_count/failed_run_count/latest_terminal_run` | 只读 |
| `get_run_detail(session,run_id)` | Run/Step/Job/Attempt DTO | 只读 |
| `list_events(session,run_id,after_id,limit)` | Event 游标；内部查询 `limit+1` 判断 `has_more` | 只读 |
| `request_cancel(...)`（增强） | 锁内幂等取消；新增 `request_cancel_outcome(...) -> CancelOutcome`；保留现有返回 Run 的兼容入口 | M05 单事务 commit |
| `read_worker_status()` | 读取 `.run/worker.heartbeat`，仅返回 WorkerSnapshot | 只读 |

**禁止：** M05 不知道 Dossier 的标题/描述；`scope_type/scope_id` 保持 opaque。

### 6.2 原子创建事务

当前 `create_run()` / `create_step()` / `create_job()` 各自 commit。Facade 不应依次调用。新增：

```text
create_run_with_step_job(
  session,
  scope_type="rag_dossier",
  scope_id=dossier_id,
  pipeline="dossier", stage="dossier_rollup",
  config_snapshot, config_hash, fingerprint,
  idempotency_key, idempotency_payload_hash,
  step_key="dossier_rollup", ordinal=1,
  job_key="dossier_rollup", kind="dossier_rollup", payload={}, max_attempts=3
)
```

事务：

1. 若 idempotency key 存在：读取现有 Run，比较 payload hash。
2. 相同：读取对应 Step/Job；完整则返回 `reused=true`；缺失则抛 `RunIncomplete`（不得静默补写）。
3. 不同：抛 `IdempotencyConflict`。
4. 新建：Run + Step + Job 同事务 `flush`，一次 `commit`。
5. 唯一约束竞争：`IntegrityError` 后必须 **rollback**，然后使用一个可用的新事务/Session 按 key 重查；不得继续使用已失败事务的 Session。
6. 同 Key 同 Payload 并发：只创建 1 Run / 1 Step / 1 Job；其余请求返回已有 Run。
7. 同 Key 不同 Payload 并发：仅一个成功；其余返回 409 `RAG_IDEMPOTENCY_CONFLICT`。
8. 不因 Worker 不可用而回滚；Job 保持 `queued`。

**`RunIncomplete` 是新增业务错误码，不改变 Schema。**

`RunIncomplete` 处理要求：

- 发现已有 Run 缺 Step/Job 时立即返回 `RAG_RUN_INCOMPLETE`。
- 不自动补建、不覆盖、不删除、不创建重复 Run。
- 保留异常现场（`run_id`、缺失对象类型）供诊断。
- `details` 只返回安全字段：`run_id`、`missing`（`step`/`job`），不返回 SQL/堆栈。

### 6.3 Pipeline 取值

**已批准：** `pipeline="dossier"`、`stage="dossier_rollup"`，表示 Dossier 级维护执行；不新增表/字段。

R3.1 编码时必须同步修正现有测试夹具中错误的 `pipeline="dataset"` 构造值为 `pipeline="dossier"`。本计划修订不修改测试代码。

### 6.4 Idempotency

- Header：`Idempotency-Key`（必填，1–128）。
- 作用域：`(scope_type="rag_dossier", scope_id=dossier_id)`。
- Payload hash 输入：
  ```json
  {"kind":"dossier_rollup","params":{},"dossier_id":"rdos_..."}
  ```
- canonical JSON：`sort_keys=True`、`ensure_ascii=False`、紧凑分隔符；SHA-256。
- 同 key 同 hash → 200 `reused=true`，不重复建 Run/Step/Job。
- 同 key 不同 hash → 409 `RAG_IDEMPOTENCY_CONFLICT`。
- 并发：利用 `execution_runs` partial unique index；`IntegrityError` 后 **rollback + 新事务/Session** 重查，不得复用失败事务。
- 并发测试必须使用两个独立 Session，而不是同一 Session 或 Mock。
- 不接受客户端把 key 放在 body；只读 Header。

### 6.5 Cancel（M05 锁内并发幂等）

**职责划分：**

- M06 前置读取只用于：Run 是否存在（404）、是否终态（409）、返回当前摘要。
- M06 **不得**根据 `cancel_requested_at` 自行决定 `already_requested`，不得复制锁、事务或取消状态机。
- M05 `request_cancel()` / `request_cancel_outcome()` 必须：
  1. 遵守既有 **Job → Step → Run** 锁顺序。
  2. 在锁定 Job/Step/Run 后重新检查取消状态。
  3. 若 `cancel_requested_at` 已存在且 Run 未终态：返回 `already_requested=true`，不重复写 Event。
  4. 若未取消：写 Run/Job 取消标记与 Event，返回 `already_requested=false`。
  5. 若 Run 已在锁内变为终态：抛 `RunNotCancellable`，由 M06 映射 409。
- 新增 `request_cancel_outcome()` 返回 `CancelOutcome(run, already_requested)`；M06 只调用该入口并序列化。
- 保留现有 `request_cancel() -> ExecutionRun` 兼容行为，避免破坏 Round 2 调用；两者共享同一锁内实现。
- 取消成功后返回最新 Run 摘要；不把 `cancel_requested` 当作 `cancelled`。
- Worker 完成后状态由 Execution Engine 决定。

**并发测试：** 两个独立 Session 同时调用 M05 `request_cancel()`；最终只允许一组 `job.cancel_requested` Event，两个结果均为成功（一个 `already_requested=false`，一个 `already_requested=true`）或一个成功一个终态 409；不得重复 Event。

### 6.6 Worker Runtime 状态

- Worker heartbeat 是 **进程运行时状态**，不是 Execution 数据库领域实体。
- 持久化执行状态只来自 `execution_runs/steps/jobs/attempts/events`。
- heartbeat 只提供 `WorkerSnapshot`；不参与 Run/Step/Job 状态计算。
- heartbeat 缺失、损坏、过期：
  - 只返回 `available=false` + `reason_code`；
  - **不得修改 Run 状态**；
  - 不抛 500，不把 Run 标记 failed。
- Worker 在线不保证下一秒一定能接单；`available=true` 只是最近心跳新鲜。
- 不增加数据库表，不新增持久化 Worker 实体。
- M05 读取路径：`RAG_WORKER_HEARTBEAT_FILE` 或默认仓库 `.run/worker.heartbeat`。
- `stale_after_seconds`：`RAG_WORKER_STALE_SECONDS` 默认 20。
- API 不因 Worker 离线拒绝入队（已批准 D2）。

---

## 7. Request / Response 契约示例

### 7.1 创建 Dossier

```http
POST /api/v1/rag/dossiers
Content-Type: application/json

{"title":"三国演义 RAG 实验","description":"叙事型语料与检索实验"}
```

```http
HTTP/1.1 201 Created
Content-Type: application/json

{"id":"rdos_...","title":"三国演义 RAG 实验","description":"叙事型语料与检索实验","status":"active","created_at":"2026-11-25T23:00:00+00:00","updated_at":"2026-11-25T23:00:00+00:00","last_run":null,"run_count":0,"active_run_count":0}
```

### 7.2 触发 Rollup

```http
POST /api/v1/rag/dossiers/rdos_.../runs
Idempotency-Key: rollup-2026-11-25-001
Content-Type: application/json

{"kind":"dossier_rollup","params":{}}
```

```http
HTTP/1.1 202 Accepted
Content-Type: application/json

{
  "run": {"id":"rrun_...","pipeline":"dossier","stage":"dossier_rollup","status":"queued","created_at":"...","updated_at":"...","error_code":null},
  "reused": false,
  "worker_available": true,
  "warnings": []
}
```

同 key 同 payload 再次请求：

```http
HTTP/1.1 200 OK
{"run":{"id":"rrun_...","status":"succeeded"},"reused":true,"worker_available":true,"warnings":[]}
```

Worker 不在线时（推荐）：

```json
{"run":{"id":"rrun_...","status":"queued"},"reused":false,"worker_available":false,"warnings":[{"code":"WORKER_UNAVAILABLE"}]}
```

HTTP 仍为 202；Run 已真实持久化，等待 Worker。

### 7.3 读取事件

```http
GET /api/v1/rag/runs/rrun_.../events?after_id=0&limit=50
```

```json
{
  "items": [
    {"id":1,"run_id":"rrun_...","step_id":null,"job_id":null,"type":"run.created","level":"info","message":"run created","payload":{},"created_at":"..."},
    {"id":2,"run_id":"rrun_...","step_id":"rstp_...","job_id":"rjob_...","type":"job.claimed","level":"info","message":"job claimed","payload":{},"created_at":"..."}
  ],
  "next_after_id": 2,
  "has_more": false
}
```

### 7.4 错误

```http
HTTP/1.1 409 Conflict
Content-Type: application/json

{"code":"RAG_IDEMPOTENCY_CONFLICT","message":"Idempotency-Key was reused with a different payload.","recoverable":false,"details":{"dossier_id":"rdos_..."}}
```

---

## 8. Error Code 设计

### 8.1 Envelope

```json
{
  "code": "RAG_...",
  "message": "Safe English fallback; clients must map by code.",
  "recoverable": false,
  "details": {},
  "dossier_id": "optional",
  "run_id": "optional"
}
```

- `message` 不作为业务判断依据；FE 用 `code` 映射 zh-CN/en-US。
- 不返回堆栈、SQL、凭证、完整 Prompt、文件路径。
- `details` 只放安全字段。

### 8.2 错误表

| HTTP | code | 触发 | 处理 |
|---|---|---|---|
| 400 | `RAG_IDEMPOTENCY_KEY_REQUIRED` | POST run 缺少 Header | 客户端生成 key |
| 404 | `RAG_DOSSIER_NOT_FOUND` | Dossier 不存在 | — |
| 404 | `RAG_RUN_NOT_FOUND` | Run 不存在 | — |
| 409 | `RAG_DOSSIER_ARCHIVED` | 归档 Dossier 触发 Run | 不再触发 |
| 409 | `RAG_IDEMPOTENCY_CONFLICT` | 同 key 不同 payload | 生成新 key |
| 409 | `RAG_RUN_INCOMPLETE` | 幂等命中但 Run 缺 Step/Job | 人工核查，不自动补写 |
| 409 | `RAG_RUN_NOT_CANCELLABLE` | 终态 Run 取消 | 刷新状态 |
| 422 | `RAG_UNSUPPORTED_RUN_KIND` | kind 非 `dossier_rollup` | 不支持 |
| 422 | `RAG_INVALID_RUN_PARAMS` | params 非空/未知字段 | 修正请求 |
| 422 | `RAG_VALIDATION_ERROR` | Pydantic 校验失败 | 修正字段 |
| 500 | `RAG_INTERNAL_ERROR` | 未分类异常 | 查日志 |
| 503 | `RAG_DB_UNAVAILABLE` | 数据库不可用 | 重试/检查 DB |

**不作为 M1-A HTTP 错误：**

- Worker 不可用：`WORKER_UNAVAILABLE` 作为 `warnings` / WorkerSnapshot，而不是拒绝入队（已批准 D2）。
- `JOB_TIMEOUT`、`LEASE_EXPIRED`、`WORKER_LOST`、`WORKER_SHUTDOWN`：属于 Run/Job/Event 状态，不在 API 层返回 5xx；`GET /runs/{id}` 显示。
- `StaleLease` 只在 Worker 内部日志/事件；API 不暴露。
- `ARTIFACT_MISSING` / Verification 属于 M1-B，不在 M1-A API。

### 8.3 业务错误 vs 系统错误

| 类别 | 示例 | 处理 |
|---|---|---|
| 资源不存在 | Dossier/Run 不存在 | 404 |
| 业务状态冲突 | 归档 Dossier、终态取消、幂等冲突 | 409 |
| 请求非法 | kind/params/字段/缺 key | 400/422 |
| 系统 | DB 不可用、未分类异常 | 500/503 |
| 执行失败 | Handler 失败、Lease 丢失 | 200 RunDetail + status/Event，不是 HTTP 错误 |

---

### 8.4 安全字段过滤

`Run.result`、`Event.payload`、`RunDetail.config_snapshot`、`error_detail`、`warning.message` 返回前必须统一过滤：

**禁止返回：**

- Provider/API Key、Authorization、Cookie、数据库连接串、密码、内网 Token。
- `lease_token`、`fencing_token` 等内部所有权 Token。
- 完整 Prompt、完整文件内容、完整文档全文。
- 堆栈、SQL、绝对文件路径、`.env`/`.data` 路径。
- 未过滤的异常 `repr`。

**允许返回：**

- 稳定错误码、计数字段、状态、时间、公开业务 ID。
- `run_id`、`step_id`、`job_id`、`attempt_id`。
- Handler 明确声明为安全的摘要结果（如 Dossier rollup 计数）。
- 已脱敏的 `details`。

**实现要求：**

- M05 DTO 层做一次过滤，M06 不重新拼装原始 ORM `payload`。
- 对 JSONB 做键名/值模式检查；发现疑似敏感键时返回 `RAG_INTERNAL_ERROR` 安全摘要，而不是原样输出。
- 测试覆盖：`password`、`api_key`、`authorization`、`prompt`、`/Users/...`、`lease_token` 等键/值不出现在响应中。

---

## 9. i18n 与 FE 契约

- API 只返回稳定 `code/status/stage_key/action/blocking`，不返回中文业务状态。
- FE 映射：
  - `t('rag.error.' + code)`
  - `t('rag.status.' + status)`
  - `t('rag.stage.' + stage_key)`
  - `t('rag.action.' + action)`
  - `t('rag.blocking.' + code)`
- `message` 仅作为无映射时的兜底；不参与条件判断。
- 时间统一 UTC ISO 8601；FE 按 locale 格式化。
- `stage_key`、`action`、`status` 不使用中文。
- Stage 的 `active` 需要独立映射键 `rag.stage.active`，不能映射为 Run 的 `running` 文案。
- 未来 FE 不硬编码错误文本；必须走 `messages.ts`，不新建 i18n 机制。
- 本轮不实现 FE；API 契约已为 `EvidenceCapabilityChips` 和 `RunTimeline` 预留。

---

## 10. 测试矩阵

> 所有 API/Facade 测试使用真实 PostgreSQL `workbench_test`；不得用 SQLite 或 Mock DB 替代持久化/事务。Worker 端到端测试使用真实 Worker 子进程。

### 10.1 API Contract

| ID | 场景 | 断言 |
|---|---|---|
| C1 | 创建/列表/详情 Dossier | 201/200/200；字段、枚举、UTC 时间；真实 DB 行 |
| C2 | 404 | 不存在的 Dossier/Run 返回结构化 404 envelope |
| C3 | 422 | title 空、kind 非法、params 非空、未知字段 |
| C4 | 400 | 缺少/超长 `Idempotency-Key` |
| C5 | 409 | 归档 Dossier、终态取消、幂等冲突、RunIncomplete |
| C6 | OpenAPI | `/api/v1/rag` 路径和 schema 出现在 `/openapi.json`，旧路径不受影响 |
| C7 | 安全过滤 | Run.result/Event.payload/error_detail 不出现 key/token/完整 Prompt/绝对路径/堆栈 |

### 10.2 Facade

| ID | 场景 | 断言 |
|---|---|---|
| F1 | Dossier create/list/detail | 真实 M06 行；无 run → `not_started` |
| F2 | 原子 Run+Step+Job | 创建一次事务；DB 只有 1 Run/1 Step/1 Job |
| F3 | 幂等复用 | 同 key 同 payload 返回同 Run；不重复 Job |
| F4 | RunIncomplete | 人为构造缺 Step/Job 的 Run；返回 409；不补建、不覆盖、不创建重复 Run；保留 run_id 现场 |
| F5 | 读模型 | active/failed/succeeded/partial 的状态、统计、错误、next_actions；active_run_count 来自真实聚合 |
| F6 | Cancel 幂等（M05） | 两个独立 Session 并发取消；不重复写 Event；一个 `already_requested=false`，一个 `true`，或终态 409 |
| F7 | WorkerSnapshot | 缺失/损坏/过期 heartbeat → `available=false` + reason；Run/Step/Job 状态完全不变 |

### 10.3 Integration

| ID | 场景 | 断言 |
|---|---|---|
| I1 | API → Worker → Run 完成（E1） | 202 → worker → 轮询 GET run/events → succeeded；`result` 来自真实 Handler；DB 新 Session 读回 |
| I2 | API 幂等（E2/E3） | 同 key 同 payload 200 reused；不同 payload 409；DB 只有 1 Run/Job |
| I3 | Cancel API（E7） | 运行中 Job → cancel → 最终 cancelled；无 running 遗留 |
| I4 | 事件分页（E9） | 使用 `limit+1` 判断 `has_more`；`after_id` 连续翻页无重复/无遗漏；terminal 后停止轮询由 FE 完成 |
| I5 | Worker 不在线 | 触发仍 202 + warning；Run queued；`GET /runtime/worker` false；不伪造 succeeded |
| I6 | 并发幂等 | 两个独立 Session 并发同 key 同 payload 只创建 1 Run/1 Step/1 Job；同 key 不同 payload 仅一个成功，其余 409；`IntegrityError` 后 rollback + 新 Session 重查 |
| I7 | 并发 Cancel | 两个独立 Session 同时取消；事务完成、无死锁、Event 不重复；最终状态一致 |
| I8 | 双 Run 并发 | 同一 Dossier 两个 Run：一个 succeeded、一个 running；Stage 显示 `active`，不能显示 succeeded |

### 10.4 Read Model / Boundary

| ID | 场景 | 断言 |
|---|---|---|
| RM1 | Dossier Cover | stage/last_run/recent_runs/execution/blocking/next_actions 字段来源正确 |
| RM2 | 无 Run | stage `not_started`；next action `RUN_DOSSIER_ROLLUP` |
| RM3 | 运行中 | stage `active`；blocking `ACTIVE_RUN`；next action `CANCEL_RUN`/`WAIT` |
| RM4 | 失败 | last_error 只含安全 code/detail；next action `RETRY_DOSSIER_ROLLUP` |
| RM5 | 双 Run 聚合 | 一个 succeeded + 一个 running → stage `active`；active_run_count=1；最近终态 success 不覆盖活跃状态 |
| RM6 | Dossier List N+1 | 多 Dossier 列表使用 M05 批量聚合；SQL 查询数不随 Dossier 数线性增长 |
| RM7 | heartbeat 过期 | heartbeat stale/missing → WorkerSnapshot false；Run 状态不变，不新增 Event |
| B1 | M05 边界 | AST/import 检查：`execution/` 不 import `evaluation/`、`rag/` |
| B2 | M06 边界 | Facade 不写 `execution_*`；只调用 M05 公共函数 |
| B3 | M01 边界 | Router 不直接 import/写 M05/M06 ORM；只调用 Facade |
| B4 | i18n | 枚举/code 无中文；时间 UTC；无语言绑定状态 |

### 10.5 必须保留的既有测试

- `tests/test_rag_schema.py`：16
- `tests/test_rag_execution.py`：9
- `tests/test_rag_worker.py`：14
- 既有 38 项业务测试
- 目标：全量 **77 + 新增** 通过。

**Mock 边界：**

- 允许在 Facade/API 测试中临时替换 Worker heartbeat 文件，以模拟 available/stale/missing；不得 mock DB。
- API 端到端至少一条走真实 Worker 子进程（I1）。
- 并发/锁测试必须真实 PostgreSQL。
- 不允许只断言 HTTP 200 或前端轮询到数据。

---

## 11. 实施子轮次与验收标准

### R3.1 — M05 公共读取与原子创建

**目标：** 提供 M06 可调用的稳定执行 API，不复制 Engine 逻辑。

**修改/新增：**

- 修改 `execution/service.py`：新增 `create_run_with_step_job`、批量 scope 聚合、读取 DTO/查询、Cancel 锁内幂等；新增 `request_cancel_outcome`，保留 `request_cancel` 现有返回签名兼容。
- 新增 `execution/read_models.py`（或 `dto.py`）：M05 中性 DTO 与安全过滤。
- 新增 `execution/runtime.py`：读取 Worker heartbeat，仅生成 WorkerSnapshot。
- 测试：`tests/test_rag_execution_read_api.py`、`test_rag_execution_atomic_create.py`、`test_rag_execution_cancel_concurrency.py`。
- 同步把现有测试夹具中的 `pipeline="dataset"` 修正为 `pipeline="dossier"`。

**依赖：** Round 1/2 已验收。

**验收：**

- 原子创建无部分状态。
- 同 key 同/不同 payload 并发使用独立 Session 行为正确；失败事务 rollback 后新 Session 重查。
- RunIncomplete 不自动修复。
- M05 Cancel 锁内幂等，重复取消不重复 Event。
- 批量 scope 聚合可供 Dossier List 避免 N+1。
- `pipeline="dossier"` 测试夹具修正完成。
- 读取 DTO 不泄露 `lease_token/fencing_token`。
- 既有 77 tests 全绿。

**回滚：** 新增函数与测试可单独移除；不改 Schema/Migration。

### R3.2 — M06 Facades 与 Read Model

**目标：** Dossier/Execution 用例编排与 DTO。

**新增：**

- `evaluation/facades/dossiers.py`
- `evaluation/facades/execution.py`
- `evaluation/read_models.py`
- `tests/test_rag_facade.py`、`tests/test_rag_read_model.py`

**依赖：** R3.1。

**验收：**

- Dossier create/list/detail 真实 PG。
- start rollup 原子；错误映射。
- stage/status/recent/blocking/actions 来源正确；双 Run 并发时 Stage `active`。
- Dossier List 使用 M05 批量聚合，无 N+1。
- 无跨模块写；边界测试 B1/B2。

**回滚：** 移除 Facade 文件即可；M05 保留。

### R3.3 — M01 API Router 与错误契约

**目标：** `/api/v1/rag` 可调用，OpenAPI 可见。

**新增：**

- `api/v1/rag/{__init__,router,dossiers,runs,runtime,schemas,errors}.py`
- `tests/test_rag_api_contract.py`、`test_rag_api_errors.py`

**修改：**

- `app/main.py` include router；注册 RAG 异常/验证 handler（仅 `/api/v1/rag` 路径）。
- 不修改既有 Router 行为。

**依赖：** R3.2。

**验收：**

- A1–R5 全部路径/状态码/字段。
- 错误 envelope 稳定；旧 API 行为不变。
- OpenAPI schema 测试。
- 真实 PG。

**回滚：** 移除 include 与 router；旧 API 不受影响。

### R3.4 — API + Worker 集成 / 边界 / i18n

**目标：** 真实闭环与边界证据。

**新增：**

- `tests/test_rag_api_integration.py`
- `tests/test_rag_module_boundaries.py`
- 文档更新（本计划、API README）。

**依赖：** R3.3。

**验收：**

- I1/I2/I3/I4/I5/I6/I7/I8 通过。
- E1/E2/E3/E7/E9 的 API 层覆盖；执行引擎既有测试不回退。
- B1–B4 通过。
- 全量测试 ≥77 + 新增全绿。
- 无 Artifact/Verification/M1-B/FE 代码。

**回滚：** 删除测试与文档；不影响运行时。

---

## 12. 风险、已批准决策与 Phase 0 差异

### 12.1 已批准决策（本轮锁定）

| ID | 已批准决策 | 理由 | 施工影响 |
|---|---|---|---|
| **D1** | `pipeline="dossier"`、`stage="dossier_rollup"` | 它不是 Dataset Pipeline，也不是 Experiment Pipeline；用 `dataset` 会误导审计 | 影响 Run 分类、FE 展示、历史数据语义；无 Schema 变更；R3.1 修正测试夹具 |
| **D2** | Worker 离线仍创建 Run+Step+Job；返回 202 + `worker_available=false` + `WORKER_UNAVAILABLE` warning | 持久化队列是真实事实；拒绝会丢失排障能力 | 不返回 503；202 不代表执行；WorkerSnapshot 独立 |
| **D3** | `Idempotency-Key` 必填；同 Key 同 Payload 返回已有 Run；不同 Payload 409 | 防止重复触发和重复 Job；符合 Phase 0 幂等要求 | 客户端必须生成 key；否则 400 |
| **D4** | M1-A 不提供独立 Stage API；Stage 内嵌 Dossier Detail | §12.6 未列该端点；M1-A 只有 `dossier_rollup` 一个 stage；独立端点在 M1-B 随 Dataset Stage 落地 | 不新增 stage 路径；不改变业务模型 |

**已无 D1–D4 待决项。** 上述决策是 R3.1–R3.4 的固定输入。

### 12.2 已定实现细节（不需 Owner 决策）

- Dossier list 使用 `limit/offset`，返回 `items/total`。
- Run 触发返回 202；复用返回 200。
- Dossier create 返回 201；不要求 Idempotency-Key。
- 错误 envelope 顶层 `code/message/recoverable/details`；`message` 仅兜底。
- `config_snapshot` 在 RunDetail 返回，不返回凭证；不提供写入。
- Attempt 不暴露 `fencing_token/lease_token`。
- Worker heartbeat 读文件，不新增表；只生成 WorkerSnapshot，不是 Execution 领域实体。
- Dossier `updated_at` 不随 Run 改变；`last_activity_at` 来自 Run。
- 列表/详情不返回 Artifact/Verification；固定 N/A。
- Stage `active` 是读模型状态，由 M05 全量聚合派生；不写入 Run 状态。
- Event 分页使用 `limit+1`；游标按 Event ID ASC。
- M05 DTO 负责安全字段过滤；M06 不重新拼装原始 payload。

### 12.3 风险

1. **当前 `create_run/create_step/create_job` 分开 commit**：必须新增原子函数，否则 API 可能留下不完整 Run。已列 R3.1 阻断项。
2. **`dossier_rollup` Handler 的 `dossier_count` 是全局值**：Dossier Detail 不得直接把它解释为“当前 Dossier 统计”；应返回 `latest_result` 并另算 Dossier execution stats。
3. **Worker 可用性只有文件心跳**：非数据库权威；API 只能表达 `available`，不能保证下一秒有 Worker 接单。
4. **取消的重复请求**：必须由 M05 在 Job→Step→Run 锁内做并发幂等；M06 不得复制状态机；已列入 F6/I7。
5. **错误 envelope 与既有 API 不一致**：RAG 使用顶层 envelope；旧 API 保持 `detail`，避免回归；需路径感知或独立 handler。
6. **`dossier_rollup` pipeline 测试夹具**：现有测试仍使用 `dataset`；R3.1 必须修正为 `dossier`，否则 API 读模型与测试断言不一致。D1 已批准，不存在语义待决。
7. **API 无鉴权**：沿用本地单用户；不对公网暴露；未来需独立安全设计。
8. **Stage 只有 `dossier_rollup`**：FE 不得把 `not_started` 当失败；M1-B Dataset Stage 未实现；多个活跃 Run 时 Stage 为 `active`，不是 `running`。
9. **测试运行成本**：API+Worker 集成测试启动子进程，需真实 PG；不得用 mock 替代；测试可能比现有 77 项慢。
10. **Round 0 文档文件名差异**：任务描述 `...plan(3).md` 不存在；本计划依据实际 `...plan.md`。Phase 0 差异仍作为文档来源风险保留。

### 12.4 Phase 0 差异清单

| # | 差异 | 影响 | 处理 |
|---|---|---|---|
| 1 | 任务引用 `rag-lab-phase-0...plan(3).md`；仓库实际为 `...plan.md` | 可能依据不同版本 | 本计划以仓库实际文件为准；请 GPT 确认 |
| 2 | §5.7 提到 `GET /dossiers/{id}/stages/{stage}`；§12.6 未列 | 端点范围冲突 | 已批准 D4：M1-A 不提供独立 Stage API，Stage 内嵌 |
| 3 | §12.6 列 `WORKER_UNAVAILABLE` 错误；未定义触发时是否拒绝 | 产品行为 | 已批准 D2：202 + warning，不拒绝入队 |
| 4 | §12.6 未列 Dossier 列表分页、Run 列表 | API 细节 | 列表分页；Run 通过 Dossier `recent_runs` |
| 5 | 当前 `dossier_rollup` 测试使用 `pipeline="dataset"` | 语义误导 | 已批准 D1：R3.1 修正为 `pipeline="dossier"`；本任务不改测试代码 |
| 6 | 当前 M05 创建函数分开 commit | 部分状态风险 | 新增原子函数（R3.1） |
| 7 | 当前 M06 无 Facade/Read Model | 需要新增 | R3.2 |
| 8 | 当前 API 错误为 `detail` | 与 Phase 0 envelope 不同 | RAG 专用错误 handler |
| 9 | Phase 0 §12.9 使用 `test_rag_shutdown.py` 等文件名；实际为 `test_rag_worker.py` / `test_rag_execution.py` | 测试命令差异 | 以当前实际测试组织为准，新增 API 测试文件 |
| 10 | 当前 `dossier_rollup` result 含全局 `dossier_count` | Dossier 读模型可能误用 | `latest_result` 原样返回；stats 另算 |
| 11 | 当前无 `docs/implementation/` | 文档路径 | 本文件新建目录 |
| 12 | 当前 `PROJECT_CONTEXT.md` 未记录 RAG Lab 新实现 | 上下文陈旧 | Round 3 完成后另行更新，须遵守文档治理 |

---

## 13. 结论

Round 3 计划的核心不是“加几个 Router”，而是补三件事：

1. **M05 的原子创建与公共读 DTO**：防止 API 制造不完整 Run，同时禁止 M06 复制 Execution 逻辑。
2. **M06 的用例 Facade 与 Dossier/Execution 读模型**：让 Stage/Run/Job/Event 的展示基于真实 DB 状态。
3. **M01 的稳定 API 契约**：错误码、幂等、取消、Worker 可用性、i18n 中性枚举。

本计划不修改 Schema/Migration，不进入 M1-B/FE。D1–D4 已批准并锁定；等待 GPT 最终审查与 R3.1 施工授权后，按 R3.1 → R3.4 分阶段施工。
