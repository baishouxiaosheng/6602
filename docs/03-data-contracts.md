# 03 · 数据契约与接口

权威定义：`src/gamegene/contracts/`（Pydantic 模型，未知字段一律拒绝）。本文解释含义与约束。

## 1. 存储布局（`GAMEGENE_DATA_DIR`，默认 `data/store/`）

```
data/store/
  profiles/<profile_id>.json            最新版本
  profiles/_history/<id>.r0001.json     历史版本（只增不改）
  catalog/<appid>.json                  目录记录（工作流二写）
  runs/<run_id>.json                    推荐运行（写入后不再修改）
  requests/<request_id>.json            幂等索引：request_id → run_id
  reports/catalog-batch-<时间>.json     目录批处理报告
data/raw/<appid>/{appdetails,reviews,tags}.json   Steam 原始快照（证据核验的对象，不入库）
```

每个文件都是一个信封：

```json
{"schema_version": "1.0", "kind": "profiles", "id": "p-1a2b3c4d", "revision": 2,
 "created_at": "…", "updated_at": "…", "data": { …模型本体… }}
```

`JsonStore` 的保证：原子写入（临时文件 + `os.replace`）；写失败时旧版本原样保留；
`put(..., expected_revision=n)` 提供乐观锁（不匹配抛 `Conflict`）；损坏文件抛 `StorageError` 而不是崩溃。

## 2. 目录：`GameRecord`（键 = `appid`）

| 字段 | 说明 |
|---|---|
| `appid`, `name` | Steam AppID 与名称 |
| `status` | `pending` / `verified` / `partial` / `failed`（见 02 §5） |
| `store: StoreInfo` | 规范化后的商店信息：`genres`、`tags`（前 20，小写）、`platforms`、`social_modes`、`languages`、`is_free`、`price`、`store_url`、`header_image`、`cc`、`lang`、`fetched_at` 等 |
| `genes: {gene_id: GeneValue}` | **必须恰好九个键**。`GeneValue = {level: 0–4 或 null, confidence, evidence_ids[], unknown_reason}`；已知等级必须有证据与置信度，未知不得带证据 |
| `evidence: Evidence[]` | `{evidence_id, gene, quote, source_type, source_ref, grade, match_score, verified_at}`；`evidence_id` 记录内唯一，且必须与引用它的基因一致 |
| `annotation` | `{provider, model, prompt_version, gene_schema_version, annotated_at}`，`verified` 必填 |
| `review_note` | `partial` / `failed` 时给人看的原因 |

`PriceInfo`：`{currency, final_cents, initial_cents, discount_percent, fetched_at}`，金额单位为分；免费游戏 `is_free=true` 且 `price=null`。

## 3. 画像：`UserProfile`（键 = `profile_id`，格式 `p-` + 8 位十六进制）

| 字段 | 说明 |
|---|---|
| `display_name` | 1–40 字符 |
| `genes: {gene_id: {target: 0–4, weight: 0–1}}` | 九维偏好：想要的等级 + 该维度的重要程度 |
| `familiar_tags: {tag: 0–1}` | 用户熟悉的表层类型（小写），决定同类轨 / 其他轨 |
| `filters: HardFilters` | `platforms[]`、`social_modes[]`（空 = 不限，满足任一即可）、`max_price_cents`、`required_language`、`exclude_owned`、`excluded_tags[]`、`excluded_appids[]` |
| `owned_appids[]` | 导入的 Steam 库 |
| `sources` | `{interview_version, answers, steam_id, library_imported_at, library_matched_appids}`：画像如何得来，可据此复现 |

`exclusion_set()` = `excluded_appids` ∪（`exclude_owned` 时的 `owned_appids`）。

输入 `ProfileRequest`：`{profile_id?, display_name, answers, filters?, steam_id_or_url?}`；
`profile_id` 为空表示新建，给出已有 ID 表示修改（生成新版本，旧版本保留）。

## 4. 推荐：`RecommendRequest` → `RecommendationRun`（键 = `run_id`）

请求：`{profile_id, mode="both", top_k=3 (1–10), request_id?}`。`mode` 故意是普通字符串：未知模式由路由器处理（课程测试三）。

