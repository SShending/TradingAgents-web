# Phase 2: Beta Stabilization

## Outcome

Replace the MVP's process-memory-only behavior with a restart-safe local research
workspace. Establish data evidence/trust, CIII usage limits, report chat, and a
deterministic verification baseline before adding China-specific providers.

## Scope

- Persistent jobs, events, reports, advice versions, conversations, usage, and
  evidence metadata in SQLite.
- Restart recovery and explicit interrupted-job behavior.
- Source evidence and trust-assessment primitives shared by later phases.
- CIII request/token/retry budgets and usage visibility.
- Report follow-up chat with optional fresh-data retrieval.
- Explicit re-evaluation that creates a new advice version.
- Deterministic vendor tests with no real network or real sleep.
- One-command local production startup, backup, and restore.
- Real Yahoo plus CIII smoke validation behind explicit opt-in.

## Non-Goals

- China off-exchange fund providers.
- Real portfolio holdings or transaction ledger.
- Multi-user accounts, remote public deployment, or brokerage integration.
- Automatic trades.
- PostgreSQL, Redis, or a distributed worker queue.

## Current Baseline

The MVP uses an in-memory `JobManager`, daemon worker threads, replayable events
only while the process lives, and reports that disappear on restart. It has no
conversation model, usage ledger, trust gate, or formal advice version.

During planning verification on 2026-07-22, isolated Web API tests passed, while
one full-suite run was interrupted during the existing Yahoo rate-limit sleep
path after 533 passing tests. Phase 2 must make CI independent of real provider
backoff and prove that the complete suite exits normally.

## Persistence Design

Use the Python `sqlite3` module behind repository interfaces. Keep the local
dependency footprint small, but implement numbered, transactional schema
migrations from the first version.

Default database:

```text
~/.tradingagents/web/tradingagents.db
```

Override:

```text
TRADINGAGENTS_WEB_DB_PATH
```

Initial logical tables:

| Table | Responsibility |
| --- | --- |
| `schema_migrations` | Applied migration versions and timestamps |
| `analysis_jobs` | Request, status, run signature, timestamps, error code |
| `job_events` | Ordered persisted events for SSE replay |
| `reports` | Immutable report/result snapshots and Markdown export |
| `advice_versions` | Formal recommendation versions and trust eligibility |
| `conversations` | Conversation attached to one report/advice lineage |
| `conversation_messages` | User/assistant/tool messages with source references |
| `usage_records` | Provider/model requests, tokens, latency, retries, status |
| `source_observations` | Source/time/hash metadata for retrieved evidence |
| `trust_assessments` | Deterministic trust result and reason codes |

Store large JSON as versioned UTF-8 JSON text. Repository APIs return domain
records rather than SQLite rows.

## Job Recovery

- Persist the job before starting a worker.
- Persist each state transition and event before exposing it over SSE.
- On startup, mark stale active jobs `interrupted`.
- If a matching LangGraph checkpoint is valid, expose a user-controlled Resume
  action; do not resume automatically and spend tokens after restart.
- Keep `Last-Event-ID` replay working across restart.
- Bound event retention by job and preserve terminal/report events.
- Cancellation remains best-effort at graph boundaries and survives restart as
  an explicit terminal/interrupted state.

## CIII Provider Budgeting

Add provider-agnostic budget configuration with CIII as the acceptance provider:

```text
max_requests_per_analysis
max_total_tokens_per_analysis
max_retries_per_request
max_debate_rounds
daily_request_limit
daily_token_limit
```

Requirements:

- The user can configure limits without exposing credentials to the browser.
- Preflight shows configured maximums and a historical estimate when prior usage
  exists; it must say unknown rather than invent a monetary estimate.
- Provider-reported usage is authoritative when available.
- Missing token usage falls back to request count and emits a usage warning.
- Budget exhaustion stops new agent/model calls, persists partial reports, and
  returns a stable `BUDGET_EXHAUSTED` state.
- Retries count toward request limits and appear in usage history.
- Automated paid tests require an explicit environment opt-in and a stricter test
  budget than normal interactive analysis.

Suggested environment namespace:

```text
TRADINGAGENTS_BUDGET_MAX_REQUESTS
TRADINGAGENTS_BUDGET_MAX_TOKENS
TRADINGAGENTS_BUDGET_MAX_RETRIES
TRADINGAGENTS_BUDGET_DAILY_REQUESTS
TRADINGAGENTS_BUDGET_DAILY_TOKENS
TRADINGAGENTS_ENABLE_PAID_TESTS
```

## Evidence and Trust Foundation

Implement the evidence contract and trust levels from DOMAIN_AND_TRUST.md without
China-provider-specific rules. Wrap current Yahoo fund fields in evidence records
and produce a trust summary alongside the existing snapshot.

MVP compatibility:

- Existing snapshot keys remain readable during migration.
- New API versions return normalized evidence/trust fields.
- Existing Markdown export gains a Data Quality section.
- Missing optional Yahoo holdings stays warning-level.
- A trade-style recommendation is observation-only unless the trust gate has the
  critical fields required for that asset/action.

