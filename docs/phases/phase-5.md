# Phase 5 — Git Diff 与端到端集成

**状态：** 已完成
**日期：** 2026-08-28
**目标提交：** feat: add git diff and end-to-end demo

## 阶段目标

在 Phase 4 的代理循环、验证状态与追踪能力之上加入工作区范围的 Git 变更可见性，并用受控 Todo CLI 项目证明完整流程能够探索代码、先写失败测试、实现修复、重新验证、查看差异并结束。本阶段不新增 Phase 6 文档发布功能，也不引入新的工具或代理功能类别。

## 文件变更

- tools/git_tool.py
- tools/registry.py
- trace_logger.py
- tests/test_git_tool.py
- tests/test_agent.py
- examples/todo_demo/todo.py
- examples/todo_demo/tests/test_todo.py
- docs/phases/phase-5.md

## 新增或变更接口

- get_diff(workspace, modified_files=None) — 返回限定在当前 Workspace 内的 Git 差异；覆盖暂存、未暂存和未跟踪文件，并在 Git 不可用或目录不是仓库时回退到已知变更文件。
- ToolRegistry 的默认本地工具集合新增原生无参数工具 get_diff，其 handler 复用代理维护的 modified_files 集合。
- TraceLogger 将 get_diff 显示为 VERIFY，仅记录输出长度与截断状态，不打印 diff 正文。
- 最终 AgentRunResult.message 继续由 AgentState.modified_files 生成明确的 Changed files 汇总。

## 实现总结

get_diff 首先用命令级 safe.directory 探测实际仓库根目录，然后计算仓库根到工作区的相对 pathspec。所有 Git diff 与未跟踪文件查询都带该 pathspec，因此父仓库中工作区外的文件不会进入结果。对有 HEAD 的仓库使用 git diff HEAD 合并暂存与未暂存的 tracked changes；对尚无提交的仓库则分别收集 index 与 worktree 差异。工作区内未跟踪文件通过 git ls-files --others --exclude-standard 单独列出。

Git 子进程输出采用流式读取，只保留有界前缀和后缀，默认最终结果最多为 MAX_TOOL_OUTPUT_CHARS。若工作区不在 Git 仓库中或 Git 可执行文件不可用，工具仍返回成功结果，并列出代理已知的 modified_files；Git 命令自身失败则返回结构化失败结果。

Todo 示例是独立、文件持久化的 Python CLI，基线只实现计划要求的 add、list 和 complete，并包含函数层与 CLI 层测试。delete 被有意保留为推荐端到端任务，未硬编码进代理运行时。

确定性 FakeLLMClient 端到端测试会复制真实 examples/todo_demo 基线到临时 Git 工作区，随后执行如下工具序列：

~~~text
list_files + read_file
→ write_file（加入 delete 测试）
→ run_command（验证失败）
→ write_file（实现 delete）
→ run_command（验证成功）
→ get_diff
→ finish
~~~

实际观察到验证记录为 False → True，get_diff 同时包含 todo.py 与 tests/test_todo.py，最终结果显示两项 changed files，Trace 依次出现 EXPLORE、EDIT、VERIFY 和 DONE 视图。

## 测试情况

执行命令：

~~~bash
python -m pytest -q tests/test_git_tool.py tests/test_agent.py
python -m pytest -q
cd examples/todo_demo && python -m pytest -q
python -m compileall -q agent.py context.py trace.py trace_logger.py main.py tools tests examples/todo_demo
~~~

测试结果：

~~~text
30 passed in 7.25s
118 passed in 10.10s
5 passed in 0.05s
compileall exited with code 0
~~~

默认测试全部确定性运行，不访问真实或付费 LLM API。覆盖工作区 pathspec、工作区外文件排除、暂存差异、未跟踪文件、长 diff 截断、非 Git 回退、工具注册、Trace 正文省略、最终 changed-files 汇总，以及真实 Todo 基线上的“编辑测试 → 失败验证 → 编辑实现 → 成功验证 → diff → finish”完整循环。

## 原始 Phase 5 的真实模型状态

原始 Phase 5 执行期间，本机在 Process、User 和 Machine 三个作用域均未发现 LLM_API_KEY、LLM_BASE_URL 或 LLM_MODEL，工作区也不存在 .env，因此当时未发起真实模型或付费 API 请求，也没有伪造实时运行结果。以下真实模型验证是在 Phase 5 完成并推送后单独执行的后续门禁，不属于原始 Phase 5 执行过程。

## Phase 5 后真实模型门禁

