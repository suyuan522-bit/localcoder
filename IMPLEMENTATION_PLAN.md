# LocalCoder Six-Phase Implementation Plan

> **Status: FROZEN EXECUTION ORDER**
>
> Implement one phase at a time.
> A phase is complete only after its tests pass, its phase document is updated, its changes are committed, and the commit is pushed.
> **After completing a phase, STOP. Do not begin the next phase without an explicit user instruction.**
>
> Read `PROJECT_SPEC.md` before every phase. The specification is authoritative.

## Global Constraints

- Python 3.11+.
- No agent framework/SDK.
- Use native tool calling through an OpenAI-compatible API.
- No secrets in source, docs, logs, commits, or demo content.
- Keep dependencies minimal.
- Prefer simple interfaces and deterministic tests.
- Do not implement any non-goal from `PROJECT_SPEC.md`.
- Do not modify `PROJECT_SPEC.md` unless explicitly instructed by the user.
- All `docs/phases/phase-N.md` reports and all phase-completion summaries returned to the user must be written in **Simplified Chinese**. Technical identifiers, commands, file paths, Git commit messages, code blocks, and raw test output may remain in English.
- Every completed phase must update `docs/phases/phase-N.md`.
- Every completed phase must run phase-specific tests and the full deterministic test suite.
- Every completed phase must end with one clear Git commit and `git push`.
- Never automatically enter the next phase.

---

# Phase 1 — Local Tool Foundation

## Goal

Build and test the deterministic local execution foundation without requiring an LLM API.

## Create/Modify

```text
config.py
tools/__init__.py
tools/base.py
tools/registry.py
tools/workspace.py
tools/file_tools.py
tools/shell_tool.py

tests/test_workspace.py
tests/test_file_tools.py
tests/test_shell_tool.py
tests/test_registry.py

docs/phases/phase-1.md
```

## Required Deliverables

### ToolResult

Implement the common tool result abstraction:

```text
success
output
error
metadata
```

### Workspace

Centralized workspace path resolution and boundary enforcement.

Must reject:

- `..` traversal escaping workspace;
- absolute paths outside workspace.

### ToolRegistry

Must support:

- registering tools;
- exposing tool definitions/schemas in a form usable by later LLMClient work;
- validating tool names;
- dispatching tool calls;
- returning `ToolResult`;
- converting unexpected tool exceptions to controlled failures.

Do not build a deep class hierarchy.

### File Tools

Implement and test:

- `list_files`
- `read_file`
- `search_text`
- `write_file`
- `replace_text`

Required edge behavior:

- line-numbered bounded reads;
- exact replacement;
- missing target error;
- ambiguous target error;
- output/match caps;
- workspace enforcement.

### Shell Tool

Implement and test `run_command`.

Required:

- workspace `cwd`;
- captured stdout/stderr/exit code;
- timeout;
- output truncation;
- obvious dangerous-command denylist;
- no secret/environment dumping in normal traces.

## Test Requirement

Start with failing tests for deterministic behaviors where practical.

At completion:

```bash
pytest -q
```

must pass.

Do not make live LLM API calls in Phase 1.

## Phase 1 Documentation

Update `docs/phases/phase-1.md` **in Simplified Chinese** using the required phase template.

- status: COMPLETE;
- objective;
- files created/modified;
- public interfaces;
- tests run and results;
- design decisions;
- limitations;
- next phase summary;
- target commit message.

## Commit

Recommended commit message:

```text
feat: implement local tool foundation
```

Push to `origin`.

Then STOP.

---

# Phase 2 — LLM Client and Native Tool Calling

## Goal

Add an OpenAI-compatible LLM client capable of sending messages plus tool schemas and normalizing native tool-call responses.

## Preconditions

- Phase 1 is COMPLETE and pushed.
- Working tree is clean.

## Create/Modify

```text
llm_client.py
config.py
tests/test_llm_client.py
.env.example
.gitignore
requirements.txt

docs/phases/phase-2.md
```

Modify Phase 1 files only when an interface bug discovered by Phase 2 genuinely requires it; document such changes.

## Required Deliverables

### Configuration

Load:

```text
LLM_API_KEY
LLM_BASE_URL
LLM_MODEL
```

Fail fast with clear errors when required configuration is missing.

No real key in repository.

### LLMClient

Responsibilities:

- instantiate/use OpenAI-compatible client;
- accept conversation messages;
- accept tool schemas from ToolRegistry;
- perform native tool calling;
- normalize assistant text and tool calls;
- preserve tool call IDs;
- parse tool arguments predictably;
- bounded retry for transient provider errors;
- never log credentials.

### Unit Tests

Use mocks/fakes.

Test:

- assistant text response;
- tool call response;
- malformed tool arguments;
- transient retry;
- no secret leakage in errors/logs.

Normal `pytest` must not depend on a paid API call.

### Optional Manual Smoke Test

