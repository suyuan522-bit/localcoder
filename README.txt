LocalCoder 是一个从零实现的轻量级本地编程智能体，使用 OpenAI-compatible API 的原生 tool calling，在指定工作区内完成检查、编辑、测试、查看 diff 和显式结束。

公开仓库：https://github.com/suyuan522-bit/localcoder

运行：安装 Python 3.11+，执行 `python -m pip install -r requirements.txt`；在当前终端安全设置 LLM_API_KEY、LLM_BASE_URL、LLM_MODEL 后，运行：
`python main.py --workspace .\\examples\\todo_demo --task "Inspect this Todo project. Do not modify files. Summarize it and call finish."`

亮点：自主 agent loop；8 个本地工具；工作区路径边界、超时和输出限制；验证感知的 finish；可观测 Trace；受控 Todo delete 端到端演示及确定性测试。

简注：它不是安全沙箱，也不是多代理或通用 IDE。演示应在临时副本中进行；不要在仓库、文档、终端输出或录屏中放入任何 API key。
