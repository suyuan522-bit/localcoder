# Phase 4 — 上下文、验证与追踪

**状态：** 已完成
**日期：** 2026-08-27
**目标提交：** `feat: add bounded context verification and trace`

## 阶段目标

在 Phase 3 自主代理循环之上加入有界上下文、真实验证状态和简洁终端追踪，使 LocalCoder 能长期保留任务约束、限制动态历史与工具输出，并在源码编辑后要求由后续成功命令提供验证证据。本阶段不实现 Git diff、Demo 集成或任何 Phase 5 功能。

## 文件变更

- `context.py`
- `trace.py`
- `trace_logger.py`
- `agent.py`
- `main.py`
- `config.py`
- `prompts.py`
- `tools/base.py`
- `tools/file_tools.py`
- `tools/shell_tool.py`
- `tests/test_context.py`
- `tests/test_agent.py`
- `tests/test_file_tools.py`
- `docs/phases/phase-4.md`

## 新增或变更接口

- `MAX_DYNAMIC_MESSAGES = 24` — 动态上下文消息的默认上限。
- `ContextManager(system_prompt, task, max_dynamic_messages=24, max_tool_output_chars=12000)` — 永久保留系统提示词和原始任务，并管理有界动态历史。
- `ContextManager.messages` — 返回与内部状态分离的 provider-ready 消息副本。
- `ContextManager.add(message)` — 添加单条动态消息。
- `ContextManager.add_group(messages)` — 将一次 assistant 响应及对应 tool observations 作为同组加入，裁剪时保持 native tool-call 配对。
- `truncate_text(text, max_chars, marker)` — 统一保留首尾内容并插入 `[output truncated]` 标记。
- `AgentState.verification_runs` — 记录每次 `run_command` 的命令、步骤、退出码、成功状态和简洁结果。
- `AgentState.last_edit_step` — 记录最近一次成功 `write_file` 或 `replace_text` 的模型步骤。
- `AgentCore(..., context_manager=None, trace_logger=None)` — 支持注入有界上下文与终端追踪器。
- `TraceLogger(stream=None, secrets=())` — 输出 `EXPLORE`、`EDIT`、`VERIFY`、`DONE` 事件，并省略命令原始输出及敏感编辑正文。

## 实现总结

`ContextManager` 将系统提示词和原始任务作为永久消息保存，动态消息默认最多保留 24 条，并要求自定义上限至少为 2，以容纳一组 assistant tool call 与对应 observation。AgentCore 按 assistant turn 分组加入上下文；裁剪会优先移除最旧完整组，避免拆开 native tool-call 配对。若单组超过上限，则保留 assistant 消息和最近 observations，同时同步过滤 tool call IDs。

工具 observation 在进入模型上下文前默认限制为 12,000 字符。普通长文本保留开头和结尾；JSON `ToolResult` observation 会优先缩短 `output` 或 `error` 字段并重新序列化，既保留首尾证据，也保持 JSON 可解析。文件和 shell 工具复用同一截断函数。

AgentCore 在每次成功编辑后更新 `last_edit_step`，并按真实工具调用顺序追踪编辑与验证先后关系。所有 `run_command` 结果都会写入 `verification_runs`。若最后一次验证失败、没有成功验证，或成功验证早于后续编辑，`finish` 会返回可恢复的 `verification_required` observation；只有显式填写真实 `limitations` 才能在验证确实不可用时结束。

`TraceLogger` 根据工具名推断阶段，输出步骤、工具、安全参数摘要、状态、结果和变更文件。编辑正文不进入追踪；命令只显示可执行程序，其结果只显示退出码、超时、输出长度和截断状态，不打印 stdout/stderr 或环境转储。CLI 还把当前 `LLM_API_KEY` 作为精确脱敏值交给追踪器。

确定性 FakeLLMClient 场景真实执行了 `write_file → py_compile 失败 → replace_text 修复 → py_compile 成功 → finish`，并验证最终文件、状态记录、五个阶段事件和秘密不出现在追踪输出中。

## 测试情况

执行命令：

```bash
python -m pytest tests/test_context.py tests/test_agent.py tests/test_shell_tool.py tests/test_file_tools.py -q
python -m pytest -q
python -m compileall -q agent.py context.py trace.py trace_logger.py main.py tools tests
```

测试结果：

```text
73 passed in 5.16s
104 passed in 5.14s
compileall exited with code 0
```

测试全部确定性运行，不访问真实或付费 LLM API。覆盖永久消息、有界动态历史、tool-call 配对、纯文本及 JSON observation 首尾截断、参数边界、编辑步骤、验证记录、过早 finish 拒绝、显式 limitation、同一步骤内验证与编辑顺序、失败后修复再验证、追踪阶段、环境转储省略、秘密脱敏、Windows 精确换行写入，以及 Phase 1–3 全部回归。

## 设计决策

- 上下文保留最近完整 assistant turn，而不是机械截取单条消息；动态上限至少为 2，防止生成孤立 tool observation。
- JSON 工具 observation 在字段级截断后重新序列化，避免简单字符串切片产生无效 JSON。
- 除规范要求的模型步骤外，AgentCore 内部维护工具调用顺序，正确处理同一响应中“先验证、后编辑”的情况。
- `finish` 只认可实际 `run_command` 状态，不把模型提供的验证文字当作执行证据；后续失败验证也不会被更早的成功结果掩盖。
- Trace 不打印编辑正文、完整命令参数或命令原始输出，只展示理解执行流所需的结构化元数据。
- 文件写入使用 UTF-8 字节原样落盘，防止 Windows 文本模式把 LF 改写为 CRLF 后破坏 `replace_text` 精确匹配。

## 与原计划的偏差

- 新增 `trace_logger.py` 作为实际运行时模块，`trace.py` 保留规范要求的公共导出。原因是 Python 标准库同样存在 `trace` 模块，pytest 插件可能预先加载它；无冲突模块名可保证测试和 CLI 稳定导入。
- `tests/test_shell_tool.py` 无需新增测试；其既有输出截断测试已覆盖共享截断行为。Windows 换行回归测试放在更直接的 `tests/test_file_tools.py`。

## 已知限制

- 有界上下文只保留最近消息组，不实现摘要、embeddings、向量数据库或语义长期记忆。
- 终端脱敏和敏感正文省略属于防泄漏控制，不是对任意编码或拆分秘密的形式化保证。
- 验证记录表明命令真实运行及退出状态，不能证明程序形式化正确，也不能保证所选命令覆盖所有行为。
- 显式 `limitations` 允许在验证确实不可用时结束，其真实性仍依赖模型遵守系统提示词和用户审查。
- 本阶段没有 Git diff 能力，也没有 Demo 项目集成；这些严格留给 Phase 5。

## 下一阶段

Phase 5 将在收到明确指令后实现工作区范围 Git diff、变更可见性和受控 Todo Demo 端到端集成；本阶段未提前实现任何 Phase 5 功能。