A live API smoke test may be provided as an explicitly opt-in command/script if useful, but it must not run in the default test suite.

Its purpose is only to confirm that the configured model can request a simple tool such as `read_file`.

## Test Requirement

```bash
pytest -q
```

must pass.

## Phase 2 Documentation

Update `docs/phases/phase-2.md` **in Simplified Chinese** using the required phase template.

## Commit

Recommended:

```text
feat: add OpenAI-compatible LLM client
```

Push.

Then STOP.

---

# Phase 3 — AgentCore and Autonomous Agent Loop

## Goal

Implement the actual autonomous coding-agent loop and explicit task termination.

## Preconditions

- Phases 1–2 COMPLETE and pushed.
- Working tree clean.

## Create/Modify

```text
agent.py
prompts.py
main.py
tools/registry.py
tools/base.py
tests/test_agent.py

docs/phases/phase-3.md
```

## Required Deliverables

### AgentState

Track at minimum:

```text
task
step_count
modified_files
verification_runs
last_error
last_edit_step
finished
```

### AgentCore

Implement:

```text
task
→ LLM call
→ tool calls
→ registry dispatch
→ ToolResult
→ tool observation returned to model
→ repeat
→ explicit finish
```

Required behavior:

- multiple steps;
- multiple tool calls in a response if provider/abstraction supports them;
- tool failures returned to model as observations;
- bounded `MAX_STEPS`;
- clean user interrupt handling;
- unrecoverable API failure handling;
- no provider-specific API parsing in AgentCore.

### Finish Tool

Implement the explicit normal-termination tool.

AgentCore must not treat an arbitrary assistant sentence as successful completion.

### System Prompt

Concise rules from the specification:

- inspect;
- use actual tools;
- targeted edits;
- verify where reasonable;
- recover from errors;
- respect workspace;
- do not claim unverified success;
- finish explicitly.

### CLI

Support at minimum:

```bash
python main.py --workspace <path> --task "<task>"
```

### FakeLLMClient Tests

Build deterministic AgentCore tests without network access.

At minimum:

1. `read_file → finish`;
2. multiple sequential tools;
3. recover after tool failure;
4. `MAX_STEPS`;
5. explicit finish requirement.

## Test Requirement

```bash
pytest -q
```

must pass with no live API requirement.

## Phase 3 Documentation

Update `docs/phases/phase-3.md` **in Simplified Chinese** using the required phase template.

## Commit

Recommended:

```text
feat: implement autonomous agent loop
```

Push.

Then STOP.

---

# Phase 4 — Context, Verification and Trace

## Goal

Make the agent bounded, verification-aware, and clearly observable.

## Preconditions

- Phases 1–3 COMPLETE and pushed.
- Working tree clean.

## Create/Modify

```text
context.py
trace.py
agent.py
prompts.py
tools/base.py
tools/file_tools.py
tools/shell_tool.py

tests/test_context.py
tests/test_agent.py
tests/test_shell_tool.py

docs/phases/phase-4.md
```

## Required Deliverables

### ContextManager

Implement:

- permanently retained system prompt;
- permanently retained original task;
- bounded dynamic history (default 24 dynamic messages);
- tool-output truncation (default 12,000 chars);
- useful beginning/end retention for long output;
- no embeddings/vector DB.

### Verification Tracking

`run_command`/AgentState must record:

- command;
- step number;
- exit code;
- success/failure;
- concise result.

Track `last_edit_step`.

### Verification-Aware Finish

If source code changed after the latest successful verification:

- reject/warn on the first finish attempt;
- instruct the model to run an appropriate verification command;
- allow explicit limitation reporting when verification is genuinely unavailable.

Do not claim that tests prove formal correctness.

### TraceLogger

Print concise events:

- step;
- inferred stage (`EXPLORE`, `EDIT`, `VERIFY`, `DONE`);
- tool;
- concise arguments;
- status;
- concise output/error;
- final changed files and verification evidence.

Never display secrets.

### Integration Behavior

A deterministic/fake-agent scenario must demonstrate:

```text
edit
→ failing verification
→ correction
→ successful verification
→ finish
```

## Test Requirement

```bash
pytest -q
```

must pass.

## Phase 4 Documentation

Update `docs/phases/phase-4.md` **in Simplified Chinese** using the required phase template.

## Commit

Recommended:

```text
feat: add bounded context verification and trace
```

Push.

Then STOP.

---

# Phase 5 — Git Diff and End-to-End Integration

## Goal

Add change visibility and prove the full agent works against a controlled local coding task.

## Preconditions

- Phases 1–4 COMPLETE and pushed.
- Working tree clean.

## Create/Modify

```text
tools/git_tool.py
tools/registry.py
agent.py
trace.py

tests/test_git_tool.py
tests/test_agent.py

examples/todo_demo/...   # initial demo skeleton may be created here if not already present

docs/phases/phase-5.md
```

