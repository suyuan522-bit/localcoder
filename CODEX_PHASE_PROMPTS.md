# Codex Sequential Prompts for LocalCoder

Use these prompts in order. Do not paste all of them at once.

---

## Prompt 0 — Bootstrap GitHub Repository

```text
You are working on the LocalCoder project.

Before doing anything else, read these files completely:
- PROJECT_SPEC.md
- IMPLEMENTATION_PLAN.md
- CODEX_RUNBOOK.md

Treat PROJECT_SPEC.md as frozen and authoritative. Do not modify it.

Now perform only the Bootstrap procedure from CODEX_RUNBOOK.md:
1. inspect the current directory and Git state;
2. verify GitHub CLI availability and authentication;
3. initialize the repository if needed;
4. create the initial .gitignore required by the runbook;
5. commit the frozen project documents;
6. create a new PUBLIC GitHub repository named `localcoder` with default branch `main`;
7. add/preserve `origin` and push the initial commit;
8. verify the remote, log, and working tree.

Safety:
- Never ask me to paste a GitHub token into the repository or source code.
- If GitHub CLI is not authenticated, STOP and tell me to run `gh auth login`.
- If the current directory is an unrelated Git repository, STOP instead of nesting LocalCoder inside it.
- If `localcoder` already exists on my GitHub account, STOP and ask me to choose another repository name.
- Do not start Phase 1.

At the end, report **in Simplified Chinese**:
- GitHub repository URL
- initial commit hash/message
- working tree status

Then STOP.
```

---

## Prompt 1 — Execute Phase 1 Only

```text
Read PROJECT_SPEC.md, IMPLEMENTATION_PLAN.md, and CODEX_RUNBOOK.md again.

Execute ONLY:
Phase 1 — Local Tool Foundation.

Follow the phase scope exactly. Do not implement LLMClient, AgentCore, ContextManager, Trace, Git diff, or demo functionality early.

Requirements:
- all phase documentation and your phase-completion report must be written in Simplified Chinese; technical identifiers, commands, file paths, Git commit messages, code, errors, and raw test output may remain in English;
- use TDD for deterministic behavior where practical;
- implement every Phase 1 deliverable;
- run focused tests during development;
- run `pytest -q` before completion;
- update `docs/phases/phase-1.md` in Simplified Chinese using the required template;
- inspect git diff/status and check for secrets;
- commit with the planned Phase 1 commit message;
- push to origin.

If any required Phase 1 test fails or a required deliverable is missing, do not mark the phase COMPLETE and do not move on.

After a successful push, report the phase summary, test results, phase document, commit hash, repository URL, and working tree status in Simplified Chinese.

DO NOT START PHASE 2. STOP after Phase 1.
```

---

## Prompt 2 — Execute Phase 2 Only

```text
Read PROJECT_SPEC.md, IMPLEMENTATION_PLAN.md, CODEX_RUNBOOK.md, and docs/phases/phase-1.md.

Verify Phase 1 is COMPLETE, pushed, and the working tree is clean.

Execute ONLY:
Phase 2 — LLM Client and Native Tool Calling.

Do not implement AgentCore or any Phase 3+ feature.

Requirements:
- all phase documentation and your phase-completion report must be written in Simplified Chinese; technical identifiers, commands, file paths, Git commit messages, code, errors, and raw test output may remain in English;
- load LLM_API_KEY, LLM_BASE_URL, LLM_MODEL safely;
- implement OpenAI-compatible native tool calling;
- normalize tool call responses for later AgentCore use;
- use mocks/fakes so default pytest requires no paid API call;
- implement bounded transient retry;
- never log or commit secrets;
- run all Phase 2 tests plus `pytest -q`;
- update `docs/phases/phase-2.md` in Simplified Chinese;
- inspect diff/status and secret safety;
- commit and push.

After a successful push, report the required completion summary in Simplified Chinese.

DO NOT START PHASE 3. STOP after Phase 2.
```

---

## Prompt 3 — Execute Phase 3 Only

