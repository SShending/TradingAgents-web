# Product Requirements

## Problem

TradingAgents can price and technically analyze listed ETFs such as SPY today,
but every non-crypto symbol is classified as a stock. The fundamentals analyst
then asks for company statements and downstream prompts discuss company revenue,
competitive position, and balance-sheet quality. Those concepts are misleading
for funds.

The project also has a terminal UI but no browser workspace. Long-running agent
analysis would be easier to configure and inspect through a browser with live
progress, structured report sections, charts, and export.

## Goals

- Correctly distinguish stocks, funds, and crypto assets.
- Give ETFs and mutual funds a fund-specific research report.
- Preserve existing stock and crypto behavior.
- Provide a usable local browser interface for starting and following analyses.
- Make unavailable fund fields explicit instead of asking the LLM to infer them.
- Keep backdated analysis honest about current-only metadata.
- Keep the core Python package usable without web dependencies.

## Non-Goals

- Mainland China off-exchange public funds unavailable from Yahoo Finance.
- Brokerage integration, order placement, portfolio accounting, or rebalancing.
- User accounts, authentication, cloud deployment, or multi-tenant isolation.
- Durable job queues or recovery of web jobs after process restart.
- Point-in-time historical fund holdings, fees, AUM, or manager history.
- Fund discovery, screening across the full market, or portfolio optimization.
- Pixel-identical reproduction of the Rich terminal interface.

## Primary User Flow

1. Open the local web application directly into the analysis workspace.
2. Enter a symbol and choose Auto, Stock, Fund, or Crypto.
3. Resolve and confirm the instrument identity before running an analysis.
4. Choose the analysis date, benchmark, analysts, LLM provider/model, research
   depth, and output language.
5. Start the analysis and see agent progress and partial reports as they arrive.
6. Inspect overview metrics, price and drawdown charts, analyst reports, debates,
   risk discussion, and the final decision.
7. Export the completed Markdown report.

## Functional Requirements

### FR-1 Instrument Resolution

- Accept the same ticker character set and normalization rules as the CLI.
- Support `auto`, `stock`, `fund`, and `crypto` selection in the web UI/API.
- Detect crypto from the canonical symbol before consulting quote metadata.
- Detect `ETF` and `MUTUALFUND` Yahoo quote types as `fund`.
- Respect an explicit user asset-type override, but return a warning when it
  conflicts with resolved metadata.
- Return canonical symbol, display name, quote type, fund subtype, exchange,
  currency, and warnings to the UI.
- Fail clearly for an unknown or unavailable symbol.

### FR-2 Fund Data

- Retrieve fund profile fields when available: category, legal type, family,
  inception date, AUM, expense ratio, yield, NAV, market price, exchange, and
  currency.
- Retrieve top holdings, sector weights, and asset-class weights when the
  installed yfinance version/provider response exposes them.
- Compute price-based performance without LLM involvement.
- Treat missing provider fields as unavailable, not zero.
- Include source and observation timestamps in normalized data.
- Label latest-only metadata explicitly on backdated analyses.

### FR-3 Fund Metrics

- Provide total return for available 1-month, 3-month, 6-month, 1-year, and
  3-year windows ending on the analysis date.
- Provide annualized volatility and maximum drawdown when sufficient data exists.
- Provide benchmark-relative return and correlation when a benchmark is usable.
- For ETFs, provide tracking error and premium/discount only when the inputs are
  available and temporally compatible.
- Do not call a market price "NAV" unless the provider identifies it as NAV.
- Render `N/A` with a reason when a metric cannot be computed.

### FR-4 Asset-Aware Analysis

- A fund run must not request company balance sheets, income statements, cash
  flow statements, EPS, revenue growth, or debt ratios.
- The fund analyst must use only normalized fund profile, holdings, performance,
  market, and news tools.
- Bull, bear, risk, trader, and portfolio prompts must refer to a fund and use
  fund-relevant evidence.
- The existing `fundamentals_report` state/output key remains for compatibility,
  while UI and saved-report headings display "Fund Analysis" for fund runs.
