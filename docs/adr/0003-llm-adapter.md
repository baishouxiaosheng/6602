# ADR 0003 · 模型适配层：OpenAI 兼容接口 + 自行校验重试

- 状态：已采纳
- 决定：统一接口 `LLMClient.complete_json(system, user, schema)`；实现为 `openai` SDK + 各家 `base_url` 预设，默认 OpenRouter。
  JSON 模式 + 提示词内嵌 JSON Schema；回答经“去围栏 → 解析 → Pydantic 校验”；失败把错误原文回传重试，上限 `LLM_MAX_RETRIES`。
  传输层错误（超时、5xx、429）另由 `retry_call` 退避重试。
- 理由：课程提供 OpenRouter Key 且限定开源模型；严格 `json_schema` 模式各家支持不一，自行校验最稳；依赖最少。
- 备选：LiteLLM（依赖重、版本变动快）；instructor（需按提供商选模式）。
- 影响：新增提供商 = `llm/factory.py` 加一行；`FakeLLM` 让全部测试离线运行。
