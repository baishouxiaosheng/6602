# 04 · 画像与推荐规格（工作流一、三）

标 **[已实现]** 的部分在冻结代码中；标 **[B]** 的部分由开发 B 按本规格实现。数值以代码和验收测试为准。

## 1. 访谈计分 **[已实现]** `profile/interview.py`

题目在 `resources/interview_v1.json`：10 道三选一的强制选择题（每个选项带若干基因增量）+ 1 道多选题（熟悉的类型，选 1–4 项）。

```
target_i = clamp(2.0 + Σ 所选选项对基因 i 的增量, 0, 4)
weight_i = min(1, 0.4 + 0.3 × |target_i − 2|)        # 态度越鲜明，权重越高；中立维度权重 0.4
familiar_tags = 所选类型选项里的全部标签，权重 1.0
```

校验一次性报告全部问题（漏答、未知题目、未知选项、选择数量不对）。

## 2. Steam 库融合 **[B]** `profile/library.py`

```
matched  = 已拥有 ∩ 目录中 verified ∩ 游戏时长 ≥ 60 分钟
w_game   = ln(1 + 游戏小时数)
对每个基因 i：
  lib_i  = matched 中“该基因已知”的游戏的等级按 w_game 加权平均（未知的跳过）
  beta_i = min(0.5, 0.1 × 该基因已知的 matched 游戏数)
  target_i' = (1 − beta_i) × target_i + beta_i × lib_i ；weight 按 §1 公式用 target_i' 重算；均保留两位小数
标签：tag_w = Σ w_game（对带该标签/类型的 matched 游戏）÷ 最大 tag_w ；与访谈标签按 max 合并
无 matched → 原样返回
```

含义：访谈是用户“说的”，游戏库是用户“做的”；库最多占一半权重，且需要 5 款以上匹配游戏才达到上限。

## 3. 工作流一编排 **[B]** `profile/builder.py`

1. **校验**（任何 Steam 调用之前）：昵称 1–40 字符；访谈答案合法；价格 ≥ 0；Steam 字段非空且 ≤ 200 字符；
   `profile_id` 给出但不存在 → `NotFound`。全部问题收集后一次抛出 `InvalidInput(problems=[…])`，不保存任何东西。
2. 访谈计分。
3. 若给了 Steam 链接：`resolve_steam_id` → `get_owned_games`，用 `retry_call(attempts=3)` 包裹。
   **失败不致命**：`SteamProfilePrivate` / `UpstreamError` / `NotFound` / 未配置密钥 → 保留仅访谈画像并追加一条中文 warning。
   成功 → §2 融合，`owned_appids` = 全部已拥有的 appid。
4. 修改已有画像：沿用 `profile_id`，`store.put` 产生新版本；本次未提供 Steam 时沿用上一版的 `owned_appids` 与 `steam_id`。
5. 新建：`profile_id = "p-" + 8 位小写十六进制`。保存并返回。

## 4. 硬过滤 **[B]** `recommend/filters.py`

按下列顺序检查，命中第一个原因即剔除并计数（`filter_drops`）：

| 顺序 | 原因 | 条件 |
|---|---|---|
| 1 | `not_verified` | `status != verified` |
| 2 | `excluded` | `appid ∈ profile.exclusion_set()` |
| 3 | `excluded_tag` | 任一排除标签**等于**游戏的某个 genre 或 tag（不区分大小写，整词相等，不做子串匹配） |
| 4 | `platform` | 用户选了平台，且与游戏平台无交集 |
| 5 | `social_mode` | 用户选了社交模式，且与游戏模式无交集 |
| 6 | `language` | 用户要求的语言不在游戏语言列表中 |
| 7 | `price` | 设了上限，游戏非免费，价格已知且 `final_cents > max`（价格未知放行） |
| 8 | `insufficient_genes` | `scoring.gene_score(...)` 返回 `None` |

返回（按输入顺序的幸存者，`{原因: 数量}` 仅含数量 > 0 的原因）。

## 5. 评分核心 **[已实现]** `recommend/scoring.py`

```
K = 游戏已知的基因；|K| < 5 → 不可评分
similarity = 1 − Σ_K w_i·|target_i − level_i| / (4 · Σ_K w_i)
coverage   = Σ_K w_i / Σ_全部 w_i
score      = similarity × (0.7 + 0.3 × coverage)

surface_overlap = Σ_{t ∈ 游戏的 genres ∪ tags} familiar[t]  ÷  用户最大的 n 个 familiar 权重之和
                  n = min(游戏标签数, 用户熟悉标签数)；任一为空 → 0
track = same_track 若 surface_overlap ≥ 0.30，否则 cross_track

共同基因 = target ≥ 2.5 且 level ≥ 3 且有证据的基因，按 weight × level 降序；每个取等级最好的一条证据
可推荐   = score ≥ 0.72 且 存在 A/B 级证据的共同基因                      ← 证据门槛
置信度   = high：score ≥ 0.82 且 coverage ≥ 0.8 且有 A 级共同基因；medium：可推荐；否则 low
barriers = 权重 ≥ 0.6 且 |target − level| ≥ 2 的基因；其他轨的表层类型；未知维度。最多 3 条
```

