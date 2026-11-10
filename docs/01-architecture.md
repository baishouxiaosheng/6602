# 01 · 总体架构

## 1. 一句话

用户填写访谈（可选导入 Steam 库）→ 得到九维基因画像 → 在“已核验证据”的游戏目录中做硬过滤和基因相似度计算
→ 分成同类轨 / 其他轨 → 只有通过证据门槛的游戏才被推荐，并由语言模型在给定证据范围内写出解释 → 整次运行存档可回看。

## 2. 三个工作流与数据流

```
                 ┌──────────────── 工作流二：目录与证据（离线批处理，开发 A）────────────────┐
 data/seed/appids.csv ─▶ Steam 采集 ─▶ 原始快照 data/raw/ ─▶ LLM 基因标注 ─▶ 证据核验分级 ─▶ catalog/<appid>.json
                                                                                                │
 浏览器 / HTTP 客户端                                                                           ▼
   │  POST /api/profiles              工作流一：画像（开发 B）                         JSON Data Store
   ├────────────────────▶ 校验 ─▶ 访谈计分 ─▶ (可选) Steam 库融合 ─▶ profiles/<id>.json ◀──┐  data/store/
   │                                                                                        │
   │  POST /api/recommendations       工作流三：推荐与历史（开发 B）                         │
   └────────────────────▶ 校验 ─▶ 路由(mode) ─▶ 读画像+目录 ─▶ 硬过滤 ─▶ 评分/分轨 ─▶ 证据门槛
                                             ─▶ LLM 解释(失败回退模板) ─▶ runs/<run_id>.json ─┘
      GET /api/runs/<id>  ◀──────────────── 后续读取：原样返回已保存的运行与证据
```

三个工作流只通过**已保存的键**耦合（课程 Lec 6/9“两个场景通过一个键共享状态”）：

| 键 | 谁写 | 谁读 |
|---|---|---|
| `appid` → `catalog/<appid>.json` | 工作流二 | 工作流一（库融合）、工作流三 |
| `profile_id` → `profiles/<id>.json`（带版本） | 工作流一 | 工作流三 |
| `run_id` → `runs/<id>.json`；`request_id` → `requests/<id>.json` | 工作流三 | 历史读取、重复请求 |

## 3. 模块、归属与依赖方向

```
app/ui.py  app/api.py ──▶ contracts.GameGeneService ◀── app/real_service.py [B] / app/demo_service.py [FW]
                                   │
        profile/builder.py [B] ────┤──── recommend/pipeline.py [B]
          ├ profile/interview.py [FW]      ├ recommend/filters.py [B]
          ├ profile/library.py [B]         ├ recommend/scoring.py [FW]
          └ steam/library.py [A]           └ recommend/explainer.py [B] ──▶ llm/ [FW]
                                   │
 catalog/pipeline.py [A] ──▶ steam/store.py [A]  catalog/annotator.py [A] ──▶ llm/ [FW]  catalog/verifier.py [A]
                                   │
                      storage/json_store.py [FW]    contracts/ [FW]    retry.py [FW]
```

规则：依赖只能向下；`contracts/` 不依赖任何业务模块；A 与 B 的代码互不 import，只通过
`contracts.protocols` 与落盘的 JSON 见面。因此两人可以完全并行：

- B 不等 A：用内置**合成样例目录**（`GAMEGENE_CATALOG=fixture`，17 款）和 `FakeSteamLibraryClient` 开发。
- A 不等 B：产物是 `catalog/*.json`，由 `GameRecord` 模型校验，写得进去就是对的。
- 前端不等任何人：`DemoService` 已实现同一接口，`RealService` 完成后改一个环境变量即切换。

## 4. 技术选型（原因见 `docs/adr/`）

| 项 | 选择 | 说明 |
|---|---|---|
| 语言 / 包管理 | Python ≥ 3.11，`uv` | 锁文件保证三人与 CI 环境一致 |
| 界面 | Gradio 5（挂载在 FastAPI 上） | 一个进程同时提供 UI 与 HTTP API |
| 数据模型 | Pydantic v2，`extra="forbid"` | 契约漂移立即报错 |
| 存储 | 带版本信封的 JSON 文件，原子写入 | 首版无并发需求；SQLite 留作扩展 |
| 模型接入 | `openai` SDK + `base_url` 预设 | 默认 **OpenRouter**（课程发放的 Key 与批准模型），可切 DeepSeek / GLM / Gemini |
| 相似度 | 9 维加权距离，NumPy 都不需要 | 300 款规模下纯 Python 足够，且可逐项解释 |

