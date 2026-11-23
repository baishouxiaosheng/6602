# Game Gene Agent V1.3 — 系统架构与技术规格

> 状态：冻结开发基线（Frozen Development Baseline）
> 文档语言：中文；产品UI、Prompt、枚举值、证据原文和推荐结果：英文
> 优先级：本文件高于V1.2及此前讨论草稿

## 0. 文档使用规则

本文件是V1.3系统行为的唯一事实来源。代码、Agent任务说明或V1.2与本文件冲突时，以本文件为准。

未经团队确认，开发Agent不得改变：九维定义、画像来源优先级、证据语义、推荐阈值、双轨算法、程序召回与LLM终排的职责边界、英文版范围、技术栈和数据规模目标。

## 1. 产品目标与范围

系统从英文问卷、当前自由文本意图和公开Steam库存构建九维玩家画像；从Steam真实数据构建可复用的游戏基因目录；由确定性程序执行硬过滤、相似度计算和双轨召回；最后调用Qwen完成最终排序和英文解释。

V1必须真实展示三类AI任务：

1. Steam证据到九维游戏基因的标注；
2. 英文自由偏好的结构化解析；
3. 候选游戏的最终排序与推荐解释。

约300款游戏是预构建种子目录，不是产品永久上限。测试账号库存中不在目录的游戏也进入同一标注流程并扩充共享目录。

### 1.1 数据规模

| 阶段 | 要求 | 目的 |
|---|---:|---|
| 技术试验 | 5款真实游戏 | 跑通Steam→Qwen→证据→SQLite |
| V1-MVP | 30款，6类×5款 | 完成课程Demo |
| V1-Final | 约300款，6类×约50款 | 扩大种子目录 |
| 质量目标 | 至少200款`verified` | 不得放宽标准凑数量 |
| 时间不足 | 至少100款高质量目录 | 质量优先 |

### 1.2 V1不做

- 全Steam实时搜索；
- 用户注册、登录、权限和多租户；
- Redis、Celery、消息队列、微服务或Kubernetes；
- 多模型横向测评和模型微调；
- 汇率转换、历史最低价或多地区价格；
- SteamSpy依赖；
- 模型失败后用模板伪装成AI推荐成功；
- 大规模并发、压力测试和完整浏览器自动化。

## 2. 冻结技术栈

| 层 | 技术 |
|---|---|
| 前端 | React + TypeScript + Vite |
| 后端 | Python 3.11+ + FastAPI + Pydantic v2 |
| 数据库 | SQLite |
| HTTP | `httpx` |
| ORM | SQLAlchemy 2.x或SQLModel二选一，项目内不得混用 |
| LLM | 阿里云百炼Qwen，通过OpenAI-compatible接口 |
| 测试 | pytest；前端轻量单元/组件测试 |
| 依赖管理 | Python使用`uv`；前端使用`npm`锁文件 |

具体Qwen模型名通过环境变量配置，选择当时具有免费额度且支持结构化输出的模型，不写死在领域代码中。

```text
React Browser
    | JSON/HTTP
    v
FastAPI
    +-- ProfileService
    +-- SteamImportService
    +-- CatalogService
    +-- RecommendationService
    +-- JobService
    |
    +-- Steam Adapters
    +-- Qwen LLM Adapter
    +-- SQLite Repositories
```

耗时操作采用“进程内后台任务 + 前端轮询”；V1不使用WebSocket或分布式队列。

## 3. 九维游戏基因

所有维度使用整数`0..4`；证据不足必须为`null`，不能以0代替未知。

| ID | English Label | 定义 |
|---|---|---|
| `challenge` | Mechanical Challenge | 练习、精度、失败恢复和操作执行的重要性 |
| `strategy` | Strategic Depth | 规划、优化、权衡和资源决策的重要性 |
| `pace` | Pace Intensity | 实时压力和单位时间行动密度 |
| `progression` | Progression | 等级、装备、解锁和长期积累的重要性 |
| `exploration` | Exploration | 未知区域、秘密和发现的重要性 |
| `creation` | Creation | 建造、设计、自定义和玩家表达空间 |
| `narrative` | Narrative | 剧情、角色和对话对体验的驱动力 |
| `immersion` | Immersion | 氛围、世界一致性和代入感 |
| `social` | Social Dependency | 核心体验对合作或竞争玩家的依赖 |

