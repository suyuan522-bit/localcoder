# LocalCoder

LocalCoder 是一个从零实现的轻量级本地编程智能体。它通过 OpenAI-compatible API 的原生 tool calling，在一个明确指定的本地工作区中完成“检查代码 → 定点编辑 → 运行验证 → 查看差异 → 显式结束”的单任务流程。项目刻意不使用任何 agent framework 或 agent SDK，重点展示编程智能体的核心闭环、可观测性与边界控制。

仓库地址：[https://github.com/suyuan522-bit/localcoder](https://github.com/suyuan522-bit/localcoder)

## 特性

- 原生 tool calling：将模型响应标准化为文本与工具调用，由本地 `AgentCore` 协调执行。
- 自主 agent loop：最多 30 步；工具失败会作为观察反馈给模型，正常完成必须调用 `finish`。
- 有界上下文：保留原始任务并限制动态消息与工具输出，避免无界增长。
- 验证感知：源代码变更后，若没有新的成功验证，`finish` 会要求先运行合适的命令。
- 可观测 Trace：按 EXPLORE、EDIT、VERIFY、DONE 输出精简事件，不回显密钥或完整 diff。
- 工作区范围：文件工具会规范化路径并拒绝越出所选工作区的访问。
- Git 变更可见：`get_diff` 只显示当前工作区范围内的有界变更。
- 确定性测试与受控 Todo 示例：无需真实 API 即可验证大部分核心行为和完整工具序列。

## 架构

```text
CLI
  ↓
AgentCore ── ContextManager ── LLMClient（OpenAI-compatible API）
  ↓                         ↑
ToolRegistry ───────────────┘
  ↓
Workspace-scoped local tools ── 本地文件、命令与 Git
  ↓
指定工作区
```

`TraceLogger` 旁路观察整个循环；`ToolResult` 为每个工具提供统一的 `success`、`output`、`error` 与 `metadata` 结果形状。

## Agent loop

1. CLI 读取任务、工作区和三个必需环境变量。
2. `AgentCore` 将消息与工具 schema 交给模型。
3. 模型请求工具时，`ToolRegistry` 校验参数并调度本地实现；结果会写回上下文。
4. 模型据此继续探索、编辑和验证；编辑后的代码应通过 `run_command` 获取真实执行证据。
5. 模型调用 `get_diff` 检查工作区变更，并以 `finish` 显式报告总结、验证和限制。
6. 达到 `MAX_STEPS`、配置错误、API 不可恢复失败或中断时，循环受控结束。

## 8 个核心工具

| 工具 | 用途 |
| --- | --- |
| `list_files` | 有界列出工作区目录树。 |
| `read_file` | 按行读取有限范围的 UTF-8 文本。 |
| `search_text` | 在工作区内递归查找字面文本。 |
| `write_file` | 创建或完整写入合理大小的文本文件。 |
| `replace_text` | 只替换唯一、精确匹配的一处文本。 |
| `run_command` | 在工作区中运行受超时与输出上限控制的命令。 |
| `get_diff` | 读取限定在当前工作区的 Git diff 与未跟踪文件列表。 |
| `finish` | 显式结束任务并输出变更、验证与限制摘要。 |

## 安全与控制边界

- 文件工具限制在 `--workspace` 指定根目录内，拒绝路径穿越及工作区外的绝对路径。
- `read_file`、搜索、目录列表、写入内容和命令输出都有上限；命令默认超时 30 秒，最长 60 秒。
- `run_command` 会拦截少量明显危险的破坏性命令模式；Git 输出按工作区 pathspec 限定。
- Trace 会对已知 API key 进行脱敏，并避免打印完整环境或授权头。

这些措施是**尽力而为的执行控制，不是安全沙箱**。不要让不受信任的任务、代码或命令在具有敏感权限的主机上运行；请在隔离环境中使用，并自行审查模型提出的改动。

## 安装

要求：Python 3.11+、可访问的 OpenAI-compatible LLM endpoint，以及 Git（使用 `get_diff` 时）。

```powershell
git clone https://github.com/suyuan522-bit/localcoder.git
cd localcoder
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

macOS/Linux 可将激活命令替换为 `source .venv/bin/activate`。

## 环境配置

运行时仅从**进程环境变量**读取下列配置；项目不会自动加载 `.env`。`.env.example` 仅提供占位模板，不能放入真实密钥或提交到 Git。

```powershell
$env:LLM_API_KEY = "<API_KEY>"
$env:LLM_BASE_URL = "https://<provider-endpoint>/v1"
$env:LLM_MODEL = "<model-name>"
```

可用以下命令确认变量名是否已配置，但不要在终端、截图或提交中打印变量值：

```powershell
if ($env:LLM_API_KEY) { 'LLM_API_KEY=SET' } else { 'LLM_API_KEY=UNSET' }
```

## 使用方法

只读检查示例：

```powershell
python main.py --workspace .\examples\todo_demo --task "Inspect this Todo project. Do not modify files. Summarize its commands and tests, then call finish."
```

程序将打印 Trace 和最终结果。退出码 `0` 表示任务以 `finish` 正常完成；`1` 表示 agent 未成功完成；`2` 表示环境变量或工作区配置无效。

### Todo delete 演示

仓库内的 `examples/todo_demo` 故意保留只含 `add`、`list`、`complete` 的基线。推荐在临时副本运行下述任务，让智能体自行新增按 ID 删除的命令与测试；这既不会改动主 fixture，也不会把答案硬编码进运行时。演示前会在临时目录初始化一个仅含 Todo 实现与测试的 Git baseline，因此 `get_diff` 展示的是真实 Git 工作区差异，而非非 Git 回退结果。

```powershell
$demoWorkspace = Join-Path $env:TEMP ("localcoder-todo-demo-" + [guid]::NewGuid())
New-Item -ItemType Directory $demoWorkspace | Out-Null
Copy-Item .\examples\todo_demo\todo.py $demoWorkspace
New-Item -ItemType Directory (Join-Path $demoWorkspace 'tests') | Out-Null
Copy-Item .\examples\todo_demo\tests\test_todo.py (Join-Path $demoWorkspace 'tests\test_todo.py')
@"
__pycache__/
.pytest_cache/
*.py[cod]
todos.json
"@ | Set-Content (Join-Path $demoWorkspace '.gitignore')
Push-Location $demoWorkspace
git init -b main
git config user.name "LocalCoder Demo"
git config user.email "localcoder-demo@example.invalid"
git add todo.py tests/test_todo.py .gitignore
git commit -m "demo: establish todo baseline"
Pop-Location
python main.py --workspace $demoWorkspace --task "Implement a delete command that deletes a todo by ID. Add relevant tests and ensure the full test suite passes. Inspect the final changes before finishing."
```

建议讲解顺序：架构 → 启动 agent → 探索 → 编辑 → 首次验证失败（若发生）→ 根据反馈修正 → 测试通过 → `get_diff` → `finish`。模型可能首次即通过；核心证据仍应是实际测试与 diff，而不是人为制造失败。

这个 .gitignore 只属于临时演示仓库；它忽略 Python/pytest 缓存、编译产物和手工 CLI 可能生成的 todos.json，让 get_diff 聚焦于源码与测试变更，不会修改 LocalCoder 仓库自身的 .gitignore。

## 验证

```powershell
python -m pytest -q
Push-Location .\examples\todo_demo
python -m pytest -q
Pop-Location
```

这些确定性测试不访问真实或付费 API。真实模型行为受 provider、模型版本、提示词和本地环境影响，应在提交演示前用自己的受控临时工作区复跑。

## 项目结构

```text
.
├── main.py                 # 单任务 CLI
├── agent.py                # AgentCore、状态和 finish 协议
├── llm_client.py           # OpenAI-compatible 原生工具调用
├── context.py              # 有界消息历史
├── config.py               # 运行上限与环境变量配置
├── trace_logger.py         # 可观测 Trace
├── tools/                  # 工作区、文件、命令、Git 与注册表
├── tests/                  # 确定性单元/集成测试
├── examples/todo_demo/     # 受控端到端演示基线
├── docs/phases/            # Phase 1–6 实际执行记录
├── PROJECT_SPEC.md         # 冻结需求规范
├── IMPLEMENTATION_PLAN.md  # 分阶段实施计划
└── CODEX_RUNBOOK.md        # 执行与提交规则
```

## 设计决策

- **单一 AgentCore，而非多代理：** v1 要证明可靠的工具闭环；单一协调器更容易追踪状态、测试和讲解，避免规划/评审代理带来的额外提示、同步与失败面。
- **原生 tool calling，而非 agent framework：** 工具 schema、历史管理、调度、终止和错误反馈由项目自身拥有，既满足“从零实现”的边界，也避免框架隐藏关键决策。
- **`ToolRegistry` 集中注册与调度：** 将 schema、参数校验、异常转换与具体工具隔离，使 `AgentCore` 不依赖一长串工具分支，新增或测试单个工具时责任更清晰。
- **显式 `finish`：** 模型停止调用工具不等于任务成功；完成调用必须携带总结与验证证据，避免把沉默误报为成功。
- **`MAX_STEPS`：** 为 API/工具循环提供硬上限，防止模型重复调用造成无界时间和成本；上限触发时给出受控失败而非继续运行。
- **有界 context：** 永久保留系统约束与原始任务，同时限制动态消息和工具输出，在保留近期反馈与控制 token/内存成本之间取平衡。
- **精确 `replace_text`：** 只接受唯一的精确旧文本，不做模糊或全局替换；这牺牲了少量便利性，换取更可预测、可复核的定点编辑。
- **验证 loop：** 编辑后的真实命令结果会回传模型，失败可驱动下一轮检查与修复；`finish` 对未验证编辑提出警告，避免把编辑动作本身当作正确性证据。
- **工作区与命令 guards 是 controls，不是 sandbox：** 路径边界、超时、输出上限和小型危险命令 denylist 用于降低误操作范围，但不能隔离任意恶意代码或绕过主机权限，故仍需隔离环境与人工审查。

## 已知限制

- 不提供 Docker/容器级安全隔离，不能安全执行任意恶意命令。
- 仅支持一个本地工作区与一次任务，不是持续聊天、多用户或多代理系统。
- 危险命令拦截是小型 denylist，不能替代系统安全策略。
- 真实 LLM 的成功率、工具选择和纠错质量会随 provider 与模型变化；测试无法证明所有真实任务都能成功。
- `get_diff` 对未跟踪文件只列路径，超长 diff 会截断中间内容；非 Git 工作区只能回退到 agent 已知的修改文件。

## 许可证

本项目采用 [MIT License](LICENSE)。
