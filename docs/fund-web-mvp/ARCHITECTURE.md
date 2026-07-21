# Architecture

## Current Extension Points

The existing repository already provides most of the integration seams:

- `cli.models.AssetType` defines stock and crypto modes.
- `cli.utils.detect_asset_type` classifies crypto by normalized ticker suffix.
- `resolve_instrument_identity` already retrieves Yahoo `quoteType`.
- `AgentState.asset_type` carries mode through the LangGraph workflow.
- analyst selection is configurable while downstream reports use stable state keys.
- both the CLI and graph can consume streamed LangGraph state updates.
- report generation is centralized in `tradingagents/reporting.py`.

The main gaps are a fund domain model, normalized fund tools, asset-aware prompts,
a reusable streamed analysis service, an HTTP job layer, and a browser client.

## Target Shape

```text
Browser (React/Vite)
  | POST jobs / GET state / SSE events
  v
FastAPI application
  |-- configuration facade (safe provider/model options)
  |-- in-memory job manager
  |-- Markdown export
  v
Analysis service (framework-neutral event stream)
  v
TradingAgentsGraph
  |-- market / sentiment / news
  |-- asset-aware fundamentals-or-fund analyst
  |-- researchers / trader / risk / portfolio manager
  v
Dataflows
  |-- existing stock, news, macro, and crypto vendors
  |-- normalized yfinance fund adapter and deterministic metrics
```

The API must consume a public analysis-service abstraction. It must not copy the
CLI's graph setup, checkpoint, memory, or final-state merge logic.

## Proposed Modules

Exact names may change if the existing structure strongly suggests a better fit,
but ownership must remain clear.

```text
tradingagents/
  instruments.py                 # enums, descriptor, shared resolution
  dataflows/
    fund_data.py                  # normalized yfinance fund snapshot
    fund_metrics.py               # deterministic return/risk calculations
  agents/
    analysts/
      fund_analyst.py             # fund-specific prompt/tool binding
    utils/
      fund_data_tools.py          # LangChain tool wrappers
  services/
    analysis_service.py           # reusable stream of typed analysis events
  web/
    app.py                        # FastAPI app factory and static serving
    schemas.py                    # request/response schemas
    jobs.py                       # bounded in-memory job manager
    routes.py                     # API routes and SSE response

web/
  package.json
  package-lock.json
  src/
    api/                          # typed HTTP/SSE client
    components/                   # workspace controls and report views
    features/analysis/            # job state reducer and screens
    styles/                       # tokens and responsive layout
```

The Python package must not import FastAPI during normal core or CLI imports.
Web imports belong behind the optional `web` dependency boundary.

## Instrument Domain Model

Use a single shared resolver for CLI, Python, and HTTP paths.

```text
AssetType: stock | fund | crypto
FundType: etf | mutual_fund | unknown

InstrumentDescriptor
  requested_symbol
  canonical_symbol
  asset_type
  fund_type (nullable)
  quote_type (nullable)
  name (nullable)
  exchange (nullable)
  currency (nullable)
  identity_source
  warnings[]
```

Resolution precedence:

1. Normalize the requested symbol with the existing symbol utility.
2. Detect canonical crypto pairs locally.
3. Resolve Yahoo identity once, including quote type.
4. Map quote type `ETF` to fund/etf and `MUTUALFUND` to fund/mutual_fund.
5. Treat other recognized securities as stock for backward compatibility.
6. Apply an explicit stock/fund/crypto override after detection and add a warning
   if it conflicts with resolved metadata.
7. Fail with a typed not-found error when no usable identity or price data exists.

Do not maintain separate asset-detection implementations in CLI and web code.
Cache successful identity resolution as the current implementation does, but do
not cache transient failures indefinitely.

## Fund Data Contract

Normalize provider output before exposing it to tools, prompts, or the API.
Provider-specific property names must not leak beyond the adapter.

```text
FundSnapshot
  instrument: InstrumentDescriptor
  observed_at
  metadata_as_of (nullable)
  profile:
    category, legal_type, family, inception_date
    total_assets, expense_ratio, yield
    nav, nav_as_of, market_price, market_price_as_of
  holdings:
    top[] {symbol, name, weight}
    sectors[] {name, weight}
    asset_classes[] {name, weight}
    as_of (nullable)
  performance:
    price_series[] {date, adjusted_close}
    benchmark_series[] {date, adjusted_close}
    metrics[] {name, value, unit, window, reason_if_unavailable}
  warnings[]
  source: yfinance
```

All provider access is best-effort by field group. A missing holdings response
must not discard usable profile or performance data.

The implementation must verify the installed yfinance public fund API after
dependencies are installed. Encapsulate any `funds_data` behavior behind the
adapter and mock the adapter in tests; do not couple agents to yfinance objects.

## Metric Semantics

- Build daily returns from adjusted close observations up to and including the
  analysis date.
- Total return is `end / start - 1` over the available requested window.
- Annualized volatility is daily-return standard deviation times `sqrt(252)`.
- Maximum drawdown is the minimum of cumulative value divided by its running
  maximum minus one.
- Correlation uses aligned fund and benchmark daily returns.
- Tracking error is annualized standard deviation of aligned active returns.
- Premium/discount is `(market_price - nav) / nav` only when NAV and market price
  are both available and timestamps are compatible.
- Return `N/A` plus a reason for insufficient history, no overlap, stale inputs,
  invalid NAV, or unavailable data.
- Never let the LLM calculate or silently repair deterministic metrics.