等级锚点：

| 等级 | 语义 |
|---:|---|
| 0 | 有明确证据证明不存在或不构成体验 |
| 1 | 可选、少量或影响很小 |
| 2 | 持续存在，但不是主要卖点 |
| 3 | 主要玩法或吸引点之一 |
| 4 | 核心循环围绕该维度构建，移除后体验根本改变 |

原文证明“机制存在”不等于支持具体强度，因此来源可信度和等级支持度必须分开保存。

## 4. 人工种子目录

团队提供版本化CSV：

```text
appid,sampling_bucket,selection_reason,added_by,batch,replacement_for
```

| Sampling Bucket | MVP | Final Target |
|---|---:|---:|
| Action | 5 | 约50 |
| Adventure | 5 | 约50 |
| RPG | 5 | 约50 |
| Strategy | 5 | 约50 |
| Simulation | 5 | 约50 |
| Casual | 5 | 约50 |

规则：

- 游戏必须至少具有上述一个Steam官方genre；
- `sampling_bucket`必须来自该游戏的官方canonical genres；
- 多类型游戏只在一个桶计数，但保留全部genres用于轨道划分；
- `Indie`、`Free to Play`、`Early Access`不作为玩法桶；
- 每桶包含热门、中等和相对小众游戏，避免同系列集中；
- 不因标注失败偷偷换游戏；客观下架/不可访问允许替换，但记录原AppID和原因；
- `sampling_bucket`不参与过滤、分数或轨道算法。

## 5. Steam数据契约

| 数据 | 来源 | 用途 |
|---|---|---|
| 库存与时长 | `IPlayerService/GetOwnedGames` | 画像与排除已拥有游戏 |
| 英文评论 | `IUserReviewsService/GetAppReviews` | 低优先级补充证据 |
| 商店详情 | public Steam Storefront `appdetails` | 描述、genres、categories、平台、语言、价格 |
| 种子AppID | 团队CSV | 目录构建入口 |

`appdetails`是公开端点，但不被描述为有稳定正式契约的Steamworks API；成功响应写入SQLite缓存。刷新失败可使用旧缓存，无缓存则标记采集失败。

固定地区设置：

```text
country = US
language = English
currency = USD
```

免费游戏价格为0；不可购买、地区受限或价格缺失为`null`。用户设置价格上限后，价格未知采用fail-closed。

Steam库存规则：

- 接受SteamID64或可解析的公开主页链接；
- 未明确同意前不得调用库存接口；
- 测试账号Game details必须公开；
- 私密/失败时保留纯问卷画像；
- 不请求密码，不模拟登录；
- Steam Key只存在后端；
- 包含玩过的免费游戏，以便画像和排除。

Steam文本是不可信数据：必须结构化分隔，Prompt声明其不是指令；删除URL、代码块和极端重复；限制长度；排序模型不读取原始评论；AppID和`evidence_id`使用白名单校验。

## 6. 证据模型

V1.3取消含义混杂的A/B/C等级，使用三个独立字段：

```text
source_priority: high | medium | low
trace_status: verified | rejected
level_support: supported | uncertain
```

| Priority | 来源 |
|---|---|
| `high` | Steam官方开发者描述或功能说明直接支持 |
| `medium` | 官方genres/categories通过预先书写的确定映射支持 |
| `low` | 至少三条独立、方向一致的英文评论支持 |

评论独立性要求不同Review ID、不同作者且文本非重复。评论冲突时写`uncertain`或`null`，不能通过平均制造确定性。

证据结构：

```json
{
  "evidence_id": "ev_...",
  "appid": 123,
  "gene_id": "strategy",
  "source_type": "official_description",
  "source_priority": "high",
  "trace_status": "verified",
  "level_support": "supported",
  "quote_original": "Exact English passage...",
  "source_locator": "appdetails.about_the_game",
  "source_record_id": "src_..."
}
```

非空基因必须满足：

