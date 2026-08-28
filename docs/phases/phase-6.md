# Phase 6 — 文档、演示打磨与发布就绪

**状态：** 已完成
**日期：** 2026-08-28
**目标提交：** `docs: prepare LocalCoder submission`

## 阶段目标

停止功能开发，在不新增架构或主要功能的前提下完成提交所需的说明、配置占位、许可证和演示指引，并对当前稳定实现执行最终确定性验证与秘密审计。

## 文件变更

- `README.md`
- `README.txt`
- `.env.example`
- `.gitignore`
- `requirements.txt`
- `LICENSE`
- `docs/phases/phase-6.md`

## 新增或变更接口

- 无运行时接口变更；本阶段只校准发布文档、样例配置、依赖声明与许可证。

## 实现总结

`README.md` 以简体中文说明项目定位、架构、agent loop、8 个核心工具、控制边界、安装、环境变量、CLI、Todo delete 演示、验证方式、目录、设计决策和限制。文档明确说明 `.env.example` 不会被运行时自动加载，真实配置必须由进程环境变量提供。

`README.txt` 为少于 1000 个中文字符的提交摘要，包含公开仓库 URL、运行方法、亮点、限制简注与不泄露密钥的提醒。`.env.example` 仅含占位符；`.gitignore` 忽略 `.env.*` 并显式保留 `.env.example`，同时覆盖常见 Python、测试与构建产物。`requirements.txt` 保持最小依赖集合并标明运行/测试用途。新增标准 MIT License，版权主体为 `LocalCoder contributors`。

Todo delete 是主要演示任务：仓库保留只实现 `add`、`list`、`complete` 的受控基线；README 指示在临时副本中只复制 `todo.py` 与 `tests/test_todo.py`，初始化独立 Git 仓库、设置该临时仓库专用的无效示例身份，并提交干净 baseline。随后 agent 自行增加 delete 和测试，`get_diff` 因而展示真实 Git 差异，且不会污染主 fixture 或把任务答案硬编码进运行时。

## 测试情况

执行命令：

```powershell
python main.py --help
# 按 README 的 Todo delete 演示准备临时工作区：复制 todo.py 与 tests/test_todo.py，
# git init -b main，设置临时仓库身份，git add/commit 基线，并调用 get_diff。
python -m pytest -q
Push-Location .\examples\todo_demo
python -m pytest -q
Pop-Location
```

测试结果：

```text
main.py --help exited with code 0
temporary Todo Git baseline committed successfully
TEMP_BASELINE_CLEAN=PASS
GET_DIFF_SUCCESS=True
GET_DIFF_GIT_REPOSITORY=True
118 passed in 10.43s
5 passed in 0.08s
```

README 的临时演示准备流程已实际执行：临时仓库只提交 `todo.py` 与 `tests/test_todo.py`，`get_diff` 确认其为 Git 工作区；验证后临时目录已删除。所有确定性测试通过。它们不访问真实或付费 LLM API。

## 最终演示状态

本次 Phase 6 开始时，进程环境中的 `LLM_API_KEY`、`LLM_BASE_URL` 和 `LLM_MODEL` 均为 `UNSET`；因此未发起 API 请求，也没有重跑实时 Todo delete 演示。README 的临时 Git baseline 与 `get_diff` 识别已完成本地验证；待在安全配置本地凭据后，才可执行其中的 agent 命令。

既有证据与本阶段状态须区分：Phase 5 推送后的独立 Real Model Gate 曾使用 Alibaba Cloud Bailian / DashScope OpenAI-compatible API 与 `qwen3-coder-flash` 通过只读冒烟和 Todo delete 端到端门禁；该事实记录于 `docs/phases/phase-5.md`，不是本次 Phase 6 的 live run。

## 设计决策

- 文档将“尽力而为的控制”与“安全沙箱”明确区分，避免夸大路径检查、超时或命令 denylist 的安全保证。
- Todo delete 演示使用随机临时目录和独立 Git baseline，保留仓库 fixture 作为可重复的未实现基线，同时确保 `get_diff` 走真实 Git 路径而不是 non-Git 回退。
- 配置模板仅保留变量名和占位符；不引入 dotenv 或其他未被运行时使用的依赖。
- 许可证采用标准 MIT 文本，使用中性的 `LocalCoder contributors`，不推测或写入个人身份。

## 与原计划的偏差

- 计划允许打磨 `examples/todo_demo/...`，但最终确定性测试未发现 bug，且现有基线正是 delete 演示所需的起点，因此未修改 fixture、源码或测试。
- 计划要求“本地凭据可用时”运行最终实时 demo；三个必需变量均未设置，按秘密安全要求跳过，不伪造执行结果。

## 已知限制

- LocalCoder 没有容器或操作系统级安全沙箱；不可将危险或不可信命令视为安全执行对象。
- 真实模型的工具选择、首轮测试结果和纠错效果随 provider、模型与环境变化；已通过的 DashScope / `qwen3-coder-flash` 门禁不能代表所有模型。
- `get_diff` 的输出有长度上限，未跟踪文件只显示路径；非 Git 工作区只能显示 agent 已知的修改文件。
- 项目是一次一任务的本地 CLI，不提供多代理、持久会话、Web UI、浏览器自动化或自动 Git 提交。

## 秘密审计

- 进程环境检查仅报告变量状态：`LLM_API_KEY=UNSET`、`LLM_BASE_URL=UNSET`、`LLM_MODEL=UNSET`；未读取或打印变量值。
- `.env.example` 已人工核对为占位符；`.env` 与 `.env.*` 已受 Git 忽略规则保护，`.env.example` 显式保留。
- 已对受 Git 跟踪文件执行常见 API key、GitHub token、AWS access key 和 JWT 模式扫描；扫描只输出命中文件名而不输出匹配内容。Phase 6 发布文件无命中；全仓库有两处既有 `sk-` 模式命中，均位于早期提交的 `tests/test_agent.py` 与 `tests/test_llm_client.py` 的测试函数中，未在本阶段修改。审计未输出其文本或任何变量值。
- 父代理已对全部已推送历史完成高置信扫描：`HISTORY_HIGH_CONFIDENCE_SECRET_FILE_MATCHES=0`、`PUSHED_ENV_FILE_PATH_MATCHES=0`。

## 发布就绪状态

- 公开仓库：<https://github.com/suyuan522-bit/localcoder>
- 文档、样例配置、依赖声明和许可证：已完成。
- 确定性完整测试与 Todo 示例测试：已通过。
- 本次 live demo：因本地凭据未配置而未重跑；Phase 5 后真实模型门禁作为已有独立证据保留。
- 目标提交：`docs: prepare LocalCoder submission`。

## 下一阶段

六个阶段均已完成；除非收到新的明确需求，不再启动新的功能阶段。
