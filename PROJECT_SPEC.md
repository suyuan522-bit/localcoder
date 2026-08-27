# LocalCoder Project Specification

> **Status: FROZEN**
>
> This document is the single source of truth for LocalCoder v1.
> Do not modify this specification unless the user explicitly requests a specification change.
> Implementation must conform to this document. When implementation and specification conflict, stop and report the conflict instead of silently changing the specification.

## 1. Project Overview

### 1.1 Project Name

**LocalCoder**

### 1.2 Positioning

LocalCoder is a lightweight local coding agent implemented from scratch without any agent framework or agent SDK.

It uses a large language model's native tool-calling capability to autonomously:

1. inspect a local code workspace;
2. read and search source files;
3. make targeted code edits;
4. execute local commands and tests;
5. observe real execution results and errors;
6. continue fixing the project when verification fails;
7. explicitly finish the task with a summary and verification evidence.

The project is intentionally scoped to the core mechanisms of a coding agent rather than attempting to reproduce every feature of Claude Code, Codex, OpenCode, or similar products.

### 1.3 Core Design Goals

LocalCoder v1 is designed around four properties:

- **Autonomous** — a persistent agent loop drives multi-step task execution.
- **Verified** — code changes should be checked using real local execution when a reasonable verification method exists.
- **Observable** — tool calls, results, errors, edits, and verification steps are visible through a trace.
- **Controlled** — local file and shell execution are constrained by explicit workspace and runtime guards.

### 1.4 Source Assignment Constraints

The implementation must satisfy these assignment-level constraints:

- The coding agent must be independently designed and implemented.
- No agent framework or agent SDK may be used.
- Model vendor API client libraries and native tool calling are allowed.
- File operations and command execution must happen locally and be implemented by this project.
- The implementation must own the important agent logic, including context/history management, tool definitions and local execution, model-output handling, loop termination, and error handling.
- API keys and other credentials must never be committed to the repository or included in documentation/demo content.
- The repository must preserve normal development history; pushed history must not be rewritten.

## 1.5 Documentation Language Policy

The following language policy is a frozen project-level requirement:

- `PROJECT_SPEC.md`, `IMPLEMENTATION_PLAN.md`, `CODEX_RUNBOOK.md`, and Codex execution prompts remain in **English**.
- All phase reports under `docs/phases/phase-N.md` must be written in **Simplified Chinese**.
- The completion summary returned by Codex after each phase must be written in **Simplified Chinese**.
- The final project completion/release report after Phase 6 must be written in **Simplified Chinese**.
- The submission `README.txt` must be written in **Simplified Chinese**.
- The repository `README.md` should be **primarily in Simplified Chinese**, while standard technical terms may remain in English when clearer.
- Source-code identifiers, class names, function names, API names, CLI commands, file paths, Git commit messages, code blocks, raw test output, error messages, and standard technical terminology may remain in **English**.
- Do not translate code identifiers merely for stylistic consistency.
- Source-code comments and docstrings may use English or Chinese, but should remain concise and internally consistent.

This policy intentionally keeps implementation instructions precise and conventional for software-engineering work while making project reports easier to review, study, and use for interview preparation.

## 2. Non-Goals

LocalCoder v1 must **not** implement the following unless the user explicitly changes the frozen specification:

- multi-agent architecture;
- Planner Agent;
- Reviewer/Critic Agent;
- LangChain, LlamaIndex, OpenAI Agents SDK, Claude Agent SDK, AutoGen, CrewAI, or another agent framework;
- web UI, React, Vue, Electron, or desktop GUI;
- browser automation;
- RAG;
- embeddings;
- vector databases;
- long-term semantic memory;
- MCP;
- AST-level code rewriting;
- Docker sandboxing;
- container orchestration;
- GitHub pull-request automation;
- automatic Git commits performed by the runtime coding agent;
- SWE-bench integration;
- multi-model voting or model ensembles.