## Report Chat and Re-evaluation

Chat is attached to a completed report, not to an active mutable prompt buffer.

Capabilities:

- answer from report and cited evidence;
- retrieve current data when the user asks a time-sensitive question;
- identify newly retrieved data and whether it conflicts with the report;
- retain conversation across restart;
- report usage per response; and
- generate a candidate adjustment without changing formal advice.

Only `POST .../re-evaluate` creates a new advice version. Re-evaluation records
the triggering message IDs, new evidence snapshot, parent advice ID, and budget.

## API Changes

Add or extend:

```text
GET  /api/analyses
GET  /api/analyses/{job_id}
GET  /api/analyses/{job_id}/events
GET  /api/analyses/{job_id}/report.md
GET  /api/analyses/{job_id}/usage
GET  /api/analyses/{job_id}/trust
POST /api/analyses/{job_id}/resume

POST /api/reports/{report_id}/conversations
GET  /api/conversations/{conversation_id}
POST /api/conversations/{conversation_id}/messages
POST /api/conversations/{conversation_id}/re-evaluate

POST /api/admin/backup
POST /api/admin/restore/preview
POST /api/admin/restore/commit
```

Backup/restore routes bind locally, use server-controlled directories, and never
accept an arbitrary output path. A CLI backup command is preferable for the
first implementation; the browser may invoke it through safe fixed locations.

## UI Changes

- History view for completed, failed, cancelled, and interrupted jobs.
- Usage summary before and after analysis.
- Data Quality panel with trust level, reason codes, source times, and warnings.
- Report chat drawer/page with source badges and refreshed-data markers.
- Explicit Re-evaluate command that previews budget and creates a new version.
- Version selector comparing formal recommendations.
- Backup status and restore preview.
- Clear budget-exhausted, interrupted, resumable, and non-resumable states.

No authentication UI is required. The frontend must still avoid exposing keys,
environment values, raw stack traces, or arbitrary local paths.

## Runtime and Packaging

- Preserve the optional `[web]` dependency boundary.
- Add a production command that builds/serves the frontend and starts the API on
  localhost.
- Docker Compose persists the SQLite database and report/cache directories.
- Shutdown waits for worker bookkeeping and marks non-finished jobs accurately.
- Structured logs include job/advice IDs, event, duration, provider/model, safe
  error code, and usage, without prompts or secrets by default.

## Implementation Slices

1. Domain records, SQLite repository interfaces, migrations, and backup tests.
2. Persistent job/event manager and restart recovery.
3. Usage/budget accounting integrated at the LLM client boundary.
4. Evidence/trust records for current Yahoo data.
5. Persistent reports and formal advice versions.
6. Conversation service, fresh-data tool path, and explicit re-evaluation.
7. API/UI history, usage, trust, chat, and version comparison.
8. Runtime shutdown, Docker volumes, production startup, and documentation.
9. Deterministic full-suite cleanup and opt-in CIII/Yahoo smoke tests.

Each slice includes tests and a reviewable commit. Do not build UI against a
temporary in-memory schema that will be discarded by the next slice.

## Test Plan

- Migration from empty DB and every prior schema version.
- Transaction rollback on migration failure.
- Job/event/report persistence across app recreation.
- Stale running job becomes interrupted.
- Valid checkpoint offered for manual resume; invalid signature rejected.
- SSE replay after process restart and event-retention boundary.
- Budget preflight, exact limit, retry accounting, exhaustion, partial report.
- Secret redaction before DB/log persistence.
- Evidence missing/stale/fresh trust outcomes.
- Chat from report, fresh retrieval, conflicting evidence, restart persistence.
- Chat cannot alter formal advice; re-evaluation creates a child version.
- Backup/restore round trip and corrupt/incompatible preview rejection.
- Existing stock/fund/crypto behavior and API compatibility.
- Full pytest exits without live network or real sleep.
- Frontend lint/unit/build and Playwright history/chat/restart scenarios.

## Manual Live Matrix

With explicit paid-test opt-in and low budgets:

| Instrument | Purpose |
| --- | --- |
| `SPY` | Yahoo ETF fund path |
| `VFIAX` or a live-confirmed Yahoo mutual fund | Mutual-fund missing-field path |
| `AAPL` | Stock regression |
| `BTC-USD` | Crypto regression |

Run at least one CIII analysis, one follow-up fresh-data question, and one
re-evaluation. Record usage and redact credentials.

## Definition of Done

- Restart preserves terminal jobs, reports, advice, chat, usage, and evidence.
- Active jobs never remain falsely running after restart.
- CIII limits are enforced and visible; paid tests cannot run accidentally.
- Data Quality and trust reason codes are visible in API, UI, and export.
- Chat can use fresh data but cannot silently replace formal advice.
- Backup/restore succeeds with documented recovery steps.
- Full deterministic backend/frontend suites exit cleanly.
- One-command local production startup and persistent Docker startup work.
- Existing CLI and package consumers remain compatible.