- Stock and crypto prompts and tool selection must remain behaviorally compatible.

### FR-5 Analysis Jobs

- Starting an analysis returns a job ID immediately.
- Only one job may actively consume the local process by default; a second start
  returns a clear busy response. This limit may be configurable later.
- Job state includes queued, running, completed, failed, and cancelling/cancelled.
- Cancellation is best-effort and takes effect between graph nodes; an in-flight
  provider request may finish first.
- Failure events include a stable error code and a safe user-facing message.

### FR-6 Live Web Workspace

- The initial route is the working analysis screen, not a marketing page.
- Show a restrained configuration sidebar and a dense report workspace.
- Show stable agent statuses: pending, running, completed, failed, and skipped.
- Stream report updates without page refresh.
- Provide tabs for Overview, Analyst Reports, Debate and Risk, and Final Decision.
- Overview includes identity, key metrics, price/performance, drawdown, holdings,
  sector allocation, and benchmark comparison when available.
- Preserve layout dimensions while content and statuses update.
- Support desktop and mobile without overlapping or clipped text.
- Include loading, empty, missing-data, connection-loss, failure, cancellation,
  and completed states.

### FR-7 Configuration and Secrets

- The browser may select from backend-approved provider/model options.
- Provider secrets are read only from backend environment configuration.
- The API reports whether required provider configuration is available without
  exposing secret values.
- The browser must never send, receive, persist, or log an LLM API key.

### FR-8 Results and Export

- A completed analysis remains available in memory until server restart.
- The browser can download a UTF-8 Markdown report.
- Saved reports keep the current report-tree format wherever compatible.
- Reports include symbol, resolved identity, asset type/subtype, analysis date,
  benchmark, data warnings, and generation time.

## Non-Functional Requirements

### NFR-1 Compatibility

- Existing public `TradingAgentsGraph.propagate()` calls continue to work.
- Existing CLI commands and current tests remain green.
- Web dependencies are isolated in an optional Python extra.

### NFR-2 Correctness

- Deterministic metrics are computed in Python, not by an LLM.
- Price data used for a historical analysis must not extend beyond the analysis
  date.
- Current-only metadata must never be described as point-in-time historical data.

### NFR-3 Security

- Bind to `127.0.0.1` by default.
- Redact tokens, authorization headers, and API keys from logs and errors.
- Validate symbols, dates, enum values, report identifiers, and download paths.
- Do not enable permissive cross-origin access outside the configured local
  frontend origin.

### NFR-4 Quality

- New Python code passes the repository's strict Ruff configuration.
- Backend domain and API behavior have isolated tests without live network or LLM
  calls.
- Frontend behavior has component tests and a production build gate.
- The main workflow has Playwright coverage at desktop and mobile viewports.

## MVP Acceptance Scenarios

1. Resolving `SPY` in Auto mode returns asset type `fund` and subtype `etf`.
2. A mocked SPY analysis produces fund metrics and a Fund Analysis report without
   company financial-statement tool calls.
3. A mocked Yahoo mutual-fund quote type returns subtype `mutual_fund` and handles
   absent intraday/volume fields without failure.
4. `AAPL` remains a stock and follows the existing company fundamentals path.
5. `BTC-USD` remains crypto and does not run company or fund fundamentals tools.
6. A backdated fund run uses price observations no later than the selected date
   and labels current profile/holdings as latest available.
7. Missing holdings produce an explicit unavailable state in the report and UI.
8. The browser receives ordered SSE progress events and renders the completed
   report without a full-page reload.
9. No browser request, response, local storage entry, or console log contains an
   API key.
10. Existing Python tests, new backend/frontend tests, lint, and frontend build
    all pass.

## Product Risks

- Yahoo field coverage varies by instrument and market. The adapter must tolerate
  partial data and retain raw-source timestamps.
- Fund metadata is generally latest-state data, not point-in-time historical data.
- LLM runs are slow and expensive. The UI must not imply that an interrupted HTTP
  request stopped provider billing immediately.
- Category-appropriate benchmarks are not universally inferable. The chosen
  benchmark must be visible and user-overridable.