### 验证环境

- Provider：Alibaba Cloud Bailian / DashScope OpenAI-compatible API。
- Model：qwen3-coder-flash。
- API 凭据仅通过环境变量临时提供，验证完成后已从 shell session 中移除；仓库和本文档均未记录 API key。

### 验证 1：只读冒烟测试

真实模型收到“检查 Todo demo 且不要修改文件”的任务后，自主调用了以下工具：

~~~text
list_files
→ read_file(todo.py)
→ read_file(tests/test_todo.py)
→ finish
~~~

最终 changed files 为空，finish 成功。该测试确认了真实 OpenAI-compatible API 连通性、native tool calling、ToolResult observation 回传和显式 finish 行为。

### 验证 2：真实 Coding Agent 端到端测试

任务：

> Implement a delete command that deletes a todo by ID. Add relevant tests and ensure the full test suite passes. Inspect the final changes before finishing.

观察到的自主执行轨迹：

- 探索工作区并读取实现与测试。
- 编辑 todo.py 和 tests/test_todo.py。
- 第一次验证失败。
- 模型检查失败信息、修改测试并再次验证成功。
- 继续执行额外验证命令。
- 成功调用 get_diff 检查最终差异。
- 成功调用 finish。
- 共执行 20 个 agent steps。
- 最终 verification status 为 SUCCESS。
- 未触发 MAX_STEPS 终止，也未发生 workspace escape。

### 独立复核

代理结束后独立执行：

~~~bash
python -m pytest -q
~~~

结果：

~~~text
7 passed in 0.08s
~~~

独立 diff 检查确认验证工作区仅修改两个文件：

- tests/test_todo.py：33 insertions。
- todo.py：29 changed lines，其中 24 insertions、5 deletions。

实现新增 delete_todo()、delete CLI subcommand 和显式 command branching。新增测试覆盖删除现有 ID、保留其他 todos、ID 不存在行为、CLI 成功路径和 CLI 失败路径。人工复核未发现功能问题。

### 门禁结论

Real Model Gate：PASSED。

与确定性 FakeLLMClient 端到端测试不同，本次后续门禁证明了真实 LLM 能够自主使用 LocalCoder 的 native tools，响应首次验证失败并修复工作，检查最终 diff，并通过 finish 正常终止。

## 设计决策

- get_diff 使用工作区相对 pathspec，而不是直接显示整个仓库差异，保持工具权限边界和任务范围一致。
- tracked changes 以 HEAD 为统一基线，使暂存与未暂存修改同时可见；无 HEAD 仓库采用两段 diff 保持可用。
- 未跟踪文件只显示工作区内的相对路径，不读取或回显其正文，减少无关内容和潜在敏感数据进入模型上下文。
- Git 输出在子进程读取期间即受内存上限约束，不依赖先完整捕获再截断。
- get_diff 的 Trace 不包含正文；模型仍通过 tool observation 获取有界差异，终端只显示结构化元数据。
- Todo fixture 保持在 delete 尚未实现的可演示基线；确定性测试中的编辑来自 FakeLLMClient 响应，AgentCore 和工具层没有任务专用逻辑。

## 与原计划的偏差

- 计划允许修改 agent.py 与 trace.py，但现有 AgentCore 的最终变更汇总和 trace.py 公共导出已经满足需求，因此未作无意义修改；实际集成点位于 tools/registry.py 和 trace_logger.py。
- 计划要求在本地凭据可用时运行真实模型；原始 Phase 5 执行时三个环境变量均未配置，因此当时按安全要求跳过实时调用。真实模型验证随后作为独立的 post-Phase-5 gate 完成，并在本文档中与原始执行记录明确分开。

## 已知限制

- 真实模型门禁仅覆盖 Alibaba Cloud Bailian / DashScope OpenAI-compatible API 与 qwen3-coder-flash；其他 provider、模型和配置的工具调用质量与稳定性仍可能不同。
- 非 Git 回退只能显示 AgentState 已知的修改文件，无法重建真实补丁。
- get_diff 不显示未跟踪文件正文，只列出相对路径；文件经工具编辑后仍会出现在最终 changed-files 汇总中。
- 12,000 字符上限保留 diff 首尾，超长中间区段会被省略，必要时仍需使用文件读取工具做定点检查。
- Todo 示例仅用于受控端到端验证，不包含并发写入、数据库事务或生产级数据迁移。

## 下一阶段

Phase 6 仅在收到明确指令后进行文档、演示打磨和发布准备；本阶段未启动 Phase 6。
