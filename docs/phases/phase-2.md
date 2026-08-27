# Phase 2 — LLM 客户端与原生工具调用

**状态：** 已完成
**日期：** 2026-08-27
**目标提交：** `feat: add OpenAI-compatible LLM client`

## 阶段目标

实现 OpenAI-compatible `LLMClient`，从环境变量安全加载模型配置，将对话消息和 Phase 1 的工具 schema 发送给模型，并把 native tool-calling 响应归一化为后续 `AgentCore` 可直接消费的稳定数据结构。本阶段不实现 AgentCore 或任何 Phase 3+ 功能。

## 文件变更

- `llm_client.py`
- `config.py`
- `tests/test_llm_client.py`
- `.env.example`
- `requirements.txt`
- `docs/phases/phase-2.md`

## 新增或变更接口

- `ConfigurationError` — 表示缺失必需运行时配置的受控错误。
- `LLMConfig(api_key, base_url, model)` — 保存 OpenAI-compatible provider 配置，并从对象表示中隐藏 `api_key`。
- `load_llm_config(environ=None)` — 从环境或显式环境映射读取 `LLM_API_KEY`、`LLM_BASE_URL` 和 `LLM_MODEL`，缺失或空白时立即失败。
- `ToolCall(id, name, arguments, argument_error)` — 保存 provider-independent tool call；保留调用 ID、函数名、解析参数及受控参数错误。
- `LLMResponse(text, tool_calls)` — 统一表示 assistant 文本和零个或多个 tool calls。
- `LLMClient(config, ..., max_retries=2, retry_base_delay_seconds=0.25)` — 创建或接收 OpenAI-compatible client，并配置由本项目负责的有界重试。
- `LLMClient.complete(messages, tools=None)` — 发送 Chat Completions 请求和 native tool schemas，返回归一化 `LLMResponse`。

## 实现总结

`load_llm_config` 只读取三个冻结规范要求的环境变量，不读取或输出完整环境；错误仅列出缺失变量名。`LLMConfig` 将 `api_key` 排除在 `repr` 之外，`.env.example` 仅提供占位符，已有 `.gitignore` 继续忽略 `.env`。

`LLMClient` 使用 OpenAI SDK 的 Chat Completions native tool-calling 接口，将模型、消息和工具 schema 原样交给兼容 provider。响应被归一化为 `LLMResponse` 和 `ToolCall`，支持同一响应中的多个 tool calls，并保留每个 call ID 和名称。JSON object arguments 被解析为字典；无效 JSON 或非 object JSON 不会抛出解析异常，而会设置 `arguments=None` 和稳定的 `argument_error`，便于后续 AgentCore 将其作为可恢复失败处理。

客户端关闭 SDK 内置重试，由本项目对连接错误、超时、限流和服务端错误执行最多两次额外重试，并使用有界指数退避。重试耗尽和非瞬态 provider 异常都会转换为不包含原始异常消息的 `LLMClientError`，代码不记录凭据、Authorization header 或 provider 错误正文。

## 测试情况

执行命令：

```bash
python -m pytest tests/test_llm_client.py -q
python -m pytest -q
```

测试结果：

```text
19 passed in 1.61s
74 passed in 4.32s
```

测试全部使用 fake client，不访问真实或付费 LLM API。覆盖环境配置读取与缺失检查、秘密不出现在配置表示和可见错误/日志中、默认 SDK client 参数、assistant 文本、单个及多个 native tool calls、调用 ID 保留、有效及异常 arguments 归一化、瞬态恢复、重试耗尽、非瞬态失败和重试参数边界。

## 设计决策

- 使用 Chat Completions native tool-calling 接口，因为其消息和函数 schema 形状与 Phase 1 的 `ToolRegistry.definitions()` 直接兼容，同时适用于 OpenAI-compatible provider。
- 将 provider response 解析集中在 `LLMClient`，使后续 AgentCore 不需要依赖 OpenAI SDK 对象结构。
- malformed arguments 使用显式数据状态而不是空字典，避免把解析失败误当成合法的无参数工具调用。
- 关闭 SDK 内置重试并由本项目统一控制额外尝试次数，避免两层重试叠加导致实际请求次数不可预测。
- 对外错误只包含错误类别和尝试次数，不拼接 provider 异常正文，降低凭据或请求细节被意外带入异常与日志的风险。
- 依赖保持为 `openai` 和 `pytest`，未引入 agent framework、配置框架或不必要的抽象层。

## 与原计划的偏差

- `.gitignore` 未产生内容变更，因为 Bootstrap 已包含 `.env`、虚拟环境、Python cache 和 pytest cache 的忽略规则，已满足 Phase 2 的秘密安全要求。
- 未添加可选 live API smoke test；默认确定性测试已覆盖 provider 边界，避免产生付费请求或要求本地真实密钥。

## 已知限制

- 不同 OpenAI-compatible provider 对 Chat Completions tool calling 的细节支持可能存在差异；本阶段只验证 SDK 边界和规范响应形状，未执行 live provider 兼容性测试。
- 重试仅覆盖明确识别的连接、超时、限流和服务端异常，默认无 jitter；其他错误会立即以受控异常终止。
- malformed tool arguments 已归一化，但把该失败返回模型并继续执行属于 Phase 3 的 AgentCore 职责，本阶段未提前实现。

## 下一阶段

Phase 3 将在收到明确指令后实现 `AgentState`、`AgentCore`、显式 `finish`、系统提示词和 CLI；Phase 3 尚未开始。