阈值（`STRONG_SCORE=0.72`、`CLOSEST_FLOOR=0.55`、`TRACK_OVERLAP=0.30`）是初值；阶段一用十个人工案例检验后，
如需调整由设计负责人改代码并补 ADR，开发不要自行修改。

## 6. 受约束的解释 **[B]** `recommend/explainer.py`

- 提示词 `prompts/explain_v1.md`：只提供画像、共同基因和它们的证据句；要求返回 `Explanation` JSON。
- `check_explanation`：1–3 条理由；每条的 `gene` 必须是共同基因之一；`evidence_id` 必须等于我们为该基因提供的那一条；基因不重复。
- `explain`：调用一次 `llm.complete_json`（适配层内部已有重试）；校验不过、`LLMOutputInvalid`、`UpstreamError`
  → 改用 `template_explanation`（确定性模板，永不失败），并返回 `fell_back=True`。
- 只为**最终展示**的游戏生成解释（省额度）：每条轨道 top_k 款，或 closest 的 1 款。
- 模型不参与“是否推荐”的任何判断。

## 7. 工作流三编排与分支 **[B]** `recommend/pipeline.py`

```
validate → route(mode) → load profile → hard filters → score → tracks → evidence gate → explain → save
```

| 分支 | 触发 | 结果 | 模型调用 |
|---|---|---|---|
| A | `request_id` 已被认领 | 原样返回已保存的运行 | 0 |
| B | `profile_id` 不存在 | 抛 `NotFound`，不保存 | 0 |
| C | `mode` 不在 `both / same_track / cross_track` | 保存并返回 `no_match`，`message` 写明该模式与可用模式；不读目录 | 0 |
| D | 硬过滤后 0 个候选 | `no_match`，`filter_drops` 说明原因 | 0 |
| E | 请求的轨道中至少 1 个可推荐 | `ok`；每轨按 (score 降序, appid 升序) 取 top_k | 展示数量 |
| F | 无可推荐，但最高分 ≥ 0.55 | `closest_only`，`closest` + `mismatch`（取 barriers 拼接） | 1 |
| G | 无可推荐，且最高分 < 0.55 | `no_match`（“没有足够匹配且证据充分的游戏”） | 0 |
| H | 读到画像之后出现其他 `GameGeneError`（存储、目录） | 保存并返回 `error`，`error = to_response()` | — |

- “最高分”与 closest 只在请求的轨道内取。`mode=same_track` 时 `cross_track` 为空，反之亦然。
- 模型失败**不是**分支 H：它被解释器吸收为模板回退，计入 `llm.fallbacks`。
- 每一步追加一条 `TraceStep`：`validate`、`route`（branch 写 `mode=…` 或 `no_matching_path`）、`hard_filters`（detail 含 drops）、
  `score`、`decide`、`llm_explain`（含 fallbacks）、`save`。顺序固定，`save` 最后。
- `run_id = "r-" + UTC 时间 yyyymmddHHMMSS + "-" + 4 位十六进制`。有 `request_id` 时用 `store.claim_request` 绑定。

## 8. 参考人设（合成样例目录上的期望结果，验收测试据此断言）

| 人设 | 访谈要点 | 同类轨 | 其他轨 |
|---|---|---|---|
| `roguelike` | 高挑战、快节奏、重成长、单人；熟悉肉鸽 | Dead Cells 0.9094，Hades 0.8478 | Hollow Knight 0.8170，Celeste 0.8007 |
| `builder` | 高策略、高创造、重成长、慢节奏；熟悉模拟建造 | Factorio 0.8569，RimWorld 0.8370 | Slay the Spire 0.8062 |
| `story` | 高叙事、高沉浸、高探索、低挑战；熟悉剧情冒险 | Outer Wilds 0.8646，Disco Elysium 0.8393 | Subnautica 0.7589 |

`roguelike` 排除上述四款后，最高分是 Terraria 0.6793（不可推荐）→ 分支 F；只剩 Disco Elysium（0.538）→ 分支 G。
答案组合见 `tests/conftest.py: PERSONAS`。
