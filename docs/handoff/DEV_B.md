# 开发 B 交接说明 · 推荐侧（工作流一：画像；工作流三：推荐与历史）

你负责把“访谈答案（+ 可选 Steam 库）”变成画像，再把“画像 + 目录”变成一次可回看的推荐运行。
界面和 HTTP API 已经做好，并且只调用 `GameGeneService` 这一个接口；你实现 `RealService`，把 `.env` 改成
`GAMEGENE_SERVICE=real`，界面就自动用上你的代码。

## 0. 开始前（30 分钟）

```bash
uv sync
uv run pytest -q -m dev_b      # 35 项全部 skipped = 你的待办清单
uv run gamegene serve          # 现在跑的是 DemoService：一个简化的参考实现
```

按顺序读：`AGENTS.md` → `docs/01-architecture.md` → `docs/04-recommendation-spec.md`（你的主规格）→
`docs/03-data-contracts.md` → `docs/06-testing-and-evidence.md`。
再读三个已经写好的文件，它们是你的积木：`recommend/scoring.py`（评分核心，直接调用，不要重写）、
`profile/interview.py`（访谈计分）、`app/demo_service.py`（简化参考，看懂流程即可，不要复制它的捷径）。

你只改这些文件：`src/gamegene/profile/{library,builder}.py`、`src/gamegene/recommend/{filters,explainer,pipeline}.py`、
`src/gamegene/app/real_service.py`、`src/gamegene/prompts/explain_v1.md`，新增 `scripts/collect_evidence.py`。

**你不需要等开发 A**：全程使用内置合成样例目录（`GAMEGENE_CATALOG=fixture`，17 款）和
`FakeSteamLibraryClient`、`FakeLLM`。A 完成后只需改环境变量。

## 1. 任务清单

| 编号 | 内容 | 文件 | 验收测试 | 预估 |
|---|---|---|---|---|
| **B1** | `blend_library`：游戏库融合（纯函数） | `profile/library.py` | `test_b1_*`（2） | 0.5 天 |
| **B2** | `validate_profile_request` + `build_profile`：先校验、访谈计分、可选库导入（失败降级为 warning）、新建 / 修改版本 | `profile/builder.py` | `test_b2_*`（5） | 1 天 |
| **B3** | `apply_hard_filters`：八种剔除原因，按固定顺序计数 | `recommend/filters.py` | `test_b3_*`（10） | 0.5 天 |
| **B4** | `template_explanation` / `check_explanation` / `explain`：受约束解释与模板回退 | `recommend/explainer.py` | `test_b4_*`（3） | 1 天 |
| **B5** | `recommend`：分支 A–H、trace、落盘、幂等 | `recommend/pipeline.py` | `test_b5_*`（10） | 2 天 |
| **B6** | `RealService`：薄封装，公开属性 `store / catalog / llm / steam / last_warnings` | `app/real_service.py` | `test_b6_*`（5，即课程五项测试） | 0.5 天 |
| **B7** | 证据收集脚本 + 用真实模型调好解释提示词 | `scripts/collect_evidence.py`, `prompts/explain_v1.md` | 见 §3 | 1–1.5 天 |

建议顺序 B3 → B1 → B2 → B4 → B5 → B6 → B7。

## 2. 关键约束（容易踩的地方）

1. **确定性在前**。校验失败时不得有任何 Steam 或模型调用（测试会断言调用次数为 0），也不得落盘。
2. **不要重写评分**。`gene_score` / `surface_overlap` / `assign_track` / `shared_genes` / `is_recommendable` /
   `confidence_for` / `barriers` 都在 `scoring.py`；阈值常量从那里 import，不要写死数字。
3. **模型不做决定**。只给最终要展示的游戏生成解释；解释不合规（引用了我们没给的证据 ID 或基因）就整条换成模板。
   模型失败不是错误运行：计入 `llm.fallbacks`，运行仍是 `ok`。
4. **解释器里不要再加重试**。`llm/` 适配层已有有限重试；`FakeLLM` 的脚本按调用次数消费，多调一次测试就会失败。
5. **Steam 导入失败不致命**。保留仅访谈画像 + 一条中文 warning（界面会显示 `service.last_warnings`）。
   重试用 `retry.retry_call(attempts=3)`，只对可重试错误生效。
6. **每个分支都要留 trace**。`step` 名称与顺序见 `docs/04` §7；`save` 永远是最后一步。运行保存后不再修改。
7. **`RealService` 的依赖要在调用时读取 `self.llm` / `self.steam`**（测试会在构造后替换它们）。没有 `STEAM_API_KEY` 时 `self.steam = None`。
8. 排序稳定：`(score 降序, appid 升序)`。浮点比较用 `scoring` 返回的四位小数值，不要自己再算一遍。
9. 所有给用户看的 `message` / warning 用中文；`code`、`branch`、`step` 用英文小写下划线。

## 3. B7 的完成标准

- `scripts/collect_evidence.py --base-url http://127.0.0.1:7860` 对运行中的服务依次执行五项测试，
  按 `docs/06` §3 的目录结构输出到 `evidence/<UTC 时间>/`，并生成 `summary.md`。只用标准库 + `httpx`。
- 强制错误按 `docs/06` §3 的表格触发；脚本或 `summary.md` 里写清每一项如何复现。
- 配好 `.env` 的 OpenRouter Key 后实际跑 10 次以上推荐：解释为中文、没有证据之外的事实、`fallbacks` 比例低于 20%。
  需要改提示词时把文件头的版本与 `PROMPT_VERSION` 一起升到 `explain-v2`，并在 PR 里写明改了什么、为什么。
- 检查输出里没有密钥；Steam ID 用测试账号。

## 4. 交回

- 有仓库权限：每个任务一个分支一个 PR（见 `CONTRIBUTING.md`）。
- 没有：全部完成后按 `CONTRIBUTING.md` 末尾的方法打一个 zip 交回，可另附一份 `evidence/` 样例。不要包含 `.env`、`.venv`、`data/store/`。
- 交回前自查：`uv run pytest -q -m dev_b` 无 skipped 无失败；`uv run pytest -q` 整体无失败；`uv run ruff check .` 通过；
  `GAMEGENE_SERVICE=real uv run gamegene serve` 下按 `docs/06` §5 手工冒烟一遍。

## 5. 与开发 A 的唯一交集

`SteamLibraryClient`（A 的任务 A4）。A 完成前你用 `FakeSteamLibraryClient`；A 完成后在 `RealService.__init__` 里构造
`HttpSteamLibraryClient(ThrottledHttp(min_interval_s=settings.steam_min_interval_s), settings.steam_api_key)`。
这是你代码里唯一 import `gamegene.steam` 的地方。

## 6. 遇到问题

契约、阈值、验收测试与文档矛盾，或你认为规格有误：不要改 FROZEN 文件或测试去迁就，直接找设计负责人，
说明“哪个文件哪一行、你期望什么、实际是什么”。规格范围内的实现细节自行决定。
