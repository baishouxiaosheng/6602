# 种子池（开发 A 维护）

`appids.csv` 目前只有 16 款起步样例，目标约 300 款。列：

| 列 | 含义 |
|---|---|
| `appid` | Steam AppID（唯一） |
| `name` | 便于人读，流水线以 Steam 返回的名称为准 |
| `bucket` | 人工指定的表层类型桶，用于检查覆盖是否均衡 |
| `doc_level` | 资料丰富程度的预估：`rich` / `medium` / `thin`，用于证据质量校准 |

## 选取规则

1. 只收 `type == game` 的正式发售作品；不收 DLC、原声带、Demo、未发售、仅成人内容作品。
2. 评测数 ≥ 500（证据来源充足）；`thin` 档可放宽到 ≥ 100，用来测试“证据不足则未知”的行为。
3. 约 20 个 `bucket`，每桶 10–20 款，单桶不超过总量的 8%，避免某一类型淹没其他轨。
4. 每桶内同时包含“典型作”和“跨类型作”（例如带建造的生存、带剧情的肉鸽），其他轨才有东西可找。
5. `doc_level` 比例约 rich 60% / medium 30% / thin 10%。
6. AppID 必须用 `https://store.steampowered.com/app/<appid>/` 实际打开核对，不要凭记忆或让模型生成。

候选来源：SteamSpy `top100in2weeks` / `top100forever` / `tag=<tag>` 列表，再人工筛选。
