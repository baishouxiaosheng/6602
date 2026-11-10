# 开发 A 交接说明 · 数据侧（工作流二：目录与证据流水线）

你负责把“一串 AppID”变成“带九维基因和已核验证据句的游戏目录”。推荐侧（开发 B）和界面只读你写出的
`data/store/catalog/<appid>.json`，所以**你的产物就是接口**：能通过 `GameRecord` 校验写进存储，就是对的。

## 0. 开始前（30 分钟）

```bash
uv sync
uv run pytest -q -m dev_a      # 19 项全部 skipped = 你的待办清单
uv run gamegene serve          # 看一眼界面，了解你的数据最终如何被展示
```

按顺序读：`AGENTS.md` → `docs/01-architecture.md` → `docs/02-gene-schema.md` → `docs/05-catalog-pipeline-spec.md`
→ `docs/03-data-contracts.md` §1–2、§5。然后读你要改的文件里的 docstring：每个桩函数都写明了输入、输出和边界情况。

你只改这些文件：`src/gamegene/steam/*.py`、`src/gamegene/catalog/{annotator,verifier,pipeline}.py`、
`src/gamegene/prompts/annotate_genes_v1.md`、`data/seed/appids.csv`，以及新增 `docs/calibration.md`。
（`steam/library.py` 里的 `FakeSteamLibraryClient` 和 `catalog/reader.py` 是框架代码，不要动。）

## 1. 任务清单

每个任务：把对应函数里的 `raise NotImplementedError` 换成实现，签名不变；对应测试从 skipped 变 passed 即完成。

| 编号 | 内容 | 文件 | 验收测试 | 预估 |
|---|---|---|---|---|
| **A1** | 节流 HTTP：共享 `httpx.Client`、同主机最小间隔、错误映射（超时/连接/5xx→`UpstreamError`，429→`RateLimited`，404→`NotFound`，非 JSON→`UpstreamError`）、`retry_call(attempts=3)` | `steam/http.py` | `test_a1_*`（4） | 0.5 天 |
| **A2** | 商店客户端：`get_app_details` / `get_reviews`（翻页、丢弃 < 80 字符的评测）/ `get_tags`（失败返回 `{}`）；原始快照读写 | `steam/store.py` | `test_a2_*`（2） | 1 天 |
| **A3** | `normalize_store_info` 纯函数 | `steam/store.py` | `test_a3_*`（2） | 0.5 天 |
| **A4** | 库客户端：`resolve_steam_id`（四种输入形式）/ `get_owned_games`（空响应→`SteamProfilePrivate`） | `steam/library.py` | `test_a4_*`（2） | 0.5 天 |
| **A5** | `build_passages` + `annotate`（渲染提示词、调用模型、确定性降级） | `catalog/annotator.py` | `test_a5_*`（2） | 1 天 |
| **A6** | `normalize_text` / `match_score` / `grade_evidence` 纯函数 | `catalog/verifier.py` | `test_a6_*`（2） | 0.5 天 |
| **A7** | `build_record` / `process_game` / `run_batch`：状态机、失败不覆盖、批处理报告 | `catalog/pipeline.py` | `test_a7_*`（5） | 1.5 天 |
| **A8** | 模型小比较 + 种子池扩到约 300 款 + 全量标注 + 校准记录 | `data/seed/appids.csv`, `docs/calibration.md` | 见 §3 | 2–3 天 |

建议顺序 A1 → A2 → A3 → A6 → A5 → A7 → A4 → A8。A4 是开发 B 的库导入功能所依赖的，尽量在第 3 天前完成并告知 B。

## 2. 关键约束（容易踩的地方）

1. **先实测端点**。`docs/05` 的接口信息未经本环境实测。做 A2 / A4 前各发一次真实请求，把响应（去掉密钥后）存成
   `tests/fixtures/` 下的新文件；如与文档不符，以实测为准并更新 `docs/05`。现有两个 fixture 是手写的形状样例。
2. **模型输出不可信**。引文必须在它声称的那一段缓存原文里被 `match_score` 找到；找不到就是未知，绝不保留等级。
   不要为了让更多游戏变成 `verified` 而放宽 `FUZZY_MIN` 或手改 JSON。
3. **等级 0 也要证据**；“没提到”不等于 0，而是未知。
4. **先存 PENDING 再调模型**；失败写 `FAILED + review_note`；已有 `VERIFIED` 不被失败覆盖。
5. **节流与额度**。Steam 商店端点 ≥ 1.5 秒 / 次；OpenRouter 全量前先 `--limit 5` 试跑看花费（`docs/05` §7），给推荐解释留一半额度。
6. **测试不联网**。`ThrottledHttp` 的 `transport` / `sleep` / `clock` 参数就是为测试注入准备的。
7. 密钥只放 `.env`；日志里不要打印带 `key=` 的完整 URL。
8. 提示词里的基因表与等级说明用代码从 `gamegene.contracts.genes` 生成，不要手抄进模板。

## 3. A8 的完成标准

- `data/seed/appids.csv` 约 300 行，符合 `data/seed/README.md` 的选取规则，每个 AppID 实际核对过。
- `uv run gamegene catalog build --appids data/seed/appids.csv` 可重复执行（已 `verified` 的自动跳过），批处理报告落在 `data/store/reports/`。
- `uv run gamegene catalog stats`：`verified` ≥ 200（达不到时在校准记录里说明原因，不要降低标准凑数）。
- `docs/calibration.md` 包含：模型比较表与选型结论；已知维度数与证据等级的分布；被拒引文的比例和典型例子；
  30 款人工抽查结果（`docs/02` §7）；最终使用的模型、提示词版本、总花费。
- 把 `.env` 设为 `GAMEGENE_CATALOG=store` 启动界面，推荐卡片上显示的是真实证据句和可点击的来源。

## 4. 交回

- 有仓库权限：每个任务一个分支一个 PR（见 `CONTRIBUTING.md`）。
- 没有：全部完成后按 `CONTRIBUTING.md` 末尾的方法打一个 zip 交回，**另附** `data/store/catalog/` 与 `data/store/reports/`
  打成的 `catalog-data.zip`（这是运行时数据，不在版本库里）。不要包含 `.env`、`.venv`、`data/raw/`。
- 交回前自查：`uv run pytest -q -m dev_a` 无 skipped 无失败；`uv run pytest -q` 整体无失败；`uv run ruff check .` 通过。

## 5. 遇到问题

契约、阈值、验收测试与文档矛盾，或你认为规格有误：不要改 FROZEN 文件或测试去迁就，直接找设计负责人，
说明“哪个文件哪一行、你期望什么、实际是什么”。规格范围内的实现细节（辅助函数、内部数据结构）自行决定。
