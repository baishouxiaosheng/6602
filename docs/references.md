# 参考项目与资料

调研时未找到同时具备“LLM 标注的设计画像 + 证据核验 + 同类/跨类双轨”的开源项目，以下是最接近的参考。

| 项目 | 可借鉴之处 |
|---|---|
| [johnamit/nextquest](https://github.com/johnamit/nextquest) | 排除已拥有游戏；“游戏库模式 / 目录模式”；分阶段流水线脚本 |
| [Netruk44/steam-embedding-search](https://github.com/Netruk44/steam-embedding-search) | 可续跑的采集器（1.5 秒节流）；区分“描述命中”与“评测命中” |
| [HaFares/Game-Recommendation-System-](https://github.com/HaFares/Game-Recommendation-System-) | 300 款规模下预计算相似度即可，不需要向量数据库 |
| [woctezuma/steam-descriptions](https://github.com/woctezuma/steam-descriptions) | 基于商店描述的 TF-IDF / 词向量基线，可作对照；同作者的 `steamreviews`、`steamspypi` 是现成采集库 |

- 维度依据：[Quantic Foundry Gamer Motivation Model](https://quanticfoundry.com/2015/07/20/how-we-developed-the-gamer-motivation-profile-v2/)；Hunicke, LeBlanc & Zubek (2004) *MDA: A Formal Approach to Game Design and Game Research*。
- Steam 采集经验：[Nik Davis, Steam data collection](https://nik-davis.github.io/posts/2019/steam-data-collection)；[Valve Developer Wiki: Steam Web API](https://developer.valvesoftware.com/wiki/Steam_Web_API)。
- 协作规范：AGENTS.md 约定（跨工具的 AI 助手说明文件）、契约先行开发、ADR、Conventional Commits。

注：调研环境无法直接打开 Steamworks 官方文档与 SteamSpy 站点，相关细节来自二手资料，开发 A 需按 `docs/05` 开头的说明实测确认。
