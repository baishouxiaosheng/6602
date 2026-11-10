# 协作规范

## 分支与提交

- `main` 始终可运行、测试全绿。不直接向 `main` 推送。
- 分支名：`feat/a2-store-client`、`feat/b5-pipeline`、`fix/…`、`docs/…`（带任务编号）。
- 一个任务编号一个 PR，尽量小于 400 行改动；先合并被依赖的任务（A1→A2…，B3→B5…）。
- 提交信息用英文 Conventional Commits：`feat(steam): add throttled http client (A1)`。

## PR 要求

1. `uv run pytest -q` 与 `uv run ruff check .` 通过（CI 会再跑一遍）。
2. 对应任务的验收测试不再 skipped。
3. 不改 FROZEN 文件与 `tests/`（见 `AGENTS.md`）。确需修改：先提 issue，由设计负责人改并补 ADR。
4. 另一位成员 review 后合并（Squash merge）。

## 使用 AI 编码助手

- 允许并鼓励使用，但**提交者必须能逐行解释自己提交的代码**（课程要求能演示和讲解）。
- 让助手先读 `AGENTS.md` 和你的 `docs/handoff/DEV_*.md`；一次只做一个任务编号。
- 助手生成的内容中若出现“看起来合理但没有来源”的 Steam 字段、接口地址或游戏事实，必须用真实请求核实。
- 不把 API Key、同学的 Steam ID 等信息粘贴给任何在线工具。

## 密钥与课程资源

- OpenRouter Key 为小组共用、额度 20 美元一次性发放，只能用课程批准的开源模型。
- 密钥只放在本地 `.env`。截图、日志、issue、提交历史中都不得出现。
- 批量标注前先用 `--limit 5` 试跑并查看费用，再跑全量（见 `docs/05-catalog-pipeline-spec.md` §7）。

## 没有 GitHub 权限时的交回方式

在仓库根目录执行（只打包你改过的源码与数据，不含 `.env`、`.venv`）：

```bash
git archive --format=zip -o ../gamegene-return.zip HEAD
```

没有使用 git 时，直接压缩整个项目文件夹，但先删除 `.venv/`、`.env`、`data/raw/`。