```text
trace_status == verified
and level_support == supported
```

`suggested_level`可用于诊断，但不参与评分。等级0需要明确否定证据或书面确定性规则；页面未提及只能是`null`。

游戏状态：

```text
pending -> partial | verified | failed
```

游戏成为`verified`必须同时满足：

```text
有效非空基因 >= 5
其中high/medium来源基因 >= 3
身份与canonical genre字段有效
```

`verified`只表示目录准入，不表示客观科学真理。

### 6.1 Demo语义人工检查

不人工检查300×9。真实运行得到最多6款展示游戏后，只检查实际展示的匹配点、劝退点和引文：

- 只能标记`approved`或`rejected`；
- 拒绝后该事实置`null`并重新评分/排序；
- 不为美化结果手工修改等级；
- 未展示事实可保持`pending`。

## 7. 游戏目录标注工作流

触发来源：团队种子CSV，以及测试账号库存中目录尚不存在的全部游戏。库存游戏成功处理后进入共享目录，但仍对其拥有者排除推荐。

### 7.1 Stage A：官方信息标注

每款最多约8,000字符，输入：AppID、名称、英文简介、官方genres/categories、平台、语言、功能字段、等级锚点和输出schema。

输出：九维建议、证据、来源字段和有证据的descriptors（如`horror_theme`、`pixel_graphics`）。后端负责原文存在性与确定映射校验。

### 7.2 Stage B：评论补充

仅当Stage A少于5个有效基因时执行；输入最多约6,000字符，只包含缺失维度、精选英文评论、Review ID/匿名作者标识和已有官方事实。

- 评论只补缺失/不确定维度；
- 不能覆盖high/medium官方事实；
- 至少三条独立一致评论才形成low证据；
- 仍不足则保持`partial`。

### 7.3 模型输出失败

每次调用先做JSON Schema、Pydantic和业务校验；失败后携带错误只修复重试一次；仍失败则真实失败。不得用模板生成游戏基因或伪装成功推荐。

## 8. 用户画像工作流

优先级：

```text
明确硬条件
> 当前英文自由补充
> 问卷初始画像
> Steam库存行为信号
```

硬条件与基因偏好独立，行为推断不得覆盖硬条件。

### 8.1 问卷和权重

- 第1–9题确定九维`target=0..4`；
- 第10题选择最多3项本次最重要的基因；
- 被选基因`weight=2`，其他`weight=1`；
- target高低不能自动推断weight；
- 问卷映射存放在唯一的版本化配置并由单测固定，LLM不得修改。

### 8.2 熟悉类型

- 从六个canonical genres选择1–3个；
- 按熟悉度排序，权重依次为`3/2/1`；
- “想尝试的新类型”进入自由补充，不进入熟悉类型。

### 8.3 自由文本解析

Qwen返回：

```json
{
  "gene_adjustments": {"pace": -1},
  "soft_descriptor_preferences": ["pixel_graphics"],
  "potential_hard_constraints": ["controller_required"]
}
```

规则：

- 单个基因最多调整一级；
- 题材/画风不能强行映射为九维；
- soft descriptors只参与LLM终排；
- 潜在硬条件必须由用户确认，且只能来自固定allow-list；
- 无法验证的要求保留原文并标注不可严格验证，不能编造过滤能力。

### 8.4 库存画像

V1测试账号库存较少，导入并处理全部游戏：

- 全部owned AppID排除推荐；
- 未启动游戏不产生正向偏好；
- 普通时长只是弱信号；
- 用户可选择喜欢的游戏并说明喜欢的方面；
- 喜欢游戏不等于喜欢其全部九维；
- 明确喜欢的方面仅强化相应基因；
- 库存最多将问卷target向库存方向调整一级；
- 自由文本在库存调整后应用；
- `partial`库存游戏中已验证的单项基因可作为弱信号；
- `null/uncertain`不参与画像。

时长弱信号必须封顶，不能由一款超长游戏控制画像。具体确定性函数属于实现选择，但必须有单测。

画像需保存每个基因的贡献：

