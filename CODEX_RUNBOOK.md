# Codex Runbook for LocalCoder

> This document defines the development protocol Codex must follow.
> It is intentionally strict because the project will be reviewed for both implementation quality and understanding of design decisions.

## 1. Authority Order

When instructions conflict, use this order:

1. explicit latest user instruction;
2. `PROJECT_SPEC.md`;
3. `IMPLEMENTATION_PLAN.md`;
4. this runbook;
5. existing implementation conventions.

Never silently modify `PROJECT_SPEC.md` to match code.

## 1.5 Language Requirement

The following output-language policy is mandatory:

- All phase documents `docs/phases/phase-1.md` through `docs/phases/phase-6.md` must be written in **Simplified Chinese**.
- The completion summary returned to the user after every phase must be written in **Simplified Chinese**.
- The final project completion/release report after Phase 6 must be written in **Simplified Chinese**.
- The submission `README.txt` must be written in **Simplified Chinese**.
- The repository `README.md` should be primarily in **Simplified Chinese**, retaining English technical terms when clearer.
- Technical identifiers, code symbols, class/function names, API names, CLI commands, file paths, Git commit messages, code blocks, error messages, and raw test output may remain in **English**.
- Do not translate code identifiers merely for stylistic consistency.

This rule applies even though the technical specification and execution prompts are written in English.

## 2. Core Rule: One Phase Per User Instruction

Codex must never execute more than one implementation phase per explicit user instruction.

When a phase is complete:

1. run required tests;
2. fix phase-related failures;
3. update `docs/phases/phase-N.md`;
4. inspect `git diff` and `git status`;
5. perform a basic secret check;
6. commit;
7. push;
8. report the result to the user;
9. **STOP**.

Do not begin the next phase, even when it looks easy.

## 3. Bootstrap — Create the GitHub Repository

Bootstrap is not one of the six implementation phases.

### 3.1 Preflight

Before modifying anything:

```bash
pwd
git status
git remote -v
gh --version
gh auth status
```

Adapt commands to the current OS/shell where needed.

### 3.2 Existing Repository Handling

If the current directory is already the intended LocalCoder Git repository:

- do not create a duplicate;
- inspect its remote;
- reuse it only if it is clearly the intended project.

If an unrelated repository is open, STOP and tell the user rather than creating LocalCoder inside it.

### 3.3 Authentication Rule

Use the user's already-authenticated Git/GitHub CLI session.

If `gh auth status` fails:

- STOP repository creation;
- tell the user to run `gh auth login` locally;
- do not ask the user to paste a GitHub token into source code, chat prompts, shell history, or repository files;
- resume only after authentication succeeds.

If `gh` is not installed, report that prerequisite. Do not embed credentials as a workaround.

### 3.4 Repository Name and Visibility

Default:

```text
Repository name: localcoder
Visibility: public
Default branch: main
```

If a repository with that name already exists under the user's account, STOP and ask for a new name rather than deleting/replacing anything.

### 3.5 Bootstrap Files

The user should place these files in the project root before or during bootstrap:

```text
PROJECT_SPEC.md
IMPLEMENTATION_PLAN.md
CODEX_RUNBOOK.md
```

Do not rewrite them unless explicitly instructed.

Create a minimal `.gitignore` immediately that covers at least:

```text
.env
.venv/
venv/
__pycache__/
.pytest_cache/
*.pyc
```

### 3.6 Initialize and Commit

If needed:

```bash
git init -b main
git add PROJECT_SPEC.md IMPLEMENTATION_PLAN.md CODEX_RUNBOOK.md .gitignore
git commit -m "docs: add frozen project specification and workflow"
```

Then create the public GitHub repository using the authenticated GitHub CLI, for example:

```bash
gh repo create localcoder --public --source=. --remote=origin --push
```

Verify:

```bash
git remote -v
git status
git log --oneline -n 3
```

### 3.7 Bootstrap Stop Gate

After repository creation and initial push:

- report the public repository URL;
- report the initial commit;
- report whether the working tree is clean;
- **STOP**.

Do not start Phase 1 until the user explicitly says to execute Phase 1.

## 4. Before Every Phase

Run/read:

```text
PROJECT_SPEC.md
IMPLEMENTATION_PLAN.md
CODEX_RUNBOOK.md
docs/phases/phase-(N-1).md  # when N > 1
```

Then inspect:

```bash
git status
git log --oneline -n 5
```

Requirements:

- working tree should be clean unless the user explicitly explains pre-existing changes;
- previous phase must be documented COMPLETE;
- previous phase commit should be pushed.

If there are unexplained user changes, do not overwrite them. Report the issue.

## 5. Implementation Style

### 5.1 TDD

For deterministic local functionality:

1. write a focused failing test;
2. run it and confirm the intended failure;
3. implement the smallest reasonable change;
4. run the focused test;
5. run related tests;
6. run the full deterministic suite before phase completion.

Not every provider-mocking line needs ritualized micro-tests, but externally visible deterministic behavior should be test-first where practical.

### 5.2 Simplicity

Prefer:

- small focused modules;
- explicit data structures;
- standard library;
- straightforward interfaces.

Avoid:

- deep inheritance;
- unnecessary factories;
- framework-like internal abstractions;
- speculative extensibility.

### 5.3 No Scope Creep

If a useful idea is outside the current phase:

- mention it under "Known Limitations" or as a possible future improvement;
- do not implement it.

Never implement a later phase early merely because it would be convenient.

## 6. Testing and Completion Gate

A phase cannot be marked COMPLETE when:

- required tests fail;
- required deliverables are missing;
- secrets are present;
- code is knowingly broken;
- documentation claims behavior that does not exist.

If blocked:

- do not mark the phase COMPLETE;
- do not create the normal phase-completion commit;
- report the blocker and current test state;
- STOP.

## 7. Phase Documentation

Before the phase commit, update:

```text
docs/phases/phase-N.md
```

using the **Simplified-Chinese** template in `IMPLEMENTATION_PLAN.md`.

The document must record actual implementation, not intended implementation.

Do not include a self-referential commit hash inside the same commit. Record the target commit message in the document; report the resulting hash to the user after committing.

## 8. Commit Policy

One primary phase-completion commit is preferred.

Recommended messages are defined in `IMPLEMENTATION_PLAN.md`.

Before committing:

```bash
git status --short
git diff --check
git diff
pytest -q
```

Use additional focused commands as required by that phase.

Stage only intended project files.

Never use:

```bash
git add .
```

blindly without first inspecting status.

After commit:

```bash
git status
git log --oneline -n 3
git push
```

Do not amend or rewrite already-pushed commits unless the user explicitly directs it and it is consistent with assignment rules.

## 9. Secret Safety

Never commit or print:

- `LLM_API_KEY`;
- GitHub tokens;
- Authorization headers;
- full environment dumps;
- private credentials.

Before each phase commit, inspect likely secret-bearing files and repository status.

Use `.env.example` only with placeholders.

If a real secret appears in a file:

- remove it from the working tree;
- do not proceed until safe.

If a real secret has already been pushed:

- stop;
- tell the user to revoke/rotate it immediately;
- do not casually rewrite pushed history.

## 10. GitHub Push Failure

If code and tests are complete but `git push` fails due to auth/network:

- keep the local commit;
- update the phase document truthfully only if the phase itself is complete;
- report that push is the only blocker;
- STOP;
- do not proceed to the next phase.

The next phase must not start until the previous phase is pushed unless the user explicitly overrides the protocol.

## 11. Required Phase Completion Report

After a successful phase push, answer the user in **Simplified Chinese** using this structure:

```text
Phase N 已完成。

已实现：
- ...

测试：
- 命令：...
- 结果：...

阶段文档：
- docs/phases/phase-N.md

提交：
- <hash> <message>

GitHub：
- <repository URL>

工作区状态：
- clean

下一步：
- Phase N+1 尚未开始。
```

Technical identifiers, commands, commit messages, paths, code, errors, and raw test output may remain in English.

Then STOP.

## 12. Final Phase Rule

Phase 6 is stabilization/documentation only.

Do not add a new architecture or major feature in Phase 6.

After Phase 6, report the final repository URL, tests, demo readiness, and known limitations in **Simplified Chinese**, then STOP.