```text
Read PROJECT_SPEC.md, IMPLEMENTATION_PLAN.md, CODEX_RUNBOOK.md, and docs/phases/phase-2.md.

Verify previous phases are COMPLETE/pushed and the working tree is clean.

Execute ONLY:
Phase 3 — AgentCore and Autonomous Agent Loop.

Required:
- all phase documentation and your phase-completion report must be written in Simplified Chinese; technical identifiers, commands, file paths, Git commit messages, code, errors, and raw test output may remain in English;
- AgentState;
- AgentCore multi-step loop;
- native tool-call dispatch through ToolRegistry;
- feed ToolResult observations back to the model;
- explicit finish tool/protocol;
- MAX_STEPS;
- clean error/interrupt handling;
- concise system prompt;
- CLI entry point;
- deterministic FakeLLMClient tests.

Do not implement ContextManager, Trace, Git diff, or Phase 4+ functionality early.

Run focused tests and `pytest -q`.
Update `docs/phases/phase-3.md` in Simplified Chinese.
Inspect diff/status/secrets.
Commit and push.

After the successful push, report completion in Simplified Chinese.

DO NOT START PHASE 4. STOP after Phase 3.
```

---

## Prompt 4 — Execute Phase 4 Only

```text
Read PROJECT_SPEC.md, IMPLEMENTATION_PLAN.md, CODEX_RUNBOOK.md, and docs/phases/phase-3.md.

Verify previous phases are COMPLETE/pushed and working tree is clean.

Execute ONLY:
Phase 4 — Context, Verification and Trace.

Required:
- all phase documentation and your phase-completion report must be written in Simplified Chinese; technical identifiers, commands, file paths, Git commit messages, code, errors, and raw test output may remain in English;
- ContextManager with permanent system/task messages;
- bounded dynamic history;
- tool-output truncation;
- verification run tracking;
- last edit tracking;
- verification-aware finish behavior;
- TraceLogger with EXPLORE / EDIT / VERIFY / DONE views;
- deterministic test showing edit -> failed verification -> fix -> successful verification -> finish.

Do not add Git diff or Phase 5 demo integration early.

Run focused tests and `pytest -q`.
Update `docs/phases/phase-4.md` in Simplified Chinese.
Inspect diff/status/secrets.
Commit and push.

After successful push, report completion in Simplified Chinese.

DO NOT START PHASE 5. STOP after Phase 4.
```

---

## Prompt 5 — Execute Phase 5 Only

```text
Read PROJECT_SPEC.md, IMPLEMENTATION_PLAN.md, CODEX_RUNBOOK.md, and docs/phases/phase-4.md.

Verify previous phases are COMPLETE/pushed and working tree is clean.

Execute ONLY:
Phase 5 — Git Diff and End-to-End Integration.

Required:
- all phase documentation and your phase-completion report must be written in Simplified Chinese; technical identifiers, commands, file paths, Git commit messages, code, errors, and raw test output may remain in English;
- implement get_diff scoped to the workspace;
- graceful non-Git fallback;
- final changed-files summary;
- create/complete the examples/todo_demo fixture/project;
- run LocalCoder on the recommended Todo delete task using the configured real model when credentials are locally available;
- keep deterministic unit tests independent of the real API;
- run the full pytest suite and Todo demo tests;
- fix only scope-relevant instability;
- do not add new feature categories.

Update `docs/phases/phase-5.md` in Simplified Chinese with actual end-to-end observations.
Inspect diff/status/secrets.
Commit and push.

After successful push, report completion in Simplified Chinese.

DO NOT START PHASE 6. STOP after Phase 5.
```

---

## Prompt 6 — Execute Phase 6 Only

```text
Read PROJECT_SPEC.md, IMPLEMENTATION_PLAN.md, CODEX_RUNBOOK.md, and docs/phases/phase-5.md.

Verify previous phases are COMPLETE/pushed and working tree is clean.

Execute ONLY:
Phase 6 — Documentation, Demo Polish and Release Readiness.

This phase is stabilization/documentation only. Do not add a new architecture or major feature.

Required:
- all phase documentation and your phase-completion report must be written in Simplified Chinese; technical identifiers, commands, file paths, Git commit messages, code, errors, and raw test output may remain in English;
- complete README.md primarily in Simplified Chinese, retaining standard English technical terms where clearer;
- create submission README.txt in Simplified Chinese within 1000 Chinese characters;
- finalize .env.example, .gitignore, requirements.txt, LICENSE;
- verify Todo demo instructions;
- run full deterministic tests;
- run Todo demo tests;
- perform a final live LocalCoder demo when local credentials are available;
- inspect git status/log/diff;
- check repository for likely secrets;
- document limitations honestly;
- update docs/phases/phase-6.md;
- commit and push.

If a real secret is discovered in pushed history, STOP and tell me to revoke/rotate it; do not casually rewrite pushed history.

After successful push, report **in Simplified Chinese**:
- final GitHub URL;
- tests;
- demo readiness;
- known limitations;
- final commit;
- working tree status.

Then STOP. The project is complete.
```
