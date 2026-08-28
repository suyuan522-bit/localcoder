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

## 真实模型端到端运行

本机在 Process、User 和 Machine 三个作用域均未发现 LLM_API_KEY、LLM_BASE_URL 或 LLM_MODEL，工作区也不存在 .env，因此未发起真实模型或付费 API 请求，也没有伪造实时运行结果。真实模型的工具选择顺序、重试次数和首次实现正确率仍属于模型依赖行为；配置凭据后可针对同一 Todo delete 任务执行真实运行。

## 设计决策

- get_diff 使用工作区相对 pathspec，而不是直接显示整个仓库差异，保持工具权限边界和任务范围一致。
- tracked changes 以 HEAD 为统一基线，使暂存与未暂存修改同时可见；无 HEAD 仓库采用两段 diff 保持可用。
- 未跟踪文件只显示工作区内的相对路径，不读取或回显其正文，减少无关内容和潜在敏感数据进入模型上下文。
- Git 输出在子进程读取期间即受内存上限约束，不依赖先完整捕获再截断。
- get_diff 的 Trace 不包含正文；模型仍通过 tool observation 获取有界差异，终端只显示结构化元数据。
- Todo fixture 保持在 delete 尚未实现的可演示基线；确定性测试中的编辑来自 FakeLLMClient 响应，AgentCore 和工具层没有任务专用逻辑。

## 与原计划的偏差

- 计划允许修改 agent.py 与 trace.py，但现有 AgentCore 的最终变更汇总和 trace.py 公共导出已经满足需求，因此未作无意义修改；实际集成点位于 tools/registry.py 和 trace_logger.py。
- 计划要求在本地凭据可用时运行真实模型；当前三个环境变量均未配置，因此按安全要求跳过实时调用，只保留确定性端到端证据。

## 已知限制

- 实时模型运行尚未在本机验证；不同 OpenAI-compatible provider 的工具调用质量和稳定性可能不同。
- 非 Git 回退只能显示 AgentState 已知的修改文件，无法重建真实补丁。
- get_diff 不显示未跟踪文件正文，只列出相对路径；文件经工具编辑后仍会出现在最终 changed-files 汇总中。
- 12,000 字符上限保留 diff 首尾，超长中间区段会被省略，必要时仍需使用文件读取工具做定点检查。
- Todo 示例仅用于受控端到端验证，不包含并发写入、数据库事务或生产级数据迁移。

## 下一阶段

Phase 6 仅在收到明确指令后进行文档、演示打磨和发布准备；本阶段未启动 Phase 6。
