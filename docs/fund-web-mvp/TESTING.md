# Test and Release Plan

## Test Principles

- CI must be deterministic and independent of live Yahoo/LLM services.
- Fund calculations are ordinary Python logic and require exact expected values.
- Agent routing is verified with fakes that record bound/called tools.
- API tests inject a fake streamed analysis service.
- Live services are manual smoke tests, never substitutes for isolated coverage.
- Existing stock and crypto tests are regression gates, not optional checks.

## Backend Unit Tests

### Instrument Resolution

- canonical normalization is shared with current dataflows;
- crypto detection wins before Yahoo quote-type mapping;
- `ETF` maps to fund/etf;
- `MUTUALFUND` maps to fund/mutual_fund;
- equity maps to stock;
- explicit override is honored with a warning on conflict;
- missing quote type fails open only when valid price data confirms the symbol;
- transient identity lookup failures are not cached permanently.

### Fund Adapter

- complete ETF payload normalization;
- partial mutual-fund payload normalization;
- holdings, sector, and asset-class weights normalize to consistent decimal units;
- missing fields stay `None`/unavailable rather than zero;
- independent field-group failures retain other usable data;
- current-only metadata on a historical date adds a warning;
- provider error text and secrets do not escape the adapter.

### Metrics

Use small checked-in CSV/JSON fixtures with known values.

- each return window;
- insufficient-history reason;
- annualized volatility;
- maximum drawdown;
- date boundary excludes future observations;
- benchmark date alignment;
- correlation and tracking error;
- zero/invalid NAV rejects premium/discount;
- stale or mismatched NAV/market timestamps reject premium/discount;
- missing benchmark returns fund-only metrics with warnings;
- NaN, duplicate dates, timezone differences, and unsorted input.

### Graph and Prompts

- fund mode binds fund tools only;
- stock mode binds company fundamentals tools only;
- crypto mode skips the stage as before;
- fund prompt contains fund context and no company revenue/EPS/debt instructions;
- downstream researchers/risk/trader/manager use fund terminology;
- report state remains under `fundamentals_report`;
- checkpoint signature changes across asset types;
- selected analysts and report headings remain correct.

## API Tests

Use FastAPI's in-process test client and injected fakes.

- health and safe configuration options;
- resolve success, conflict warning, invalid symbol, and unavailable provider;
- create validation and configured-provider failure;
- one-active-job conflict response;
- ordered SSE events and heartbeat format;
- `Last-Event-ID` replay without duplicates;
- completed job state and Markdown export;
- structured analysis failure without stack trace;
- cancellation requested, cancelled terminal event, and already-terminal behavior;
- unknown and expired job IDs;
- report path sanitization;
- local CORS allowlist;
- response/log secret-redaction assertions.

## Frontend Tests

Use Vitest and Testing Library for:

- configuration validation and resolve-before-start behavior;
- asset-type segmented control and resolved identity state;
- provider/model option dependencies;
- job reducer handling every event type and duplicate event IDs;
- reconnect indicator and resumed event stream;
- agent status transitions without layout-dependent logic;
- fund metric value, unavailable reason, and warning rendering;
- stock/fund/crypto report heading selection;
- loading, empty, busy, failure, cancel, and completed states;
- export action;
- Markdown sanitization;
- keyboard operation and accessible names for icon controls.

## End-to-End Tests

Run Playwright against a fake deterministic backend mode.

Required flows:

1. Resolve SPY, start a fund analysis, receive streamed events, inspect all tabs,
   and download the report.
2. Render missing holdings and benchmark warnings without broken layout.
3. Cancel a running analysis and return controls to a usable state.
4. Render a provider failure and retry with preserved form selections.
5. Confirm a stock resolution does not show fund-only panels.

Required viewports:

- desktop: 1440x900;
- compact laptop: 1024x768;
- mobile: 390x844;
- narrow mobile: 360x800.

For each viewport, capture screenshots of configuration, running, and completed
states. Verify no overlap, clipped text, horizontal page overflow, blank chart,
or dynamic panel resizing. Tables may scroll within their own container.

## Manual Live Smoke Tests

Run only when API credentials and network access are intentionally available.

- ETF: SPY or another Yahoo-resolved ETF;
- mutual fund: one Yahoo-resolved mutual-fund symbol confirmed at test time;
- stock regression: AAPL;
- optional crypto regression: BTC-USD.

For each run, record:

- resolved identity/type;
- analysis date and benchmark;
- unavailable/warning fields;
- provider/model;
- completion or failure;
- evidence that fund runs did not call company statement tools.

Do not place API keys, full authorization headers, or sensitive prompt content in
the smoke-test record.

## Quality Gates

Backend:

```bash
pytest -q
ruff check .
```

Frontend:

```bash
cd web
npm ci
npm run lint
npm run test -- --run
npm run build
npx playwright test
```

Clean-install smoke:

```bash
python3 -m venv /tmp/tradingagents-clean
source /tmp/tradingagents-clean/bin/activate
python -m pip install .
python -c "import tradingagents, cli.main"
python -m pip install ".[web]"
python -c "from tradingagents.web.app import app"
```

Use a temporary environment outside the repository and remove it after the check.

## Release Checklist

- [ ] All PRODUCT.md acceptance scenarios addressed.
- [ ] Python tests pass on supported versions in CI.
- [ ] Strict Ruff passes for the full repository.
- [ ] Frontend lint, unit tests, and production build pass.
- [ ] Playwright passes at all required viewports.
- [ ] Core install works without web dependencies.
- [ ] Web extra and local server startup work from a clean install.
- [ ] No secret appears in browser traffic, console, logs, screenshots, or reports.
- [ ] README and changelog accurately state scope and limitations.
- [ ] Docker/Compose changes preserve the CLI workflow.
- [ ] Live tests omitted due to credentials/network are named explicitly.
- [ ] Pull request targets upstream `main` from `feat/fund-web-mvp`.