```json
{
  "gene_id": "challenge",
  "questionnaire_target": 3,
  "library_adjustment": 1,
  "text_adjustment": -1,
  "final_target": 3,
  "weight": 2,
  "sources": ["questionnaire", "owned_game:1245620", "free_text"]
}
```

## 9. 硬过滤

固定顺序：

1. 游戏不是`verified`；
2. 已拥有或显式排除；
3. 命中可验证的排除条件；
4. 平台不匹配；
5. 已确认的社交模式硬条件不匹配；
6. 语言不匹配；
7. 设置价格上限时价格未知或超过USD上限；
8. 已知基因少于5；
9. 缺少canonical surface genre。

用户明确设置硬条件时采用fail-closed。社交必须拆成：是否接受强制联网/玩家互动的硬条件，以及`social`强度软偏好，二者不可替代。

## 10. 相似度与推荐准入

共同已知集合为`K`：

```text
similarity = 1 - sum(w_i * abs(target_i - level_i))
                 / (4 * sum(w_i)), i in K

weighted_coverage = sum(w_i, i in K) / sum(w_i, all genes)

compatibility_score = similarity * (0.7 + 0.3 * weighted_coverage)
```

实现必须处理空集合、零分母、非法等级/权重和非有限数。

当前用户下的`recommendation_eligible`：

```text
game.status == verified
weighted_coverage >= 0.70
用户最高优先级3项中至少2项非null
全部硬过滤通过
```

如果提升权重的基因不足3个，按稳定的九维ID顺序补足优先级检查槽位。

匹配基因：

```text
target和level非null
abs(target - level) <= 1
证据verified且level supported
```

匹配点可为共同吸引、共同规避或强度相容。劝退点只能来自已知且有证据的大差异维度，未知不能伪装成劝退点。

## 11. 双轨算法

`U`为用户熟悉类型权重，`G`为候选canonical genre集合：

```text
surface_overlap = sum(weight[t] for t in U ∩ G) / sum(weight[t] for t in U)
```

```text
surface_overlap >= 0.50 -> same_track
surface_overlap < 0.50  -> cross_track
```

缺少canonical genre不得进入任何轨道。类型只决定轨道，不进入九维相似度。

## 12. 程序召回与Qwen终排

正式候选：

```text
recommendation_eligible == true
compatibility_score >= 0.72
至少一个有效匹配基因
```

程序按`(compatibility_score DESC, appid ASC)`在每轨召回最多5款；这只是召回顺序，不是最终展示顺序。

每款传给Qwen的精简事实包仅包含：AppID、名称、轨道、compatibility、最多3个重点匹配基因、最多2个最大已知差异、每个展示基因最多1条最佳证据、相关verified descriptors、来源优先级和evidence IDs。不得发送原始评论全文。

Qwen排序优先级：

1. 用户最高权重基因；
2. 整体compatibility；
3. 避免明显劝退点；
4. 证据强度和完整性；
5. 当前soft descriptors；
6. 不使用未提供的热度、销量或模型记忆。

Qwen可以完全重排Top 5，但不能跨轨、选择白名单外游戏、修改基因/分数、生成第二套AI分数、引用未知证据或使用模型记忆补事实。

一次结构化调用同时输出每轨最多Top 3与英文解释：

```json
{
  "same_track": [{
    "appid": 123,
    "rank": 1,
    "ranking_reason": "...",
    "matched_gene_ids": ["strategy"],
    "evidence_ids": ["ev_..."],
    "caution": null
  }],
  "cross_track": []
}
```

后端校验AppID、轨道、rank唯一性、gene ID、证据归属和最大数量。UI显示`AI Recommendation Rank`和确定性的`Gene Compatibility`，不显示模型虚构分数。

### 12.1 Closest与No Match

- `score >= 0.72`：formal；
- `0.55 <= score < 0.72`：仅在该轨无formal时可作为closest；
- `< 0.55`：no-match。

Closest必须明确提示并说明未满足项；不得降证据、覆盖率或硬过滤凑满。任一轨可为空。

## 13. LLM适配器

```python
class LLMClient(Protocol):
    async def annotate_official(self, request): ...
    async def supplement_reviews(self, request): ...
    async def parse_preferences(self, request): ...
    async def rank_candidates(self, request): ...
```

