# Phase 1 — 本地工具基础

**状态：** 已完成
**日期：** 2026-08-27
**目标提交：** `feat: implement local tool foundation`

## 阶段目标

在不依赖 LLM API 的前提下，建立 LocalCoder 可确定性测试的本地执行基础，包括统一工具结果、工作区边界、工具注册与分发、文本文件操作和受控命令执行。

## 文件变更

- `config.py`
- `tools/__init__.py`
- `tools/base.py`
- `tools/registry.py`
- `tools/workspace.py`
- `tools/file_tools.py`
- `tools/shell_tool.py`
- `tests/test_workspace.py`
- `tests/test_file_tools.py`
- `tests/test_shell_tool.py`
- `tests/test_registry.py`
- `docs/phases/phase-1.md`

## 新增或变更接口

- `ToolResult(success, output, error, metadata)` — 为所有本地工具提供统一的成功或失败结果。
- `Workspace(root)` — 保存并规范化工作区根目录。
- `Workspace.resolve(requested_path)` — 解析路径并拒绝逃逸工作区的相对路径、绝对路径及链接目标。
- `Workspace.relative(path)` — 返回经边界校验的 POSIX 风格工作区相对路径。
- `ToolRegistry.register(name, description, parameters, handler)` — 注册工具处理器及 native tool-calling schema。
- `ToolRegistry.definitions()` — 返回可供后续模型客户端使用的函数工具定义。
- `ToolRegistry.dispatch(name, arguments)` — 校验工具名和参数，并将异常转换为 `ToolResult`。
- `list_files(workspace, path=".", max_depth=2)` — 输出有深度、条目数及字符数上限的目录结构。
- `read_file(workspace, path, start_line=1, end_line=None)` — 读取最多 200 行带行号的 UTF-8 文本。
- `search_text(workspace, query, path=".")` — 在工作区内递归执行有界字面量搜索。
- `write_file(workspace, path, content, modified_files=None)` — 创建或完整替换有大小限制的 UTF-8 文本文件。
- `replace_text(workspace, path, old_text, new_text, modified_files=None)` — 仅替换唯一的精确文本匹配。
- `run_command(workspace, command, timeout=None)` — 在工作区中执行命令，捕获输出、错误、退出码及超时状态。

## 实现总结

实现了统一的 `ToolResult` 数据结构和轻量 `ToolRegistry`，使工具 schema、参数绑定、分发和异常转换集中管理。`Workspace` 使用规范化后的真实路径执行边界判断，文件工具共享该检查并对目录、读取、搜索、写入和精确替换施加明确上限。

`run_command` 使用标准库子进程执行，默认超时 30 秒、最大超时 60 秒，并限制返回输出。命令在独立进程组中运行，超时后终止整个子进程树；小型 denylist 会在执行前拒绝明显破坏性命令。文件递归通过已解析目录集合避免 symlink/junction 循环。

## 测试情况

执行命令：

```bash
python -m pytest tests/test_workspace.py tests/test_registry.py -q
python -m pytest tests/test_file_tools.py -q
python -m pytest tests/test_shell_tool.py -q
python -m pytest -q
```

测试结果：

```text
12 passed
25 passed
18 passed
55 passed in 2.78s
```

测试覆盖工作区内外路径、规范化路径、工具注册与 schema、未知工具、无效参数、工具异常转换、文件列表深度与上限、带行号的分段读取、二进制与缺失文件、文本搜索上限、精确替换、修改文件跟踪、symlink/junction 循环、命令工作目录、stdout/stderr、非零退出、超时进程树清理、输出截断和危险命令拒绝。

## 设计决策

- 使用单一 `ToolResult`，让可恢复失败成为显式观察结果，避免工具异常泄漏到后续 `AgentCore`。
- 将路径解析集中在 `Workspace`，所有文件工具复用同一边界语义，减少重复安全逻辑。
- `replace_text` 只允许一个精确匹配；缺失或多重匹配均失败，避免模糊或批量误改。
- 工具注册使用简单字典和函数签名绑定，不引入工厂、继承树或 agent framework。
- 命令执行使用独立进程组并清理进程树，使 timeout 对实际子进程生效。
- 目录和命令控制均属于 best-effort execution controls，而不是安全沙箱。

## 与原计划的偏差

- 无。

## 已知限制

- 危险命令 denylist 仅覆盖明显破坏性模式，不能识别所有等价写法或恶意命令组合。
- `run_command` 仍通过平台 shell 执行字符串命令，具体解析行为依赖操作系统。
- 文件工具仅将 UTF-8 文本作为可读写文本处理；二进制文件和其他编码会返回受控错误或在搜索时跳过。
- 工作区边界、命令 guard、超时和输出限制是控制措施，不构成针对任意恶意代码的安全沙箱。

## 下一阶段

Phase 2 将在收到明确指令后实现 OpenAI-compatible `LLMClient` 与 native tool calling；本阶段未提前实现任何 Phase 2 功能。