YAGNI applies: do not add infrastructure or abstraction that is not required by this specification.

## 3. Technology Stack

### Required

- **Python:** 3.11+
- **LLM API:** OpenAI-compatible API
- **Agent/model interaction:** native tool calling
- **Command execution:** Python `subprocess`
- **Filesystem:** Python `pathlib`
- **CLI:** Python `argparse`
- **Testing:** `pytest`
- **Version control:** Git
- **Configuration:** environment variables

### Preferred Third-Party Dependencies

Keep dependencies minimal.

Expected dependencies:

- `openai`
- `pytest`

Optional only if genuinely useful:

- `python-dotenv`

Do not add an agent framework or unnecessary infrastructure library.

## 4. High-Level Architecture

```text
┌──────────────────────────────────────┐
│               User / CLI             │
│          Natural-language task       │
└──────────────────┬───────────────────┘
                   ↓
┌──────────────────────────────────────┐
│              AgentCore               │
│ Agent loop / state / termination     │
│ tool dispatch / error feedback       │
└──────────────────┬───────────────────┘
                   ↕
┌──────────────────────────────────────┐
│           ContextManager             │
│ history / bounded context /          │
│ tool-output truncation               │
└──────────────────┬───────────────────┘
                   ↕
┌──────────────────────────────────────┐
│              LLMClient               │
│ OpenAI-compatible API /              │
│ native tool calling                  │
└──────────────────┬───────────────────┘
                   ↓
┌──────────────────────────────────────┐
│             ToolRegistry             │
│ schemas / validation / dispatch      │
└──────────────────┬───────────────────┘
                   ↓
┌──────────────────────────────────────┐
│              Local Tools             │
│ file / search / edit / shell / diff  │
└──────────────────┬───────────────────┘
                   ↓
              Workspace

TraceLogger observes the complete loop and prints concise execution events.
```

## 5. Project Structure

Target structure:

```text
localcoder/
├── main.py
├── agent.py
├── llm_client.py
├── context.py
├── config.py
├── prompts.py
├── trace.py
│
├── tools/
│   ├── __init__.py
│   ├── base.py
│   ├── registry.py
│   ├── workspace.py
│   ├── file_tools.py
│   ├── shell_tool.py
│   └── git_tool.py
│
├── tests/
│   ├── test_workspace.py
│   ├── test_file_tools.py
│   ├── test_shell_tool.py
│   ├── test_registry.py
│   ├── test_context.py
│   ├── test_llm_client.py
│   └── test_agent.py
│
├── examples/
│   └── todo_demo/
│       ├── ...
│       └── tests/
│
├── docs/
│   └── phases/
│       ├── phase-1.md
│       ├── phase-2.md
│       ├── phase-3.md
│       ├── phase-4.md
│       ├── phase-5.md
│       └── phase-6.md
│
├── PROJECT_SPEC.md
├── IMPLEMENTATION_PLAN.md
├── CODEX_RUNBOOK.md
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── LICENSE
```

Files may be split only when there is a clear responsibility-based reason. Do not introduce redundant layers.

## 6. Core Data Types and Interfaces

The exact implementation syntax may vary slightly, but the following conceptual interfaces must remain stable.

### 6.1 ToolResult

All tools return one common result type.

Required fields:

```text
success: bool
output: str
error: str | None
metadata: dict
```

Purpose:

- AgentCore receives one consistent result shape.
- Tool-specific exceptions do not leak into AgentCore.
- Tool failures become observations that can be sent back to the model.

### 6.2 AgentState

AgentCore maintains explicit runtime state.

At minimum:

```text
task: str
step_count: int
modified_files: set[str]
verification_runs: list
last_error: str | None
last_edit_step: int | None
finished: bool
```

The state is intentionally small. Do not implement a complex planner/state machine.

### 6.3 LLM Response Abstraction

`LLMClient` should normalize provider responses enough that `AgentCore` can determine:

- assistant text, if any;
- zero or more tool calls;
- tool call IDs;
- tool names;
- parsed arguments.

Provider-specific response handling belongs in `LLMClient`, not in `AgentCore`.

## 7. Configuration

Configuration must be provided through environment variables and/or safe command-line arguments.

Required environment variables:

```text
LLM_API_KEY
LLM_BASE_URL
LLM_MODEL
```

Recommended runtime defaults:

```text
MAX_STEPS = 30
MAX_DYNAMIC_MESSAGES = 24
MAX_TOOL_OUTPUT_CHARS = 12000
READ_FILE_MAX_LINES = 200
DEFAULT_COMMAND_TIMEOUT_SECONDS = 30
MAX_COMMAND_TIMEOUT_SECONDS = 60
```

These values should be configurable without changing core logic.

`.env` must be ignored by Git.

`.env.example` must contain names/placeholders only and no real secrets.

## 8. CLI

Minimum supported invocation:

```bash
python main.py --workspace ./examples/todo_demo --task "Implement the delete command and ensure all tests pass."
```

If `--task` is omitted, an interactive single-task prompt may be provided.

LocalCoder v1 is **task-oriented**, not a persistent multi-user chat application:

```text
one task
→ autonomous execution
→ final result
```

## 9. Agent Loop

`AgentCore` is the central coordinator.

Conceptual loop:

```text
initialize task/state/context

for step in 1..MAX_STEPS:
    call LLM with current messages + tool schemas

    if model requests tool calls:
        validate and execute each requested tool
        convert each result to a tool observation
        add observations to context
        update AgentState
        continue

    if task has been explicitly finished:
        return final result

    otherwise:
        keep the model response in context and continue when appropriate

if MAX_STEPS is reached:
    terminate with a controlled failure
```

### 9.1 Normal Termination

The model must use the explicit `finish` tool to declare task completion.

Do not treat "the model stopped calling tools" as sufficient evidence of successful completion.

### 9.2 Abnormal Termination

The loop must terminate safely on:

- `MAX_STEPS`;
- unrecoverable configuration error;
- user interrupt;
- unrecoverable provider/API failure after bounded retries.

Tool failures should normally be returned to the model as observations so that the agent has a chance to recover.

## 10. Tool Registry

`ToolRegistry` is responsible for:

- registering tools;
- exposing model-facing tool schemas;
- validating tool names;
- dispatching calls;
- converting failures into `ToolResult`;
- keeping AgentCore independent from tool implementations.

AgentCore must not contain a long `if/elif` dispatch chain for individual tool names.

Do not build unnecessary factory/provider hierarchies.

## 11. Workspace Boundary

All file-oriented tools operate relative to one user-selected workspace root.

Required behavior:

1. resolve the requested path;
2. normalize it;
3. verify that the resolved path remains inside the workspace root;
4. reject traversal or absolute paths that escape the workspace.

Examples to reject:

```text
../../outside.txt
C:\Windows\System32\...
/etc/passwd
```

when those paths resolve outside the configured workspace.

The workspace layer should be shared by file tools.

### Security Disclaimer

Workspace checks, command guards, timeouts, and output limits are **best-effort execution controls, not a security sandbox**.

README documentation must not claim that LocalCoder securely sandboxes arbitrary malicious commands.

## 12. Tools

LocalCoder v1 exposes exactly the following core tools unless an implementation-only helper is required internally.

### 12.1 `list_files`

Purpose: inspect workspace structure.

Suggested arguments:

```text
path: str = "."
max_depth: int = 2
```

Requirements:

- operate only inside workspace;
- return readable relative paths;
- ignore obvious noise where reasonable (`.git`, `__pycache__`, virtual environments);
- cap excessive output.

### 12.2 `read_file`

Purpose: read a bounded range of a text file.

Suggested arguments:

```text
path: str
start_line: int = 1
end_line: int | None = None
```

Requirements:

