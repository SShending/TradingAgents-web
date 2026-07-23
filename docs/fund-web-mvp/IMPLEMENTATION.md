# Implementation Plan and Workflow

## Branch Policy

- Work only on `feat/fund-web-mvp`.
- Do not commit directly to `main`.
- Preserve unrelated user changes in a dirty worktree.
- Sync from official upstream before implementation and again before opening a
  pull request.
- Use a fork only when the developer lacks push access to the official remote.
  See README.md in this directory for exact remote setup.

Suggested commit sequence:

1. `feat: add shared fund instrument classification`
2. `feat: add normalized fund data and metrics`
3. `feat: make analyst graph fund-aware`
4. `feat: add streamed analysis web API`
5. `feat: add fund analysis web workspace`
6. `test: cover fund web workflow`
7. `docs: document fund mode and web UI`

Commits should be reviewable vertical slices. Do not mix broad formatting or
unrelated refactors into this branch.

## Phase 0 - Baseline and Bootstrap

- Create and activate `.venv` with Python 3.12 when available.
- Install `.[dev]` and run the current test suite and Ruff before edits.
- Record any baseline failure; do not attribute it to the feature.
- Inspect the installed yfinance version and its public fund-data surface.
- Add the `web` optional Python extra without importing it from core paths.
- Scaffold `web/` with React, TypeScript, Vite, lint, unit tests, and a committed
  npm lockfile.
- Add `.gitignore` entries for frontend dependency/build/test artifacts.

Exit gate: existing tests and lint have a known baseline, and clean core imports
work with and without the web extra.

## Phase 1 - Instrument Classification

- Add `FUND` to the shared asset type.
- Add a fund subtype enum/model.
- Move asset detection into a shared core module usable by CLI and web.
- Extend identity metadata with currency and any required fund fields.
- Implement detection precedence and override warnings from ARCHITECTURE.md.
- Update state annotations, context rendering, run signatures, tests, and CLI
  messaging.
- Keep crypto normalization/detection behavior unchanged.

Primary test cases: ETF, mutual fund, stock, crypto, explicit override conflict,
identity lookup failure, and normalization.

Exit gate: SPY/ETF metadata resolves to fund, AAPL remains stock, and BTC-USD
remains crypto in isolated tests.

## Phase 2 - Fund Data and Metrics

- Add a yfinance fund adapter returning the normalized snapshot contract.
- Fetch profile, holdings/allocation, price history, and benchmark history by
  independent field group.
- Implement deterministic metrics with pandas and explicit unavailable reasons.
- Enforce the analysis-date boundary for price history.
- Add metadata timestamps and backdated-analysis warnings.
- Add LangChain tools that return concise structured/Markdown data for the fund
  analyst.
- Keep raw provider exceptions behind typed repository dataflow errors.

Use mocked yfinance objects and fixed price fixtures. CI tests must not call the
live Yahoo service.

Exit gate: all metric formulas, missing data, stale/unaligned NAV inputs, and
benchmark alignment are covered by deterministic tests.

## Phase 3 - Fund-Aware Agent Workflow

- Add a fund analyst prompt and bind only fund-valid tools.
- Dispatch the current fundamentals stage by `asset_type` while retaining the
  `fundamentals_report` state key.
- Update instrument context and all downstream prompts that currently branch only
  between stock and generic asset.
- Update CLI/report headings to display Fund Analysis for funds.
- Carry benchmark/run metadata into state or a stable adjacent run model.
- Ensure selected analyst planning and checkpoint signatures remain valid.
- Verify no fund run can call balance-sheet, cash-flow, income-statement, or
  insider-transaction tools solely intended for companies.

Exit gate: mocked stock, fund, and crypto graph-path tests prove the correct tools,
labels, and report content are selected.

## Phase 4 - Reusable Analysis Service and API

- Extract or add a public streamed analysis service; do not duplicate CLI graph
  orchestration in the API.
- Define typed analysis events and stable error codes.
- Add FastAPI app factory, schemas, safe config facade, routes, job manager, SSE,
  reconnect history, cancellation, and Markdown download.
- Run blocking graph work outside the event loop.
- Enforce the active-job limit and terminal job cleanup.
- Bind locally and configure restrictive development CORS.
- Add backend API tests using dependency-injected fake analysis services.

Exit gate: API tests cover resolve, create, busy, progress, reconnect, complete,
failure, cancel, unknown job, validation, safe config, and report download.

## Phase 5 - Browser Workspace

- Implement the responsive workspace defined in ARCHITECTURE.md.
- Add typed API/SSE clients and a reducer/state machine for job events.
- Build configuration controls for instrument, date, benchmark, analysts,
  provider/model, research depth, and language.
- Resolve the instrument before enabling Start; display identity conflicts and
  data warnings without hiding them.
- Build stable agent progress, summary metrics, price/benchmark and drawdown
  charts, holdings/allocation views, report tabs, error/cancel states, and export.
- Sanitize Markdown rendering and keep all secrets backend-only.
- Add accessible names, keyboard focus, contrast, empty states, and tooltips for
  unfamiliar icon actions.

Use CSS variables and a small component vocabulary. Do not introduce a large UI
framework unless it demonstrably removes more complexity than it adds.

Exit gate: component tests pass and no supported desktop/mobile viewport has
overlap, clipped controls, blank charts, or layout shifts during streamed updates.

## Phase 6 - Packaging, Docker, CI, and User Docs

- Add documented backend and frontend development commands.
- Add scripts that start each service with explicit ports and local host binding.
- Extend Docker/Compose only after local development works; preserve the CLI
  entrypoint or add a separate web service rather than replacing it.
- Add frontend lint, test, and build jobs to CI.
- Keep the supported Python 3.11-3.13 matrix green.
- Update top-level README with fund support, web startup, data limitations, and
  research-only disclaimer.
- Add a changelog entry only when behavior is implemented and verified.

Exit gate: a clean install can import core/CLI, the web extra can start the API,
and the frontend production build succeeds from a clean npm install.

## Phase 7 - End-to-End Verification

- Start backend and frontend on unused local ports.
- Run the mocked deterministic end-to-end suite.
- When credentials/network are available, run one live ETF smoke analysis and one
  stock regression smoke analysis. Do not make live tests a CI requirement.
- Use Playwright at desktop and mobile viewports.
- Capture screenshots for configuring, running, completed, missing-data, and
  failure states.
- Inspect browser console/network logs for errors and secret leakage.
- Run full Python tests, Ruff, frontend lint/tests/build, and Playwright.

Exit gate: every acceptance scenario in PRODUCT.md is either verified or listed
as a concrete external limitation in the final handoff.

## Development Commands

Expected commands after implementation:

```bash
source .venv/bin/activate
pytest -q
ruff check .
python -m uvicorn tradingagents.web.app:app --host 127.0.0.1 --port 8000 --reload
```

```bash
cd web
npm ci
npm run dev -- --host 127.0.0.1 --port 5173
npm run lint
npm run test -- --run
npm run build
npx playwright test
```

Script names may be normalized during scaffolding, but the final README and CI
must use the actual commands.

## Definition of Done

- PRODUCT.md acceptance scenarios pass.
- Existing CLI/Python behavior remains compatible.
- No company-statement tool is used in a fund run.
- Metrics and date boundaries are deterministic and tested.
- Web job progress streams and reconnects correctly.
- The UI is complete and usable across required viewports.
- Secrets stay out of browser traffic, logs, repository files, and reports.
- Full backend/frontend quality gates pass from clean installs.
- Documentation describes supported instruments and known limitations accurately.
- The final developer report lists changed files, commands run, live tests omitted,
  and any residual risk.