```env
LLM_PROVIDER=aliyun_qwen
DASHSCOPE_API_KEY=...
QWEN_BASE_URL=...
QWEN_MODEL=...
STEAM_WEB_API_KEY=...
DATABASE_URL=sqlite:///./app.db
```

要求：优先JSON Schema；所有响应经Pydantic；只允许一次输出修复；供应商字段不泄漏到领域服务；FakeLLM仅用于测试，真实Demo不得使用。

## 14. SQLite数据模型

### 14.1 `games`

```text
appid PK, name, sampling_bucket nullable
catalog_status: pending|partial|verified|failed
genres_json, categories_json, platforms_json, languages_json, social_modes_json
price_usd_cents nullable, is_free
store_source_json, store_fetched_at
failure_code nullable, failure_message nullable
created_at, updated_at
```

### 14.2 `game_genes`

```text
id PK, game_appid FK, gene_id
level nullable, suggested_level nullable
level_support: supported|uncertain
semantic_review_status: pending|approved|rejected
annotation_stage: official|reviews
prompt_version, model_name, created_at
```

### 14.3 `evidence`

```text
evidence_id PK, game_gene_id FK
source_type, source_priority: high|medium|low
trace_status: verified|rejected
quote_original, source_locator, source_record_id
review_id nullable, review_author_hash nullable
raw_source_json nullable, created_at
```

### 14.4 `profiles`

```text
profile_id PK, questionnaire_version
questionnaire_json, free_text, familiar_genres_json
hard_filters_json, soft_preferences_json, gene_profile_json
owned_appids_json, steam_import_status
created_at, updated_at
```

### 14.5 `owned_games`

```text
profile_id, appid, playtime_minutes
is_favorite, liked_aspects_json, participates_in_profile
PRIMARY KEY(profile_id, appid)
```

### 14.6 `recommendation_runs`

```text
run_id PK, profile_id FK
status: running|ok|closest_only|no_match|failed
candidate_facts_json, llm_result_json nullable, validated_result_json nullable
error_code nullable, created_at, completed_at nullable
```

### 14.7 `jobs`

```text
job_id PK, job_type: steam_import|catalog_batch|recommendation
status: queued|running|completed|failed
current_step, processed_items, total_items
result_ref nullable, error_code nullable, error_message nullable
created_at, updated_at
```

数据库初始化/迁移只能由统一模块负责；业务服务不得临时建表。

## 15. HTTP API

统一错误：

```json
{"ok": false, "code": "invalid_input", "message": "English message", "retryable": false, "details": {}}
```

| Method | Path | 作用 |
|---|---|---|
| GET | `/api/health` | 服务、DB与配置状态 |
| GET | `/api/questionnaire` | 英文题目、选项、canonical genres |
| POST | `/api/profiles` | 创建纯问卷画像 |
| GET | `/api/profiles/{id}` | 获取最终画像和贡献拆分 |
| POST | `/api/profiles/{id}/preferences/parse` | Qwen解析自由文本 |
| PUT | `/api/profiles/{id}/preferences/confirm` | 确认硬条件并应用调整 |
| POST | `/api/profiles/{id}/steam-import/preview` | 同意后预览公开库存，不融合 |
| POST | `/api/profiles/{id}/steam-import/confirm` | 提交喜欢游戏/方面，启动导入任务 |
| GET | `/api/jobs/{job_id}` | 前端轮询任务 |
| POST | `/api/recommendations` | 启动召回+Qwen终排任务 |
| GET | `/api/recommendations/{run_id}` | 获取推荐结果 |
| GET | `/api/catalog/stats` | 目录状态统计 |
| GET | `/api/catalog/games/{appid}` | Demo/开发检查单款游戏 |

Preview不修改画像；Confirm才保存库存、标注缺失游戏并重建画像。召回数量和阈值由后端控制，前端不可提交任意值覆盖。

## 16. 前端范围

四步英文网页：

1. Questionnaire & Preferences
2. Steam Library Import
3. Profile Summary
4. Recommendations

