# Phase 3 — AgentCore 与自主代理循环

**状态：** 已完成
**日期：** 2026-08-27
**目标提交：** `feat: implement autonomous agent loop`

## 阶段目标

在 Phase 1 本地工具与 Phase 2 OpenAI-compatible `LLMClient` 之上，实现单任务、自主、多步骤的 `AgentCore`。模型通过 native tool calling 请求工具，工具结果作为真实 observation 返回模型，任务只能通过显式 `finish` 协议正常结束，并由 `MAX_STEPS` 和受控错误路径保证异常终止。

## 文件变更

- `agent.py`
- `prompts.py`
- `main.py`
- `config.py`
- `tools/registry.py`
- `tests/test_agent.py`
- `docs/phases/phase-3.md`

## 新增或变更接口

- `MAX_STEPS = 30` — AgentCore 的默认最大模型调用步数。
- `AgentState(task, ...)` — 保存任务、步骤数、修改文件、验证记录、最近错误、最近编辑步骤和完成状态，以及显式 finish 的最终信息。
- `AgentRunResult(success, message)` — 表示一次 AgentCore 运行的受控成功或失败结果。
- `AgentCore(llm_client, registry, task, max_steps=MAX_STEPS)` — 初始化任务状态、基础消息和显式 finish 工具。
- `AgentCore.run()` — 执行模型调用、工具分发、observation 回传和终止判断的多步骤循环。
- `finish(summary, verification, limitations=None)` — 由 AgentCore 注册的唯一正常终止协议。
- `register_local_tools(registry, workspace, modified_files)` — 将六个 Phase 1 本地工具及 native schemas 注册到一个任务的 ToolRegistry，并共享修改文件集合。
- `SYSTEM_PROMPT` — 编码检查真实状态、使用工具、定向编辑、合理验证、错误恢复、工作区边界、证据约束和显式 finish 的简洁系统提示词。
- `main(argv=None)` — 支持 `python main.py --workspace <path> --task "<task>"` 的 argparse CLI 入口。

## 实现总结

`AgentCore` 维护普通消息列表，并在每一步把当前消息与 `ToolRegistry.definitions()` 交给 `LLMClient.complete()`。返回的 `ToolCall` 不在 AgentCore 中解析 provider-specific 对象，而是按归一化 ID、名称和 arguments 通过 `ToolRegistry.dispatch()` 执行。

每个 `ToolResult` 都会被序列化为包含 `success`、`output`、`error` 和 `metadata` 的 `role="tool"` observation，并使用原始 `tool_call_id` 与 assistant tool call 配对。一个响应中的多个普通工具调用按顺序全部执行并全部回传；未知工具、malformed arguments 和工具失败不会直接终止循环，而是作为可恢复 observation 反馈给模型。

纯 assistant 文本不会被视为完成。只有独立响应中的成功 `finish` tool call 才会设置 `state.finished` 并返回最终摘要、修改文件、验证说明及可选限制。若 `finish` 与其他工具混在同一响应中，finish 会收到可恢复失败，其他调用仍全部执行，防止提前终止造成 tool call 与 observation 不配对。

达到 `MAX_STEPS`、`LLMClientError` 或 `KeyboardInterrupt` 时，AgentCore 返回受控失败并更新 `last_error`。CLI 负责安全加载配置、验证工作区、组合真实本地工具与 AgentCore，并用退出码区分成功、代理失败和启动配置错误。

## 测试情况

执行命令：

```bash
python -m pytest tests/test_agent.py -q
python -m pytest tests/test_agent.py tests/test_registry.py tests/test_llm_client.py -q
python main.py --help
python -m pytest -q
```

测试结果：

```text
15 passed in 1.40s
41 passed in 1.82s
CLI help exited with code 0
89 passed in 4.29s
```

测试使用确定性 `FakeLLMClient`，不发起真实或付费 API 请求。覆盖 `AgentState` 默认状态、`read_file → finish`、多步骤与多 tool-call、工具失败反馈及恢复、malformed arguments、混合 finish 批次、纯文本不得完成、`MAX_STEPS`、不可恢复 LLM 错误、用户中断、默认工具注册、真实工作区写入与修改文件共享、CLI 成功组合和配置错误。

## 设计决策

- AgentCore 只依赖 Phase 2 的归一化 `LLMResponse`，不导入或解析 OpenAI SDK response 对象，保持 provider-specific 代码集中在 `LLMClient`。
- 所有模型请求工具均通过 `ToolRegistry` 分发，不在 AgentCore 中建立按工具名分支的长 `if/elif` 链。
- observation 使用完整 `ToolResult` 结构，而不是只返回文本，使模型可区分成功、错误和工具元数据，并据此恢复。
- `finish` 由 AgentCore 注册为保留协议，普通 assistant 文本不能绕过它；混合调用批次中的 finish 被拒绝，以保证每个 native tool call 都有对应 observation。
- CLI 复用真实 `Workspace` 和 Phase 1 工具，写入与替换 handler 共享 `AgentState.modified_files`，无需建立额外状态容器。
- 错误处理返回小型 `AgentRunResult`，不引入状态机、agent framework 或 Phase 4 的 Trace/Context 抽象。

## 与原计划的偏差

- `tools/base.py` 未修改，因为现有 `ToolResult` 已完整满足 AgentCore observation 契约，无需机械改动或新增字段。
- 未执行 live LLM 运行；所有 AgentCore 和 CLI 测试使用 fake client，以保证默认 `pytest` 不依赖密钥、网络或付费调用。

## 已知限制

- 当前消息历史尚未限制动态消息数量，tool observation 也没有 Phase 4 的上下文级截断；本阶段仅复用各本地工具已有的输出上限。
- `verification_runs` 和 `last_edit_step` 字段已按 AgentState 契约存在，但其记录逻辑属于 Phase 4，本阶段未提前实现。
- `finish` 目前要求显式验证说明，但尚未检查“最后一次成功验证是否晚于最后一次源码修改”；verification-aware finish 属于 Phase 4。
- Trace、阶段推断和终端事件输出尚未实现。
- malformed arguments 的失败 observation 保留稳定错误，但 Phase 2 归一化接口未保留 provider 的原始 arguments 字符串，assistant history 会以空 object 重建该调用。
- 未执行真实 OpenAI-compatible provider 兼容性测试，实际运行仍依赖用户本地配置的 provider 与模型支持 native tool calling。

## 下一阶段

Phase 4 将在收到明确指令后实现 `ContextManager`、有界动态历史、上下文级工具输出截断、验证记录、verification-aware finish 和 `TraceLogger`；Phase 4 尚未开始。
