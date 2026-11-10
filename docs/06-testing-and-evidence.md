# 06 · 测试与证据

## 1. 三层测试

| 层 | 位置 | 说明 |
|---|---|---|
| 框架测试 | `tests/framework/` | 契约、存储、适配层、评分核心、演示服务与 API。**必须始终通过** |
| 验收测试 | `tests/dev_a/`, `tests/dev_b/` | 两位开发的完成定义。桩函数未实现时显示为 skipped，实现后自动生效 |
| 实网测试 | 自行添加，标 `@pytest.mark.live` | 真实 Steam / 模型调用，只在本地手动跑：`uv run pytest -m live` |

全部离线、无需密钥、数秒跑完。HTTP 用 `httpx.MockTransport`，模型用 `FakeLLM`，Steam 库用 `FakeSteamLibraryClient`。

## 2. 课程五项测试的对应

| # | 课程要求 | 做法 | 预期可观察结果 | 自动化测试 |
|---|---|---|---|---|
| 1 | 正常输入 | 完整访谈 → 生成画像 → `mode=both` 推荐 | 两条轨道均有结果；`runs/<id>.json` 落盘；每条推荐带共同基因与证据句 | `test_b6_1_normal_input` |
| 2 | 非法输入 | 漏答 / 空昵称 / `top_k=99` | HTTP 400 `invalid_input`，`problems` 列出全部问题；**模型与 Steam 调用次数为 0**；无新文件 | `test_b6_2_invalid_input`, `test_b2_invalid_input_stops_before_steam` |
| 3 | 不匹配任何路径 | ① `mode=surprise_me` ② 过滤条件排除全部候选 | `status=no_match`，`trace` 中 `branch=no_matching_path` 或 `filter_drops` 说明；没有编造的推荐 | `test_b6_3_no_matching_path`, `test_b5_branch_c/d/g` |
| 4 | 强制错误 | ① 模型强制失败 ② Steam 强制失败 ③ 目录文件损坏 ④ 流水线中模型失败 | ① 模板回退，`llm.fallbacks>0` ② 画像仍保存并给出 warning ③ `status=error` 运行落盘，已有数据完好 ④ 记录 `FAILED`，旧 `VERIFIED` 不被覆盖 | `test_b6_4_forced_error`, `test_b5_branch_h`, `test_a7_*` |
| 5 | 后续读取已保存数据 | 重启服务后 `GET /api/runs/<id>`、读取画像、历史页 | 返回与当时完全一致的运行（含证据句） | `test_b6_5_later_read` |

六个替代部件各自由哪项测试“实际生效”：

| 部件 | 被哪些测试触发 |
|---|---|
| Webhook（API / UI 处理器） | 1–5 全部经由 `POST /api/...` |
| Router | 3（未知模式、过滤清空）、1（双轨分流）、4（错误分支） |
| Data Store | 1（写）、5（读）、4（失败不破坏旧版本） |
| Error handler | 2（校验错误）、4（重试、回退、FAILED 记录） |
| OpenRouter / 模型 | 1（`generated_by="llm"` 的解释被保存）、目录标注改变 `genes` |
| 三个工作流 | 1：画像（WF1）+ 目录（WF2 产物）+ 推荐（WF3）串联 |

## 3. 演示用证据包（任务 B7）

`scripts/collect_evidence.py`（开发 B 编写）对运行中的服务依次执行五项测试，为每项在 `evidence/<UTC 时间>/` 下保存：

```
0N-<名称>/request.json      发出的请求
0N-<名称>/response.json     HTTP 状态码 + 响应体
0N-<名称>/trace.json        运行的 trace（选中的分支与中间数据）
0N-<名称>/stored/           相关的落盘文件副本（profiles/…、runs/…）
summary.md                  每项一行：输入 → 分支 → 结果 → 是否符合预期
```

强制错误的触发方式（不改代码）：

| 故障 | 方法 |
|---|---|
| 模型失败 | 启动时设 `LLM_PROVIDER=custom LLM_BASE_URL=http://127.0.0.1:9 LLM_API_KEY=x LLM_MODEL=x`（连接被拒 → `UpstreamError` → 重试 → 模板回退） |
| Steam 失败 | 画像请求里填一个不公开的资料链接，或设错误的 `STEAM_API_KEY` |
| 目录损坏 | 复制一份数据目录，把其中一个 `catalog/<appid>.json` 改成非法 JSON，用 `GAMEGENE_DATA_DIR` 指向副本 |

证据中不得出现密钥；Steam ID 用测试账号或打码。

## 4. 阶段一：十个人工案例（可行性判断）

用真实目录跑通 30 款后，三人各准备 3–4 个真实玩家画像（自己或朋友），记录到 `docs/feasibility.md`：
画像 → 两条轨道的结果 → 该玩家对每条推荐的判断（想玩 / 已经喜欢同类 / 不感兴趣）→ 解释是否可信。
判定标准：其他轨推荐中“想玩”的比例 ≥ 1/3 且没有与证据矛盾的解释 → 继续；否则调整阈值或题目（设计负责人负责）。

## 5. 手工冒烟（每次合并前 2 分钟）

`uv run gamegene serve` → 画像页不填直接提交（应出现红色错误面板）→ 完整填写并生成画像 →
推荐页获取推荐（两条轨道）→ 模式手动输入 `xyz`（应为“无匹配”）→ 历史页刷新并打开刚才的运行。
