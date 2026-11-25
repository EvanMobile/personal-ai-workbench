# RAG Lab M1-A — R3.4.3 i18n Baseline & Hardcoded Text Audit

**状态：COMPLETED（R3.4.3）；未进入 M1-B；未 Commit / Push。**

## 1. 执行范围与结论

### 当前 FE 事实

- `apps/web` 当前实现的是 **Personal Knowledge / P1.M1** 工作台。
- 当前仓库 **尚未实现 RAG Lab M1-A FE 页面**。
- `apps/web/src/views/DossiersView.tsx` 与 `DossierDetailView.tsx` 属于 M02 Personal Knowledge Dossier，不是 M06 RAG Dossier。
- 因此本轮没有 RAG Lab 页面需要做 A 类文案整改，也没有用 M02 Dossier 冒充 RAG Lab UI。
- 本轮建立了 RAG Lab 术语与 API 错误文案基线，并复用现有 i18n 机制；没有创建新页面。

### 已建立的基线

| 项目 | 状态 |
|---|---|
| 默认语言 | `zh-CN` |
| 第二语言 | `en-US` |
| i18n 机制 | 现有 React Context + 集中词典 |
| 资源文件 | `apps/web/src/i18n/messages.ts` |
| 语言切换 | 现有 `LanguageSwitcher` + `localStorage` |
| 词典 Key 数 | zh-CN / en-US 各 **499** |
| RAG 术语 Key | 17 |
| RAG API 错误 Key | 13 |
| RAG Lab 页面 | 尚未实现 |
| 新增 RAG 页面 | 无 |

## 2. 现有 i18n 技术方案

### 依赖与实现

- 无新增 i18n 运行时依赖。
- `apps/web/src/i18n/index.tsx`
  - `I18nProvider`
  - `useI18n()`
  - `translate()`
  - `DEFAULT_LOCALE = 'zh-CN'`
  - `en-US` 支持
  - `localStorage` 持久化 key：`paw.locale.v1`
  - `document.documentElement.lang`
  - `setFormatLocale` 同步日期/相对时间 locale
- `apps/web/src/i18n/messages.ts`
  - `zhCN` 与 `enUS` 集中词典
  - `MessageKey = keyof typeof zhCN`
  - `enUS: Record<MessageKey, string>`，编译期约束 Key 完整
- `apps/web/src/components/LanguageSwitcher.tsx`
  - 已有 zh-CN / en-US 切换入口
- `apps/web/src/utils.ts`
  - `Intl.DateTimeFormat` / `Intl.RelativeTimeFormat`
  - 随 locale 切换

### 文案组织

- 用户可见文案通过 `t('...')` 获取。
- 动态变量使用 `{name}` 插值，例如 `dossiers.cardsCount`。
- 现有 FE 无硬编码中文在 `src/i18n` 之外。
- 现有 `pnpm check:i18n` 已能检测：
  - Key 对齐
  - 空翻译
  - 插值占位符一致
  - `src/i18n` 外中文
  - JSX 可见文本与技术白名单之外的属性文本

## 3. RAG Lab 术语表

| Key | zh-CN | en-US | 说明 |
|---|---|---|---|
| `rag.term.dataset` | 数据集 | Dataset | M1-B 领域 |
| `rag.term.document` | 文档 | Document | 文档实体 |
| `rag.term.chunk` | 分块 | Chunk | 分块结果 |
| `rag.term.chunking` | 分块 | Chunking | 分块过程 |
| `rag.term.embedding` | 向量嵌入 | Embedding | 向量化 |
| `rag.term.retrieval` | 检索 | Retrieval | 检索 |
| `rag.term.reranking` | 重排序 | Reranking | 重排序 |
| `rag.term.evaluation` | 评估 | Evaluation | M06 评估 |
| `rag.term.experiment` | 实验 | Experiment | M06 实验 |
| `rag.term.run` | 运行 | Run | 一次 Execution Run |
| `rag.term.step` | 步骤 | Step | Run 内阶段 |
| `rag.term.job` | 作业 | Job | 可调度作业 |
| `rag.term.attempt` | 尝试 | Attempt | Job 的一次执行 |
| `rag.term.event` | 事件 | Event | 执行时间线事件 |
| `rag.term.artifact` | 产物 | Artifact | **不等于 Verified** |
| `rag.term.dossier` | RAG 实验档案 | RAG experiment dossier | 与 M02 “档案集”区分 |
| `rag.term.groundTruth` | 标准答案 | Ground truth | Evaluation 基准 |

