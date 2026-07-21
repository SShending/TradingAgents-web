# Fund Mode and Web UI MVP

- Status: implementation-ready specification
- Prepared: 2026-07-21
- Working branch: `feat/fund-web-mvp`

Product implementation has not started. This directory is the approved planning
and handoff package for the implementation session.

## Objective

Add first-class fund analysis to TradingAgents and expose the existing stock,
fund, and crypto workflows through a local browser application.

The first release supports instruments that Yahoo Finance can resolve as an ETF
or mutual fund. Mainland China off-exchange public funds that Yahoo Finance does
not cover are deliberately deferred to a later data-provider integration.

## Fixed MVP Decisions

- Preserve the current CLI and Python package behavior.
- Add `fund` as an asset type, with `etf`, `mutual_fund`, and `unknown` subtypes.
- Resolve fund type from Yahoo `quoteType`, with an explicit user override.
- Reuse the existing `fundamentals_report` state slot, but make its analyst and
  label asset-aware. This limits graph and report migration risk.
- Use yfinance as the only fund data provider in this release.
- Build a local single-user web app with FastAPI, React, TypeScript, and Vite.
- Stream analysis progress to the browser with Server-Sent Events (SSE).
- Keep API keys on the backend. Never send or store provider secrets in the
  browser.
- Do not add authentication, multi-user scheduling, a database, or real order
  execution in the MVP.

## Document Map

Read these files in order before implementation:

1. [PRODUCT.md](PRODUCT.md) - user flows, scope, requirements, and acceptance.
2. [ARCHITECTURE.md](ARCHITECTURE.md) - domain model, data semantics, API, SSE,
   backend services, and frontend shape.
3. [IMPLEMENTATION.md](IMPLEMENTATION.md) - branch workflow and ordered tasks.
4. [TESTING.md](TESTING.md) - automated and manual verification gates.
5. [CODEX_HANDOFF.md](CODEX_HANDOFF.md) - ready-to-run Codex assignment.

If documents conflict, the priority is PRODUCT, ARCHITECTURE, IMPLEMENTATION,
TESTING, then CODEX_HANDOFF.

## Repository and Fork Workflow

The current clone has `origin` set to the official repository:

```text
https://github.com/TauricResearch/TradingAgents.git
```

Local development does not require a fork. Work in the current clone on the
existing `feat/fund-web-mvp` branch and leave `main` untouched.

If the developer has write access to the official repository:

```bash
git push -u origin feat/fund-web-mvp
```

If the developer does not have write access, create a GitHub fork before the
first push, then use the conventional remote names:

```bash
git remote rename origin upstream
git remote add origin git@github.com:<YOUR_ACCOUNT>/TradingAgents.git
git fetch upstream
git push -u origin feat/fund-web-mvp
```

Open the pull request from the fork branch to
`TauricResearch/TradingAgents:main`. A fork is a publication and collaboration
mechanism, not a requirement for editing files locally.

## Development Prerequisites

- Python 3.10-3.13; this machine currently provides `python3` 3.12.
- Node.js 20 or newer; this machine currently provides Node 22 and npm 10.
- One configured LLM provider key, or a reachable local Ollama/OpenAI-compatible
  endpoint, for manual end-to-end analysis.
- Network access for live Yahoo Finance and LLM smoke tests.

The current environment has not installed the Python package dependencies yet.
Create an isolated environment before implementation:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

The `web` optional extra does not exist yet; adding it is an implementation task.
After Phase 0 creates it, install the complete development environment with:

```bash
python -m pip install -e ".[dev,web]"
```

Never commit `.env`, API keys, generated reports, `node_modules`, or frontend
build output.

## Start Condition

Implementation may begin when:

- all documents in this directory have been read;
- the working branch is `feat/fund-web-mvp`;
- unrelated user changes have been identified and preserved;
- Python and frontend dependencies can be installed; and
- the implementer accepts the MVP non-goals in PRODUCT.md.