## 5. 来自课程的五条设计原则（代码评审按此检查）

1. **确定性检查先于模型调用**（Lec 4）。校验、路由、硬过滤、评分全部是纯代码；非法输入在任何 Steam / 模型调用之前被拒绝。
2. **模型输出是 JSON 契约，先解析再使用**（Lec 4/8/9）。去掉代码围栏 → `json.loads` → Pydantic 校验；失败时把错误原文回传给模型重试，次数有上限。
3. **AI 给建议，规则做决定**（Lec 9）。是否推荐由 `scoring.is_recommendable` 决定；模型只写解释，且解释里引用的基因与证据 ID 必须来自我们提供的集合，否则丢弃改用模板。标注同理：模型给出的引文必须能在缓存原文中找到，否则该维度记为未知。
4. **每个失败都要落在人看得见的地方**（Lec 9）。目录记录有 `FAILED + review_note`；推荐运行有 `status=error + error`；画像导入失败给出 warning；批处理有逐条报告。不允许静默丢失。
5. **证据链而不是“返回了 200”**（Lec 5/6）。每次推荐运行保存 `trace`（请求 → 选中的分支 → 中间数据 → 保存结果），界面可展开查看，五项测试据此留证。

## 6. 与标准路线六项要求的对应

| 标准部件 | 本项目的等价物 | 代码位置 | 可观察的输入 → 输出 |
|---|---|---|---|
| Custom webhook | FastAPI 端点 + Gradio 事件处理器 | `app/api.py`, `app/ui.py` | 请求 JSON → `ProfileRequest`/`RecommendRequest` → 保存的记录 |
| Router | 模式路由、状态分支、证据门槛、硬过滤 | `recommend/pipeline.py`（分支 A–H）、`catalog/pipeline.py`（状态机） | `trace[].branch`、`filter_drops`、`status` |
| Data Store | 带版本的 JSON 存储 | `storage/json_store.py` | `data/store/{profiles,catalog,runs,requests}/` 文件及其 `revision` |
| Error handler | 结构化错误 + 有限重试 + 回退 | `contracts/errors.py`, `retry.py`, `explainer.py` | 强制故障 → `fallbacks` 计数 / `FAILED` 记录 / `ErrorResponse` |
| OpenRouter | 提供商无关适配层，默认 OpenRouter | `llm/` | 模型回答改变 `GameRecord.genes` 与 `Explanation`（`generated_by="llm"`） |
| Three scenarios | 三个相互关联的 Python 工作流 | `profile/`, `catalog/`, `recommend/` | 通过 `appid` / `profile_id` / `run_id` 交换数据 |

## 7. 范围

**做**：约 300 款精选目录；访谈画像 + 可选公开库导入；硬过滤（已拥有、平台、社交模式、语言、价格、排除标签）；
双轨推荐与证据展示；历史回看；五项测试的证据导出。

**不做**（首版）：抓取完整 Steam 目录、冷门游戏覆盖承诺、促销筛选、多用户并发、账号登录、SQLite、聚类覆盖分析。

## 8. 时间

期末展示为 11 月 20 日或 27 日。建议节奏（按 11 月 27 日场次；若抽到 20 日，目录规模先降到 100 款）：

| 截止 | 开发 A | 开发 B | 设计 / 前端 |
|---|---|---|---|
| 第 3 天 | A1–A4 采集可用 | B1–B3 画像与过滤 | 答疑，核对契约 |
| 第 6 天 | A5–A7 流水线跑通 30 款，校准 | B4–B6 推荐全分支通过 | 用真实服务联调界面 |
| 第 9 天 | 300 款目录 + 校准记录 | B7 五项测试证据脚本 | 演示脚本、截图 |
| 第 11 天 | 回传 | 回传 | 合并、彩排 |