| `RecommendationRun` 字段 | 说明 |
|---|---|
| `status` | `ok`（至少一条轨道有推荐）/ `closest_only` / `no_match` / `error`，与载荷的一致性由模型校验 |
| `message` | 一句给人看的说明 |
| `same_track[]`, `cross_track[]` | `Recommendation` 列表 |
| `closest` | 仅 `closest_only`：最接近的候选，`explanation.mismatch` 说明差异 |
| `candidates_total`, `candidates_after_filters`, `filter_drops{原因: 数量}` | 过滤前后数量与剔除原因 |
| `llm` | `{provider, model, calls, retries, fallbacks}` |
| `error` | 仅 `error`：`ErrorResponse` |
| `trace[]` | `{step, branch, detail, at}`：执行证据链 |
| `profile_id`, `profile_revision`, `request`, `created_at` | 可复现所需的上下文 |

`Recommendation`：`appid, name, track, score, similarity, coverage, surface_overlap, confidence,
shared_genes[], explanation, barriers[], price, is_free, store_url, header_image`。

`SharedGene`：`{gene, user_target, game_level, evidence_id, quote, grade, source_type, source_ref}`（证据句直接内嵌，历史回看不依赖目录是否变化）。

`Explanation`：`{headline, reasons[{gene, text, evidence_id}], mismatch?, generated_by: "llm"|"template"}`。

## 5. 错误（`contracts/errors.py`）

| 异常 | `code` | HTTP | 可重试 | 何时 |
|---|---|---|---|---|
| `InvalidInput` | `invalid_input` | 400 | 否 | 确定性校验失败（`details.problems` 列出全部问题） |
| `NotFound` | `not_found` | 404 | 否 | 画像 / 运行 / 游戏不存在 |
| `Conflict` | `conflict` | 409 | 否 | 版本冲突 |
| `UnsupportedMode` | `unsupported_mode` | 422 | 否 | 备用；推荐流水线对未知模式返回 `no_match` 运行而不抛出 |
| `UpstreamError` | `upstream_error` | 502 | **是** | Steam / 模型超时、连接失败、5xx |
| `RateLimited` | `rate_limited` | 429 | **是** | 上游限流 |
| `SteamProfilePrivate` | `steam_profile_private` | 403 | 否 | Steam 库不公开 |
| `LLMOutputInvalid` | `llm_output_invalid` | 502 | 否 | 模型回答重试后仍不合契约（`details` 含 `model`、`raw_head` 前 200 字符） |
| `StorageError` | `storage_error` | 500 | 否 | 文件损坏或写入失败 |
| `ConfigError` | `config_error` | 500 | 否 | 缺密钥、未知提供商 |

对外统一为 `ErrorResponse {ok:false, code, message, http_status, retryable, details}`。

## 6. 服务接口：`GameGeneService`（界面与 HTTP API 唯一调用的对象）

| 方法 | HTTP | 说明 |
|---|---|---|
| `get_interview()` | — | 访谈题目 |
| `build_profile(ProfileRequest)` | `POST /api/profiles` → 201 | 工作流一 |
| `get_profile(id)` | `GET /api/profiles/{id}` | |
| `list_profiles()` | — | |
| `recommend(RecommendRequest)` | `POST /api/recommendations` → 200（`status=error` 时 502） | 工作流三 |
| `get_run(id)` | `GET /api/runs/{id}` | 后续读取 |
| `list_runs(profile_id?)` | `GET /api/runs?profile_id=` | 新的在前 |
| `catalog_stats()` | `GET /api/catalog/stats` | |
| — | `GET /api/health` | |

请求体格式错误（缺字段、类型不对、`top_k` 越界）由 API 层直接返回 400 `invalid_input`，不进入服务。

## 7. 其他协议（`contracts/protocols.py`）

- `LLMClient.complete_json(system, user, schema) -> schema 实例`：见 `llm/`，已实现；测试用 `FakeLLM`。
- `SteamStoreClient`（A 实现）：`get_app_details` / `get_reviews` / `get_tags`。
- `SteamLibraryClient`（A 实现，B 使用）：`resolve_steam_id` / `get_owned_games`；B 开发期用 `FakeSteamLibraryClient`。
- `CatalogReader`：`list_games` / `get_game`；`FixtureCatalog` 与 `StoreCatalog` 已实现。

## 8. 完整样例

样例记录见 `src/gamegene/resources/fixture_catalog.json`（合成数据）；运行 `uv run gamegene serve`
并完成一次推荐后，可在 `data/store/demo/` 下看到真实落盘的画像与运行文件。