## Required Deliverables

### get_diff

Implement:

- Git diff scoped to workspace when a Git repository exists;
- output truncation;
- graceful fallback to known `modified_files` when Git is unavailable.

### Changed File Summary

Final result must clearly show changed files.

### End-to-End Integration

Create/complete a small Todo CLI fixture/project with tests.

Required existing functionality should be simple, e.g.:

- add;
- list;
- complete.

Validate LocalCoder against a task equivalent to:

> Implement a delete command by ID, add or adjust relevant tests, and ensure the full test suite passes.

The agent runtime must not contain hard-coded logic for this task.

### Reliability Work

Run the demo multiple times with the selected model/configuration.

Fix only specification-relevant instability.

Do not add new feature categories.

## Test Requirement

Run:

```bash
pytest -q
```

and the Todo demo test command.

If a live end-to-end agent run uses a real API, document it separately from deterministic unit tests.

## Phase 5 Documentation

Update `docs/phases/phase-5.md` **in Simplified Chinese** using the required phase template.

Document:

- end-to-end task;
- observed tool sequence;
- test command/result;
- known model-dependent behavior;
- any remaining demo risk.

## Commit

Recommended:

```text
feat: add git diff and end-to-end demo
```

Push.

Then STOP.

---

# Phase 6 — Documentation, Demo Polish and Release Readiness

## Goal

Stop feature development and make the repository submission-ready, understandable, and demo-stable.

## Preconditions

- Phases 1–5 COMPLETE and pushed.
- Core functionality stable.
- No new architecture/features in this phase.

## Create/Modify

```text
README.md
README.txt
.env.example
.gitignore
requirements.txt
LICENSE
examples/todo_demo/...
docs/phases/phase-6.md
```

Source code may be modified only for bugs found during final verification.

## Required Deliverables

### README.md

Write it primarily in **Simplified Chinese**, retaining standard English technical terms where clearer.

Must include:

- overview;
- features;
- architecture;
- agent loop;
- tools;
- safety/control limitations;
- installation;
- configuration;
- usage;
- example;
- project structure;
- design decisions;
- limitations.

### Submission README.txt

Write it in **Simplified Chinese** and keep it within **1000 Chinese characters**.

Include:

- public repository URL;
- how to run;
- core feature highlights;
- concise notes.

No API key.

### Demo Readiness

Prepare the Todo delete task as the primary demonstration.

The target two-minute narrative:

```text
architecture
→ start agent
→ explore
→ edit
→ verification failure/success feedback
→ correction when needed
→ tests pass
→ diff
→ finish
```

Do not fake a failure or hard-code an answer merely for the video. If the model succeeds first try, the demo is still valid; verification evidence remains the core point.

### Final Secret Audit

Check:

```bash
git status
git log --oneline
git diff
```

Search repository for likely credentials/secrets.

Ensure:

- `.env` is ignored;
- no key appears in Git history;
- no secret is printed in demo commands/logs.

If a real secret was ever committed, stop and instruct the user to revoke/replace it. Do not rewrite already-pushed history as a casual fix.

### Final Test

Run the full deterministic suite:

```bash
pytest -q
```

Run the Todo tests.

Run at least one final live agent demo if API credentials are locally available.

## Phase 6 Documentation

Update `docs/phases/phase-6.md` **in Simplified Chinese** using the required phase template.

- release readiness status;
- final tests;
- final demo result;
- documentation completed;
- known limitations;
- secret audit result;
- final repository URL;
- target commit message.

## Commit

Recommended:

```text
docs: prepare LocalCoder submission
```

Push.

Then STOP.

---

# Phase Document Template

Each `docs/phases/phase-N.md` must be written in **Simplified Chinese** and use this structure:

```markdown
# Phase N — <阶段名称>

**状态：** 已完成
**日期：** YYYY-MM-DD
**目标提交：** `<commit message>`

## 阶段目标

<本阶段需要完成什么>

## 文件变更

- `path`
- `path`

## 新增或变更接口

- `<name/signature>` — <用途>

## 实现总结

<本阶段实际实现了什么>

## 测试情况

执行命令：

```bash
...
```

测试结果：

```text
...
```

## 设计决策

- <设计决策及原因>

## 与原计划的偏差

- 无。

或：

- <明确说明偏差及原因>

## 已知限制

- <真实限制，不隐藏 bug>

## 下一阶段

<下一阶段将完成什么；不要提前实现>
```

Language rules for phase documents:

- Narrative text and headings: **Simplified Chinese**.
- Technical identifiers, class/function names, commands, file paths, Git commit messages, code blocks, error messages, and raw test output: may remain **English**.
- Do not mechanically translate standard technical identifiers.
- The phase report is also intended to serve as project review/interview notes, so design decisions should explain not only **what** was implemented but **why**.

The phase document must reflect reality. Do not mark a phase COMPLETE if required tests fail or required deliverables are missing.