- workspace boundary enforcement;
- line-numbered output;
- default maximum of 200 lines per call;
- descriptive error for missing/binary/unreadable files;
- no silent full-file dump for very large files.

### 12.3 `search_text`

Purpose: locate text across workspace files.

Suggested arguments:

```text
query: str
path: str = "."
```

Requirements:

- recursive search inside workspace;
- return file + line number + concise matching line;
- ignore `.git`, caches, and virtual environments;
- cap match count/output;
- standard library implementation is sufficient.

### 12.4 `write_file`

Purpose: create or fully replace a reasonably sized text file.

Suggested arguments:

```text
path: str
content: str
```

Requirements:

- workspace boundary enforcement;
- create parent directories when reasonable;
- mark path in `modified_files`;
- return concise success metadata.

### 12.5 `replace_text`

Purpose: make a targeted textual edit.

Suggested arguments:

```text
path: str
old_text: str
new_text: str
```

Requirements:

- the target text must match exactly;
- do not silently perform fuzzy replacement;
- if no match exists, return a recoverable error instructing the agent to read the latest file;
- if the match is ambiguous because it appears multiple times, return an error instead of replacing all occurrences unless the implementation exposes an explicit safe occurrence selector;
- mark the file as modified on success.

### 12.6 `run_command`

Purpose: run local verification/build/program commands.

Suggested arguments:

```text
command: str
timeout: int | None = None
```

Requirements:

- execute with working directory set to workspace;
- capture stdout, stderr, exit code, and timeout status;
- default timeout 30 seconds;
- maximum user/model-requested timeout 60 seconds;
- truncate excessive output before returning it to the model;
- record command, exit code, step, and concise output in `verification_runs`;
- use a small dangerous-command denylist for obviously destructive commands.

Minimum dangerous patterns should cover clear examples such as:

```text
rm -rf /
mkfs
shutdown
reboot
format C:
del /s /q C:\
```

The denylist is not a sandbox and must be documented as such.

### 12.7 `get_diff`

Purpose: show repository changes relevant to the workspace.

Requirements:

- when the workspace is inside a Git repository, return a diff scoped to the workspace;
- use Git via a local subprocess;
- cap output;
- when no Git repository exists, return a useful message and the known `modified_files` summary rather than crashing.

### 12.8 `finish`

Purpose: explicit normal termination protocol.

Suggested arguments:

```text
summary: str
verification: str
limitations: str | None = None
```

Required behavior:

- store a final concise summary;
- include changed files;
- include verification evidence or an explicit reason why verification could not reasonably be run;
- mark state as finished;
- produce the final user-facing completion result.

### Verification-aware finish policy

If source-code files were modified after the latest successful verification run, the first attempt to finish should return a recoverable warning/error asking the agent to run an appropriate verification command.

If verification is genuinely unavailable, the agent may finish only by explicitly stating that limitation in the final result.

This is intended to encourage verification, not to falsely claim formal correctness.

## 13. Context Management

`ContextManager` owns conversation/history policy.

### 13.1 Permanently Retained

- system prompt;
- original user task.

### 13.2 Dynamic History

Keep a bounded recent history, with a default target of at most 24 dynamic messages.

Do not implement embeddings or semantic long-term memory.

### 13.3 Tool Output Truncation

Tool results inserted into model context must be capped, defaulting to 12,000 characters.

For long output, prefer retaining useful beginning and ending portions with a marker such as:

```text
[output truncated]
```

### 13.4 Large Files

Large files should be inspected using bounded `read_file` ranges plus `search_text`, not by dumping the entire file into context.

## 14. System Prompt Policy

The system prompt should be concise and encode operational rules, not hidden reasoning.

It should communicate at least:

1. inspect real project state before making assumptions;
2. use tools to obtain file contents;
3. prefer targeted edits over unnecessary rewrites;
4. verify code changes when a reasonable verification method exists;
5. use execution errors as feedback and continue fixing;
6. never intentionally access paths outside the workspace;
7. never claim successful verification without evidence;
8. use `finish` when the task is complete.