### 术语边界

- **RAG Dossier ≠ Personal Knowledge Dossier**
  - M02 `common.dossiers` = “档案集”
  - M06 `rag.term.dossier` = “RAG 实验档案”
  - 不把 M02 的“档案集”复用到 RAG Lab。
- **Run ≠ Step ≠ Job ≠ Attempt**
  - 分别使用 `运行 / 步骤 / 作业 / 尝试`。
- **Completed ≠ Verified**
  - 有 Run 结果只表示执行完成；不得翻译为“已验证”。
- **Artifact**
  - UI 可展示 Artifact，但不得因为存在 Artifact 就显示 Verified。

## 4. 硬编码文本审计

### 4.1 RAG Lab 页面

当前 **不存在 RAG Lab FE 页面**，因此 RAG Lab A 类硬编码文本为 **0**。

不存在以下页面路径或组件：

- `apps/web/src/views/rag/*`
- RAG Dossier Library / Cover / Run Timeline
- RAG Lab API 客户端页面

没有为了审计而创建空页面或伪造 RAG 页面覆盖。

### 4.2 现有 FE A/B/C 分类

| 文件:行 | 文本 | 分类 | 处理 | 说明 |
|---|---|---|---|---|
| `apps/web/src/App.tsx:241` | `Personal AI Workbench` | B | 保留 | 产品品牌名 |
| `apps/web/src/App.tsx:438` | `Personal AI Workbench` | B | 保留 | 产品品牌名 |
| `apps/web/src/components/ContextTree.tsx:37` | `CTX` | B | 保留 | 技术面板标记 |
| `apps/web/src/components/ContextTree.tsx:193` | `⌘N` | B | 保留 | 键盘快捷键 |
| `apps/web/src/views/CaptureView.tsx:201` | `KB ·` | B | 保留 | 文件大小单位 |
| `apps/web/src/views/CaptureView.tsx:241` | `knowledge_capture` | B | 保留 | 后端 intent 技术标识 |
| `apps/web/src/views/PlaceholderView.tsx:15` | `PRJ_REPLAY` | B | 保留 | 模块 ID |
| `apps/web/src/views/PlaceholderView.tsx:29` | `ARSENAL` | B | 保留 | 模块 ID |
| `apps/web/src/views/PlaceholderView.tsx:104` | `P1.M1` | B | 保留 | 技术阶段标识 |
| `apps/web/src/views/PagesView.tsx:157` | `P.` | B | 保留 | 页码技术前缀 |
| `apps/web/src/i18n/messages.ts` | 全部用户文案 | A | 已集中 | 由 `t()` 消费 |

### 4.3 C 类

无 C 类待确认项。

- 没有发现需要人工判断的 RAG Lab 用户可见文案。
- 未来 RAG Lab 页面出现后，CSV/JSON 字段、事件 payload、API code、状态枚举等仍按技术标识处理，不机械翻译。
- 用户上传内容、日志、注释、API 参数不进入翻译资源。

## 5. RAG API 错误映射基线

新增 13 个稳定错误文案 Key：

