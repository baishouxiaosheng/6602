# 05 · 目录与证据流水线规格（工作流二，开发 A）

> **先核实再依赖**：本节的 Steam / SteamSpy 接口信息整理自公开资料与社区文档，撰写时未能在本环境中逐一实测。
> 任务 A2、A4 的第一步是对每个端点发一次真实请求，把响应存入 `tests/fixtures/`，发现与本文不符之处以实测为准并更新本文。

## 1. 端点

| 用途 | 请求 | 关键响应字段 | 备注 |
|---|---|---|---|
| 商店详情（无需密钥，非官方） | `GET https://store.steampowered.com/api/appdetails?appids=<id>&cc=us&l=english` | `{"<id>": {"success": bool, "data": {...}}}`；`data` 含 `type, name, is_free, short_description, detailed_description(HTML), supported_languages(HTML), header_image, developers, price_overview{currency,initial,final,discount_percent}, platforms{windows,mac,linux}, categories[{description}], genres[{description}], release_date{date}` | 一次只查一个 appid；约 200 次 / 5 分钟 / IP（社区经验值）；下架或锁区返回 `success:false`；免费游戏没有 `price_overview`；价格单位为分；**不含用户标签** |
| 评测（无需密钥） | `GET https://store.steampowered.com/appreviews/<id>?json=1&filter=recent&language=english&purchase_type=all&num_per_page=100&cursor=*` | `success, query_summary{review_score_desc,total_reviews,…}`（仅首页）, `cursor`, `reviews[{recommendationid, review, voted_up, votes_up, language, author{playtime_forever}}]` | `cursor` 需 URL 编码；评测列表为空或 cursor 重复即停止；`filter=all` 翻页不可靠。有资料称该地址将被 `IUserReviewsService/GetAppReviews` 取代（未核实），因此评测访问封装在 `SteamStoreClient.get_reviews` 之后，便于替换 |
| 用户标签（SteamSpy，无需密钥） | `GET https://steamspy.com/api.php?request=appdetails&appid=<id>` | `tags: {标签: 票数}` | 约 1 次 / 秒；失败或无标签返回 `{}`，不影响流水线 |
| 解析自定义链接（需密钥） | `GET https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/?key=K&vanityurl=<name>` | `response.success`（1 成功，42 未找到）, `response.steamid` | |
| 已拥有游戏（需密钥） | `GET https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/?key=K&steamid=<id64>&include_appinfo=1&include_played_free_games=1&format=json` | `response.game_count`, `response.games[{appid, name, playtime_forever(分钟)}]` | **资料不公开时返回 HTTP 200 且 `response` 为空对象**：必须识别为 `SteamProfilePrivate`，不能当作 0 款游戏 |

通用：节流 ≥ 1.5 秒 / 请求（`STEAM_MIN_INTERVAL_S`）；429 与 5xx 走 `retry_call` 退避；User-Agent 用通用客户端名，不带个人信息；
固定 `cc` 与 `l` 并写入 `StoreInfo`（价格和语言随地区变化）。

## 2. 原始快照

每次成功响应写入 `data/raw/<appid>/{appdetails,reviews,tags}.json`，带 `fetched_at`。之后默认读快照（`refresh=False`）。
300 款 × 3 个文件很小；开发期间不要重复抓取。快照目录不进版本库。

## 3. 规范化：`normalize_store_info`（纯函数）

映射规则见 `steam/store.py` 的 docstring：genres / tags 小写；tags 取票数前 20；platforms 取为真的键；
social_modes 由 categories 推出（`Single-player`→single，含 `co-op`→coop，含 `pvp`→pvp，`MMO`→mmo）；
`supported_languages` 去 HTML 标签和 `*` 后按逗号拆分并丢弃“languages with full audio support”脚注；
免费或无 `price_overview` → `price=None`。

## 4. 标注

1. `build_passages`：商店描述按段落拆分并去 HTML（`source_type=store_description`，`source_ref`=商店链接）；
   随后最多 30 条评测，按 `votes_up` 降序，每条截断到 1200 字符（`source_ref`=`recommendationid`）。
   每段有连续编号 `index`。总长 ≤ 24k 字符，超出时先丢票数最少的评测。
2. 提示词 `prompts/annotate_genes_v1.md`：占位符 `{{LEVEL_SCALE}}`、`{{GENE_TABLE}}`（从 `contracts.genes` 生成，不要手抄）、
   `{{NAME}}`、`{{TAGS}}`、`{{PASSAGES}}`。
3. `llm.complete_json(schema=AnnotationOut)`，`temperature=0.2`。
4. 确定性后处理（模型输出只是“主张”）：必须恰好九条、每个基因一条；有等级但缺引文或缺段落编号 → 置为未知；
   置信度不是 `high` → 置为未知。

## 5. 核验与分级：`catalog/verifier.py`（纯函数）

对每条有等级的主张：在它声称的那一段里算 `match_score`；
评测引文还要统计“有多少条**不同**评测包含这句话”（`supporting_reviews`）；然后查 02 §4 的等级表。
被拒绝的主张 → `GeneValue(level=None, unknown_reason="evidence_unverified")`。
模型本就回答 null 的 → `unknown_reason="no_evidence"`；因置信度被降级的 → `"low_confidence"`。

## 6. 状态机与批处理：`catalog/pipeline.py`

```
(无) ──抓取成功──▶ PENDING（先落盘）──标注+核验──▶ VERIFIED（已知 ≥ 5）
                      │                        └──▶ PARTIAL （已知 < 5，review_note 说明）
                      └──任一步出错──▶ FAILED（review_note = 步骤 + 错误信息）
```

- 先存 `PENDING` 再调模型：模型失败不丢失抓取结果。
- **失败不覆盖已有的 `VERIFIED` 记录**：保留旧记录，只在批处理报告里记失败。
- 重跑默认跳过 `VERIFIED`（`force=True` 才重做）。
- `process_game` 不向外抛 `GameGeneError`，一律转成 `ItemReport(outcome="failed", step=…, error_code=…, message=…)`。
- `run_batch` 逐个处理，单个失败不中断；结束写 `reports/catalog-batch-<UTC 时间>.json`。
- 命令：`uv run gamegene catalog build --appids data/seed/appids.csv [--limit N] [--force]`，`uv run gamegene catalog stats`。

## 7. 模型选择与额度

- 课程 OpenRouter Key：20 美元一次性额度，仅限批准的开源模型（DeepSeek、GLM、MiMo、MiniMax、Kimi、Mistral 等家族中对本组 Key 开放的条目）。
- 先做小比较（计划书第 2 节）：同 5 款游戏 × 2–3 个候选模型，比较 ① 首次回答即通过契约的比例 ② 引文核验通过率 ③ 单款成本与耗时。
  结果写入 `docs/calibration.md`，选定模型写入 `.env.example` 的 `LLM_MODEL`。
- 每款约 1 次调用、输入约 6–8k tokens。全量前务必 `--limit 5` 试跑并在 OpenRouter 后台看实际花费，再估算 300 款总额；
  预留至少一半额度给推荐解释与演示。

## 8. 校准（阶段二交付物 `docs/calibration.md`）

按 `doc_level`（rich / medium / thin）各抽若干款，记录：已知维度数分布、证据等级分布、被拒绝引文的比例与典型原因、
人工抽查与标注的差异（02 §7）。据此决定是否需要调整提示词（升 `PROMPT_VERSION`）或把 `FUZZY_MIN` 之类的阈值提请设计负责人修改。
