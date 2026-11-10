# ADR 0005 · 界面只依赖 GameGeneService，演示服务先行

- 状态：已采纳
- 决定：UI 与 HTTP API 只调用 `contracts.GameGeneService`。框架自带 `DemoService`（简化实现 + 合成样例目录），
  产品实现为开发 B 的 `RealService`，由 `GAMEGENE_SERVICE` 切换。
- 理由：前端、数据侧、推荐侧三条线并行，互不阻塞；验收测试同时覆盖两种实现的同一组接口。
- 影响：`DemoService` 与合成目录绝不能用于最终演示（界面顶部有常驻提示）。