Do not ask the model to reveal private chain-of-thought. Tool calls and concise action summaries are sufficient.

## 15. Verification Loop

The intended core workflow is:

```text
EXPLORE
→ EDIT
→ VERIFY
→ observe failure
→ inspect relevant code/error
→ EDIT
→ VERIFY
→ success
→ DIFF
→ FINISH
```

Testing cannot prove absolute correctness. Documentation and final output must describe verification as evidence from real execution, not as a proof of correctness.

## 16. Trace / Observability

The terminal trace must make the agent loop easy to follow.

Minimum event information:

- step number;
- inferred stage: `EXPLORE`, `EDIT`, `VERIFY`, or `DONE`;
- tool name;
- concise arguments;
- success/failure;
- concise result/error;
- changed-file summary;
- final verification result.

Example style:

```text
Step 4 · EDIT
Tool: replace_text
File: src/todo.py
Status: SUCCESS
```

Do not print API keys, Authorization headers, complete environment dumps, or other secrets.

Trace formatting may be simple text; no UI framework is required.

## 17. LLM Client

`LLMClient` responsibilities:

- create/use an OpenAI-compatible client;
- load base URL, API key, and model from configuration;
- send messages and tool schemas;
- parse native tool calls;
- normalize provider response shape for AgentCore;
- implement bounded retries for transient API errors;
- never log secrets.

AgentCore must not directly contain provider-specific API code.

## 18. Error Handling

Required categories:

### Tool errors

Return a failed `ToolResult` to the model when recovery is reasonable.

Examples:

- file not found;
- replacement target not found;
- ambiguous replacement;
- command non-zero exit;
- command timeout;
- path outside workspace;
- unknown tool.

### API errors

Use bounded retry for transient failures.

After retry exhaustion:

- terminate cleanly;
- provide a concise error;
- do not loop indefinitely.

### Configuration errors

Missing required LLM configuration should fail fast with a helpful message.

## 19. Testing Strategy

TDD is preferred for deterministic local components.

### 19.1 Workspace Tests

Cover:

- normal in-workspace path;
- `..` traversal;
- absolute outside path;
- nested valid path.

### 19.2 File Tool Tests

Cover:

- list files;
- bounded reads and line numbering;
- missing file;
- search matches;
- write file;
- exact replacement;
- replacement target missing;
- ambiguous replacement;
- outside-workspace rejection.

### 19.3 Shell Tool Tests

Cover:

- successful command;
- non-zero exit;
- stdout/stderr capture;
- timeout;
- output truncation;
- dangerous-command rejection.

Tests must use harmless platform-appropriate commands.

### 19.4 Tool Registry Tests

Cover:

- successful dispatch;
- unknown tool;
- invalid arguments;
- tool exception converted to `ToolResult`.

### 19.5 Context Tests

Cover:

- permanent messages retained;
- bounded dynamic history;
- long tool output truncated.

### 19.6 LLM Client Tests

Use mocks/fakes where possible.

Cover:

- normal assistant text;
- one tool call;
- multiple tool calls if supported by implementation;
- malformed/invalid tool arguments handled predictably;
- transient retry behavior.

Do not require paid network API calls in the normal unit-test suite.

### 19.7 Agent Loop Tests

Implement a `FakeLLMClient` for deterministic tests.

At minimum test:

- model requests `read_file` then `finish`;
- multi-step tool execution;
- tool failure is fed back and later recovered;
- explicit `finish`;
- `MAX_STEPS` termination;
- verification-aware finish behavior.

## 20. Demo Project

Provide a small Python Todo CLI under:

```text
examples/todo_demo/
```

The demo project should already have a simple structure and tests.

Suggested existing features:

- add todo;
- list todos;
- complete todo.

Recommended demo task:

> Implement a `delete` command that deletes a todo by ID, add/adjust the relevant tests, and ensure the full test suite passes.

The task should be real but small enough for a reliable two-minute demonstration.

The demo should naturally allow the agent to show:

```text
list/search/read
→ targeted edit
→ test
→ possibly observe a failure
→ fix
→ test passes
→ diff
→ finish
```

Do not intentionally hard-code the runtime agent to solve only this demo.

## 21. README Requirements

The repository `README.md` should be written primarily in Simplified Chinese, retaining standard English technical terms where clearer, and should contain:

1. project overview;
2. features;
3. architecture;
4. agent loop;
5. tool descriptions;
6. safety/control limitations;
7. installation;
8. environment configuration;
9. usage;
10. demo example;
11. project structure;
12. design decisions;
13. limitations.

Important design decisions to explain:

- why single-agent rather than multi-agent;
- why native tool calling;
- why ToolRegistry;
- why explicit `finish`;
- why `MAX_STEPS`;
- why bounded context;
- why targeted `replace_text`;
- why verification loop;
- why workspace/command guards are controls rather than a true sandbox.

## 22. Submission-Oriented Constraints

The implementation process and repository must make it easy to prepare the required submission materials.

- Public Git repository.
- Normal, readable commit history.
- No secret credentials in repository history.
- A separate concise submission `README.txt` must be written in Simplified Chinese and can contain repository URL, run instructions, feature highlights, and short notes.
- Demo behavior should be suitable for a video of no more than two minutes.

Do not commit the final private API key or expose it in screen recordings.

## 23. Code Quality Rules

- Prefer simple, focused modules.
- Use type hints for public interfaces where useful.
- Add docstrings/comments for non-obvious behavior, not for every trivial line.
- Avoid deep inheritance.
- Avoid abstraction for abstraction's sake.
- Keep provider-specific code inside `LLMClient`.
- Keep workspace/path logic centralized.
- Keep tool execution independent of AgentCore.
- Keep deterministic components unit-testable.
- No silent exception swallowing.
- No hidden network calls outside the configured LLM API.
- No telemetry.

## 24. Acceptance Criteria

LocalCoder v1 is complete only when all of the following are true.

### Core Agent

- [ ] accepts a natural-language coding task;
- [ ] uses an LLM with native tool calling;
- [ ] performs multiple autonomous tool steps;
- [ ] feeds tool results/errors back to the model;
- [ ] terminates explicitly with `finish`;
- [ ] stops safely at `MAX_STEPS`.

### Local Tools

- [ ] `list_files`;
- [ ] `read_file`;
- [ ] `search_text`;
- [ ] `write_file`;
- [ ] `replace_text`;
- [ ] `run_command`;
- [ ] `get_diff`;
- [ ] `finish`.

### Context

- [ ] permanent task/system context;
- [ ] bounded dynamic history;
- [ ] bounded tool output;
- [ ] no vector database or embedding memory.

### Controlled Execution

- [ ] workspace path boundary;
- [ ] command timeout;
- [ ] command output limit;
- [ ] dangerous-command denylist;
- [ ] documentation clearly states this is not a sandbox.

### Verification and Observability

- [ ] changed files tracked;
- [ ] verification runs tracked;
- [ ] verification-aware finish behavior;
- [ ] readable terminal trace;
- [ ] diff available when Git exists.

### Engineering

- [ ] deterministic unit tests pass;
- [ ] AgentCore tested with fake/mocked LLM;
- [ ] no real API key committed;
- [ ] `.env.example` provided;
- [ ] README documents architecture and limitations;
- [ ] demo task succeeds reliably;
- [ ] Git history contains staged, understandable phase commits.

## 25. Final Scope Rule

When there is a trade-off between adding a new feature and making an existing required feature more reliable, choose reliability.

LocalCoder v1 should be a small coding agent whose core mechanism is easy to inspect, test, demonstrate, and defend in an interview.