必须：外部调用前显示校验错误；Steam明确同意；展示库存预览/时长；选择喜欢游戏和方面；约2秒轮询任务；展示画像各来源贡献；分开same/cross；区分formal/closest/no-match；展示Qwen名次、确定性兼容度、证据与caution；不暴露Key和堆栈。

不做：登录、管理后台、复杂图表、拖拽、WebSocket和完整移动端优化。

## 17. Job与错误行为

```text
queued -> running -> completed | failed
```

```json
{
  "job_id": "j_...",
  "job_type": "steam_import",
  "status": "running",
  "current_step": "annotating_inventory",
  "processed_items": 3,
  "total_items": 8,
  "result_ref": null,
  "error": null
}
```

| 故障 | 行为 |
|---|---|
| 非法问卷/确认 | HTTP 400且不调用外部接口 |
| 私密Steam库存 | 清晰warning，纯问卷画像仍可用 |
| 单款采集失败 | 标记该游戏failed，批次继续 |
| Qwen输出两次非法 | 对应任务失败，不模板伪装 |
| 无候选 | 正常`no_match`，不是HTTP 500 |
| SQLite写失败 | 当前操作失败并返回统一错误 |
| 价格未知且设置上限 | `price_unverifiable`剔除 |

V1不实现额度耗尽专用逻辑；供应商错误按普通上游错误处理。

## 18. 安全与隐私

- `.env`、`app.db`、Key和未脱敏测试账号数据不得进Git；
- 浏览器不得直接调用Steam/Qwen；
- 日志可记录AppID，但掩码SteamID且绝不记录密钥；
- 外部请求设置超时和响应大小限制；
- LLM文本按纯文本渲染，不作为可信HTML；
- 对ID、枚举、价格、列表长度做后端校验。

## 19. 课程六项映射

| 课程概念 | V1.3实现 |
|---|---|
| Custom Webhook | FastAPI POST端点 |
| Router | 画像/目录、双轨、formal/closest/no-match分支 |
| Data Store | SQLite |
| Error Handler | Pydantic、统一错误、有限重试、Job状态 |
| OpenRouter / Another Tool | Qwen API + LLM Adapter |
| Three Scenarios | 画像构建、目录标注、推荐终排 |

每项必须在真实工作流中执行并影响结果，不能只写在报告里。

## 20. 冻结工程参数

| 参数 | 值 |
|---|---:|
| formal threshold | `0.72` |
| closest floor | `0.55` |
| track overlap | `0.50` |
| recommendation coverage | `0.70` |
| matching distance | `<=1` |
| 每轨召回 | 最多5 |
| 每轨最终输出 | 最多3 |
| 官方标注输入 | 约8,000字符上限 |
| 评论补充输入 | 约6,000字符上限 |
| 输出修复 | 1次 |
| 重点基因 | 最多3个，weight=2；其他=1 |
| 熟悉genres | 1–3个，权重3/2/1 |

这些是课程Demo工程默认值，不宣称统计验证，不得为改善录制结果静默调参。

## 21. 可由实现阶段决定

- SQLAlchemy或SQLModel；
- CSS方案或轻量组件库；
- 封顶的playtime弱信号函数；
- 当时可用的Qwen模型ID；
- 英文问卷和Prompt的最终措辞；
- 目录批处理使用CLI还是仅本地受保护端点。

所有选择必须保持本文冻结契约。

## 22. 官方参考资料

- [Steam IPlayerService / GetOwnedGames](https://partner.steamgames.com/doc/webapi/iplayerservice?language=english)
- [Steam IUserReviewsService / GetAppReviews](https://partner.steamgames.com/doc/webapi/IUserReviewsService?l=english)
- [Steam IStoreService / GetAppList](https://partner.steamgames.com/doc/webapi/IStoreService)
- [Alibaba Model Studio OpenAI-compatible Chat API](https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-chat-completions)
- [Alibaba Model Studio structured output](https://help.aliyun.com/zh/model-studio/qwen-structured-output)
- [Alibaba Model Studio free-quota rules](https://help.aliyun.com/zh/model-studio/new-free-quota)

`appdetails`在本文中明确作为public Storefront endpoint使用，不把它表述为具有上述Steamworks文档同等级保证的正式接口。