If a Sharpe ratio is included, its risk-free-rate assumption must be explicit in
the output. It is acceptable to defer Sharpe rather than publish an ambiguous
number.

## Graph Integration

Keep `fundamentals_report` as the state key to avoid a migration across every
downstream node and saved report.

At runtime:

- stock: bind existing company fundamentals tools and prompt;
- fund: bind normalized fund profile/holdings/performance tools and fund prompt;
- crypto: skip the fundamentals stage as it does today.

The fundamentals tool node may contain both company and fund tools, but each
analyst invocation must bind only the tools valid for the current asset type.
Company statement tools must be unreachable from a fund prompt.

Update identity context, bull/bear researchers, managers, risk debaters, trader,
portfolio manager, UI labels, and report headings to recognize fund terminology.
Do not use a binary `stock else asset` branch when fund behavior differs.

The benchmark must be carried explicitly in analysis state or run metadata. Fund
runs may use the user's benchmark override; when omitted, retain the existing
market mapping and disclose the selected benchmark.

## Analysis Service and Events

Create a core service that can be used by both the API and, later, the CLI. It
owns graph initialization, checkpoint handling, memory context, streamed state
merge, reporting hooks, and terminal completion/failure events.

Use typed events with this common envelope:

```json
{
  "id": 17,
  "job_id": "uuid",
  "type": "agent.completed",
  "timestamp": "2026-07-21T12:00:00Z",
  "data": {}
}
```

Required event types:

- `analysis.started`
- `agent.started`
- `agent.completed`
- `agent.skipped`
- `report.updated`
- `analysis.completed`
- `analysis.failed`
- `analysis.cancelled`
- `heartbeat`

Event IDs are monotonically increasing per job. The SSE endpoint should honor
`Last-Event-ID` while the job remains in memory so short browser reconnects do
not lose progress.

## HTTP API

All routes live below `/api`.

### Health and Configuration

- `GET /api/health`
- `GET /api/config/options`

Configuration output includes supported asset types, analysts, languages,
providers, models, and whether required backend configuration is present. It
must not include environment values or secret material.

### Instrument Resolution

- `POST /api/instruments/resolve`

Request:

```json
{"symbol":"SPY","asset_type":"auto"}
```

Response: normalized `InstrumentDescriptor` plus safe warnings.

### Analysis Jobs

- `POST /api/analyses`
- `GET /api/analyses/{job_id}`
- `GET /api/analyses/{job_id}/events`
- `POST /api/analyses/{job_id}/cancel`
- `GET /api/analyses/{job_id}/report.md`

Create request fields:

```text
symbol, asset_type, analysis_date, benchmark_symbol
analysts[], research_depth, llm_provider
quick_model, deep_model, output_language
```

Validate dates before starting work. Return HTTP 409 when the configured active
job limit is reached, 404 for an unknown/expired job, and 422 for invalid input.
Map provider/data failures to stable application error codes without returning
stack traces to the browser.

## Job Execution

The graph and provider SDK calls are blocking. Run each job in a worker thread so
the FastAPI event loop remains responsive. Bridge typed events to a bounded
async queue for SSE consumers.

MVP job storage is an in-memory mapping with:

- bounded event history;
- one active job by default;
- terminal result/error state;
- cancellation flag checked between nodes; and
- cleanup by age/count, never while an SSE client is consuming a live job.

Document that server restart loses web job state. The existing on-disk report and
checkpoint features may still operate through the analysis service.

## Frontend Experience

Build the actual workspace as the first screen.

Desktop layout:

```text
Top bar: TradingAgents | resolved instrument | connection/job status
Left rail (300-340px): mode, symbol, date, benchmark, analysts, model settings
Main workspace: summary strip, agent progress, tabbed reports and charts
```

Mobile layout:

- configuration opens as a drawer;
- job status and primary action remain reachable;
- tabs can scroll horizontally without shrinking labels into unreadable text;
- charts use stable aspect ratios and tables become horizontal scroll regions.

Use a quiet operational visual style. Use Lucide icons for actions, compact
segmented controls for mode, checkboxes for analysts, selects for provider/model,
and a clear Start/Cancel command. Avoid marketing content, decorative gradients,
nested cards, oversized headings, and rounded text pills. Card radius must be 8px
or less. Dynamic content must not resize the overall workspace unexpectedly.

Charts must show real normalized data. Recommended first charts are adjusted
price/performance versus benchmark and drawdown. Allocation data should use bars
or a compact table rather than decorative charts when labels are dense.

## Security and Privacy

- Default server host is `127.0.0.1`.
- Restrict CORS to the local Vite origin in development.
- Never serialize process environment, LLM client objects, headers, or callbacks.
- Sanitize report filenames with the existing safe ticker helper.
- Escape report content; Markdown rendering must not allow arbitrary HTML/script.
- Add no endpoint that writes arbitrary filesystem paths.
- Log job IDs, event types, durations, and safe error codes, not prompt secrets or
  authorization material.

## Dependency and Packaging Boundary

Add a Python optional dependency group named `web` for FastAPI and the ASGI
server. Keep base installation and CLI imports unchanged.

The frontend has its own committed `package-lock.json`. Select compatible current
versions during implementation and rely on the lockfile rather than broad global
tool assumptions. Expected packages include React, TypeScript, Vite,
`lucide-react`, a charting library, Vitest, Testing Library, ESLint, and
Playwright for end-to-end verification.

Development runs two processes. A production build may be served by FastAPI from
`web/dist`, but core package imports must still succeed when that directory is
absent.
