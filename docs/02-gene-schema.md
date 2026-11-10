# 02 · 九维游戏基因结构（已冻结，版本 1.0）

唯一权威来源是 `src/gamegene/contracts/genes.py`；本文档是它的说明。提示词与界面都从代码读取定义，
修改任何一项都需要 ADR 并升级 `GENE_SCHEMA_VERSION`（旧标注随即失效，需要重跑）。

## 1. 设计依据

- 维度骨架取自 **Quantic Foundry 玩家动机模型**（12 项动机 / 6 组，基于大样本因子分析，是目前实证支持最好的框架），
  并用 **MDA 框架**的八种“美学”做交叉核对。
- 把 12 项动机合并为 9 个**可以在商店页与评测里找到原句佐证**的设计维度：无法被文本证据支持的维度没有意义。
- 基因描述的是“游戏靠什么吸引人”，与表层类型（Steam genres / tags）刻意分离：
  表层类型只用于划分同类轨与其他轨，不参与相似度。

## 2. 九个维度

| # | id | 中文名 | 标注时回答的问题 | 低分（0–1）的样子 | 满分（4）的样子 | 依据 |
|---|---|---|---|---|---|---|
| 1 | `challenge` | 操作挑战 | How much does success depend on practiced skill, precision and overcoming failure? | Cannot really fail; no skill ceiling (walking sim, idle game). | Demanding execution, repeated failure is the core loop (precision platformer, soulslike). | Quantic Foundry: Mastery/Challenge; MDA aesthetic: Challenge |
| 2 | `strategy` | 策略深度 | How much does success depend on planning, optimisation and weighing trade-offs? | Decisions are obvious or purely reactive. | Long-horizon planning with many interacting systems (4X, deckbuilder, factory builder). | Quantic Foundry: Mastery/Strategy |
| 3 | `pace` | 节奏强度 | How fast and intense is moment-to-moment play (time pressure, action density)? | Untimed, contemplative, the game waits for the player. | Constant real-time pressure and high action density (arena shooter, action roguelike). | Quantic Foundry: Action/Excitement + Destruction; MDA aesthetic: Sensation |
| 4 | `progression` | 成长积累 | How much of the appeal is getting stronger, unlocking, collecting and completing over time? | Nothing persists or grows; every session starts equal. | Long unlock trees, loot, levels, meta-progression or completion lists drive play. | Quantic Foundry: Achievement/Power + Completion |
| 5 | `exploration` | 探索发现 | How much is play driven by finding unknown places, secrets and mechanics on your own? | Linear, fully signposted, nothing to find off the path. | Curiosity is the main drive; knowledge of the world is the reward (metroidvania, open world). | Quantic Foundry: Creativity/Discovery; MDA aesthetic: Discovery |
| 6 | `creation` | 创造表达 | How much can players build, design or express something that is their own? | No customisation; every player ends with the same result. | The player's own constructions are the content (sandbox, builder, automation). | Quantic Foundry: Creativity/Design; MDA aesthetic: Expression |
| 7 | `narrative` | 叙事 | How much is play driven by authored story, characters and dialogue? | No story beyond a premise. | Story and characters are the reason to play; mechanics serve them (narrative RPG, visual novel). | Quantic Foundry: Immersion/Story; MDA aesthetic: Narrative |
| 8 | `immersion` | 世界沉浸 | How much does the game rely on atmosphere, sense of place and being someone/somewhere else? | Abstract presentation; theme is interchangeable. | Atmosphere and world are central to the experience, independent of plot. | Quantic Foundry: Immersion/Fantasy; MDA aesthetic: Fantasy + Sensation |
| 9 | `social` | 社交依赖 | How much does the core experience depend on playing with or against other people? | Strictly single-player. | The game barely works alone; co-operation or competition is the content. | Quantic Foundry: Social/Competition + Community; MDA aesthetic: Fellowship |

## 3. 等级（所有维度通用）

| 等级 | 含义 |
|---|---|
| 0 | absent: the game does not contain this at all |
| 1 | minor: present but incidental, players rarely mention it |
| 2 | supporting: a real part of the game, but not why people play it |
| 3 | major: one of the main reasons people play it |
| 4 | defining: the game is built around it; removing it removes the game |
| `null` | **未知**：没有通过核验的证据。不是 0，也不是猜测。 |

判定提示：先问“删掉它游戏还成立吗”（成立不了 = 4）；再问“评测里玩家会不会主动提到它”（会 = 至少 3）。
等级 0 同样需要证据（例如商店页写明“纯单人体验”可支持 `social = 0`）。

## 4. 证据与等级

每个已知等级至少对应一条 `Evidence`：一句**逐字摘自来源**的原文 + 来源类型 + 来源定位 + 匹配分 + 证据等级。

| 证据等级 | 条件（`catalog/verifier.py: grade_evidence`） |
|---|---|
| **A** | 引文在**官方文本**（商店描述 / 官方文档）的缓存快照中逐字出现（匹配分 = 1.0） |
| **B** | 引文在 **Wiki** 中逐字出现；或在**至少两条**不同用户评测中逐字出现 |
| **C** | 只在一条评测中出现；或只是模糊匹配（0.85 ≤ 匹配分 < 1.0） |
| 拒绝 | 匹配分 < 0.85：视为模型编造，该维度记为 `null`（`unknown_reason = "evidence_unverified"`） |

匹配分：引文与来源都做规范化（小写、去 HTML、统一引号与空白）后，子串命中 = 1.0，否则取滑动窗口上的最佳相似度。
核验对象永远是 `data/raw/` 里的**缓存快照**，不是实时网页（评测会被编辑或删除）。

## 5. 目录记录的状态

| 状态 | 条件 | 能否被推荐 |
|---|---|---|
| `verified` | 已知维度 ≥ 5 | 能 |
| `partial` | 已知维度 < 5 | 不能（过滤原因 `not_verified`） |
| `pending` | 已抓取、未标注 | 不能 |
| `failed` | 流水线出错，`review_note` 写明原因 | 不能 |

## 6. 推荐时如何使用证据

- **共同基因**：用户目标值 ≥ 2.5 且游戏等级 ≥ 3 的维度，取该维度等级最好的一条证据展示。
- **证据门槛**：匹配分 ≥ 0.72 **并且**至少一个共同基因的证据为 A 或 B 级，才允许推荐。
- 未知维度不参与相似度，但会降低“基因覆盖”，从而按比例压低得分，并在界面上列出。

## 7. 有效性检查（开发 A 在校准阶段完成，结果写入 `docs/calibration.md`）

1. 人工抽查 30 款 × 9 维：与标注等级相差 ≥ 2 的比例应低于 10%。
2. 标签一致性：例如带 `souls-like` / `difficult` 标签的游戏，`challenge` 的平均等级应明显高于不带的。
3. 重复标注稳定性：同一游戏重跑两次，等级完全一致的维度比例。