```text
rag.error.RAG_DOSSIER_NOT_FOUND
rag.error.RAG_RUN_NOT_FOUND
rag.error.RAG_DOSSIER_ARCHIVED
rag.error.RAG_IDEMPOTENCY_CONFLICT
rag.error.RAG_RUN_INCOMPLETE
rag.error.RAG_RUN_NOT_CANCELLABLE
rag.error.RAG_UNSUPPORTED_RUN_KIND
rag.error.RAG_INVALID_RUN_PARAMS
rag.error.RAG_IDEMPOTENCY_KEY_REQUIRED
rag.error.RAG_INVALID_IDEMPOTENCY_KEY
rag.error.RAG_VALIDATION_ERROR
rag.error.RAG_INTERNAL_ERROR
rag.error.RAG_EXECUTION_CONFLICT
```

未来 FE 规则：

- 以 API 返回的稳定 `code` 为主键。
- 通过 `t('rag.error.' + code)` 映射。
- 不依赖后端 `message` 文本做判断。
- 未知 code 使用安全通用错误文案。

## 6. 自动化检查

### 已有检查

```bash
cd apps/web
pnpm check:i18n
```

覆盖：

- zh-CN / en-US Key 对齐
- 空翻译
- 插值占位符一致
- `src/i18n` 外中文
- JSX 可见文本/属性文本绕过

### 本轮新增 RAG 检查

```bash
cd apps/web
pnpm check:rag-i18n
```

覆盖：

- 17 个 RAG 术语 Key 存在且非空
- 13 个 RAG API 错误 Key 存在且非空
- RAG Dossier 与 M02 档案集术语区分
- 默认语言 `zh-CN`
- `en-US` 为支持语言

### 硬编码扫描命令

```bash
cd apps/web
pnpm check:i18n
pnpm check:rag-i18n
```

当前结果：

- `src/i18n` 外硬编码中文：0
- JSX 可见文本/属性绕过：0
- RAG Lab 页面：当前不存在，故 RAG A 类为 0

## 7. 后续 RAG Lab FE 强制规则

1. 所有 RAG Lab 用户可见文案必须通过 `t()`。
2. RAG 术语使用 `rag.term.*`，不得在页面中重复定义翻译。
3. RAG API 错误使用 `rag.error.<稳定 code>`，不得直接展示 `message`。
4. 默认 `zh-CN`，可选 `en-US`；不得改变默认语言。
5. 新增 Key 必须同时加入 zh-CN / en-US。
6. 参数化使用 `{name}` 插值，不拼接句子。
7. 日期、时间、相对时间使用现有 `formatDate` / `formatDateTime` / `relativeTime`。
8. 状态值使用稳定枚举；UI 不根据文案判断状态。
9. `Completed` 与 `Verified` 使用不同文案；Artifact 存在不等于 Verified。
10. 技术标识符、API 字段、事件 code、日志、用户原文不进入翻译资源。

## 8. 验证结果

```bash
cd apps/web
pnpm check:i18n
pnpm check:rag-i18n
pnpm exec tsc -b
pnpm build
```

| 命令 | 结果 |
|---|---|
| `pnpm check:i18n` | 5 passed |
| `pnpm check:rag-i18n` | 3 passed |
| `pnpm exec tsc -b` | passed |
| `pnpm build` | passed |

- 语言资源 Key：zh-CN 499 / en-US 499
- 新增 RAG term keys：17
- 新增 RAG error keys：13
- RAG Lab 页面硬编码 A 类：0（页面尚未实现）
- FE lint script：项目当前未定义 `lint` script；采用 `tsc -b` + `vite build` + i18n checks

## 9. 未完成事项与风险

1. **RAG Lab FE 页面尚未实现**：本轮只建立基线与资源，不创建页面，不提前实现 M1-B。
2. RAG 术语/错误 Key 目前尚未被页面消费，等待 RAG Lab FE 实现时使用。
3. 现有 M02 “档案集”与 RAG “RAG 实验档案”必须持续区分；不得在后续页面合并术语。
4. 现有 i18n 检查允许产品品牌/技术标识白名单；新增白名单必须经过审查，不得用白名单隐藏普通用户文案。
5. 无 RAG Lab 页面，因此没有页面级视觉回归；本轮验证为静态资源、类型、构建和全局 UI 扫描。
