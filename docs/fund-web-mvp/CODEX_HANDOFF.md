# Codex Handoff

This file is the task entry point for an implementation Codex session.

## Assignment

Implement the Fund Mode and Web UI MVP end to end on the existing
`feat/fund-web-mvp` branch.

Before changing code, read every file in `docs/fund-web-mvp/` in the order listed
by its README. Treat PRODUCT.md acceptance scenarios and ARCHITECTURE.md data/date
semantics as requirements, not suggestions.

## Non-Negotiable Constraints

- Preserve existing stock, crypto, CLI, and Python package behavior.
- Do not work directly on `main`.
- Do not overwrite unrelated changes in a dirty worktree.
- Do not add mainland China off-exchange fund providers in this MVP.
- Do not add authentication, a durable database/queue, or trade execution.
- Do not expose API keys to the frontend or logs.
- Do not let the LLM compute fund metrics or invent missing provider fields.
- Do not describe current fund metadata as historical point-in-time data.
- Do not duplicate graph orchestration inside HTTP routes.
- Keep web dependencies optional so a base install still imports core and CLI.
- Use `apply_patch` for manual file edits and existing repository patterns first.

## Execution Protocol

1. Confirm branch, remotes, worktree status, Python/Node versions, and any existing
   user changes.
2. Create a task plan matching the phases in IMPLEMENTATION.md and update it as
   work completes.
3. Establish the existing tests/Ruff baseline before production edits.
4. Implement in ordered vertical slices: classification, fund data/metrics, graph,
   service/API, frontend, packaging/docs.
5. Add focused tests with each slice; do not postpone all testing to the end.
6. Start the local backend/frontend after implementation and provide their URLs.
7. Verify with Playwright screenshots at every viewport in TESTING.md.
8. Run all backend/frontend quality gates and clean-install smoke checks.
9. Report files changed, behavior delivered, commands/results, omitted live tests,
   and residual risks.

Do not stop after scaffolding or a backend-only implementation. The requested
deliverable is a usable fund-aware web workspace with verification.

## First Commands

```bash
git status --short --branch
git remote -v
python3 --version
node --version
npm --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
pytest -q
ruff check .
```

If dependency installation fails because network access is restricted, request
the required approval rather than replacing dependencies with unplanned local
implementations.

After the baseline, inspect the installed yfinance public API and then add the
optional web dependencies and frontend lockfile as described in ARCHITECTURE.md.

## Required Deliverables

- shared stock/fund/crypto instrument resolution;
- normalized Yahoo fund snapshot and deterministic metrics;
- fund-aware agent/tool/prompt/report behavior;
- reusable streamed analysis service;
- safe local FastAPI job/SSE/export API;
- responsive React/Vite analysis workspace;
- backend, frontend, API, and Playwright tests;
- optional packaging, CI, Docker/Compose where appropriate, README, and changelog;
- final verification report against PRODUCT.md acceptance scenarios.

## Ready-to-Paste User Prompt

Use this short prompt to start the implementation session:

```text
Implement the first Fund Mode and Web UI release described in
docs/fund-web-mvp/README.md. Read all linked documents before editing, work on
feat/fund-web-mvp, follow the implementation phases and acceptance criteria, and
complete the work end to end including tests, local servers, and Playwright
desktop/mobile verification. Preserve existing CLI, stock, and crypto behavior.
```

## Completion Report Format

The final response should state:

1. what users can now do;
2. key architecture and compatibility choices;
3. test/lint/build/Playwright results;
4. local URLs and exact startup commands;
5. live integrations not tested and why;
6. remaining known limitations, especially Yahoo field coverage and latest-only
   fund metadata.
