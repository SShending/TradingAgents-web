# Cross-Phase Domain and Data Trust Contract

## Purpose

This document fixes meanings shared by phases 2-4. Persistence schemas, API
models, prompts, reports, and UI labels must use the same vocabulary.

## Time Semantics

`analysis_date` is the market/NAV price cutoff. A price observation later than
that date is forbidden in deterministic performance calculations.

Fund profile, manager, fees, purchase status, and holdings may be latest-state
data. Each such field must retain its own observation, publication, and effective
date. Reports must not describe latest-state data as if it were known on a
historical analysis date.

## Core Terms

### Instrument

A uniquely identified security or fund share class. A-share-class and
C-share-class codes are distinct instruments even when they belong to the same
fund product.

### Fund Product

The parent investment product shared by one or more instrument/share-class
codes. Product identity must not erase share-class fees or transaction rules.

### Source Observation

One retrieved provider payload or disclosure with source, retrieval time,
effective date, publication date, raw-content hash, and cache status.

### Evidence Field

A normalized value linked to one or more source observations. Missing is distinct
from zero, false, empty, or not applicable.

### Trust Assessment

A deterministic evaluation of evidence completeness, freshness, consistency,
and action eligibility. The LLM may explain it but cannot override it.

### Advice Version

An immutable recommendation produced from a specific data snapshot, risk policy,
benchmark, portfolio snapshot, model configuration, and conversation context.

### Trade Proposal

An unexecuted list of suggested actions. It never changes real holdings.

### Transaction

A user-recorded real-world operation. Only a transaction in `confirmed` status
affects real holdings, units, cash, and cost.

### Position

A derived view of confirmed opening balances and confirmed transactions. It is
not an independently editable source of truth after initial import.

## Trust Levels

```text
trusted
  Critical evidence is present and fresh enough for the requested action.

usable_with_warning
  Research can proceed; non-critical fields are missing, old, or single-source.

insufficient
  A critical field is missing, stale, contradictory, or cannot be traced.
```

Only `trusted` evidence may produce an executable trade proposal. An explicit
user override changes the result to observation-only; it does not promote the
evidence to trusted.

## Evidence Contract

Every normalized provider field must be able to expose:

```text
value
unit
source_id
source_url or source_reference
retrieved_at
published_at (nullable)
effective_at (nullable)
raw_hash
freshness_status
normalization_warnings[]
```

Cache hits retain the original retrieval metadata and add the cache-read time.
Provider error strings never become evidence values.

## Initial Freshness Policy

These are configurable defaults, not claims about every provider.

| Data group | Initial policy | Effect when outside policy |
| --- | --- | --- |
| Fund identity/share class | Revalidate within 30 days | Block if identity is ambiguous |
| Purchase/redemption status | Observe on the current local day | Block executable action |
| Mainland domestic NAV | No more than 2 trading days behind | Block executable action |
| QDII NAV | No more than 5 relevant trading days behind | Observation-only or reduced confidence |
| Fee/holding-period rule | Revalidate within 30 days | Block when required to determine action legality |
| Manager/profile | Revalidate within 30 days | Warn; normally non-blocking |
| Holdings/allocation | Latest published reporting period | Warn and reduce confidence as disclosure ages |
| Benchmark prices | Align with fund return cutoff | Block relative metric, not fund-only research |

Trading calendars and public holidays must be used instead of raw calendar-day
subtraction where the distinction changes the result.

## Critical Data by Action

### Subscribe

- unambiguous instrument/share class;
- current subscription status and limits when available;
- sufficiently recent NAV;
- currency;
- risk-policy capacity; and
- available cash plus explicitly declared new contribution.

### Redeem

- confirmed units;
- current redemption status;
- holding-period/fee rule sufficient for a rough friction assessment;
- sufficiently recent NAV; and
- any minimum remaining-holding constraint when available.

### Convert

- all subscribe and redeem requirements;
- explicit evidence or user confirmation that the selected sales platform
  supports conversion between the two share classes; and
- source and target transaction status.

Without confirmed platform support, conversion is represented as a redeem plus a
subscribe proposal, never as a native conversion instruction.

## Action Vocabulary

Listed instruments:

```text
buy | hold | sell
```

Off-exchange funds:

```text
subscribe | hold | redeem_partial | redeem_all | convert
```

Subscribe proposals use currency amounts. Redemption proposals use a percentage
of confirmed units and may show estimated units. Exact confirmation NAV, units,
and fees are recorded only after the real transaction confirms.

## Advice Eligibility

The deterministic pipeline decides:

- whether advice is executable or observation-only;
- which actions are legally/data-wise available;
- risk-policy violations;
- cash feasibility;
- target-weight math; and
- deterministic metrics.

The LLM may rank qualitative factors, summarize evidence, and write a short
reason. It must not invent a missing value, promote trust, calculate ledger
balances, or mark a transaction confirmed.

## Advice Versioning and Chat

Each advice version stores immutable references to:

- input data snapshot and trust assessment;
- analysis/report version;
- model/provider and prompt version;
- token/request usage;
- benchmark;
- risk policy;
- portfolio snapshot, when applicable; and
- parent advice version, when re-evaluated.

Conversation messages may retrieve new evidence and must label it as newer than
the report. Chat can produce a candidate change, but only an explicit
`re-evaluate` command creates a new formal advice version.

## Job State

```text
queued -> running -> completed
                  -> failed
                  -> cancelling -> cancelled
                  -> interrupted
```

On process restart, a job found in `queued`, `running`, or `cancelling` becomes
`interrupted` unless a graph checkpoint can safely resume the exact run
signature. Never leave a stale job looking active.

## Transaction State

```text
draft -> proposed -> submitted -> confirmed
                 \-> cancelled
                            \-> failed
```

`submitted` is projected separately from real holdings. Only `confirmed` posts
ledger effects. Status changes are append-only audit events even if a current
status column is maintained for efficient reads.

## Numeric and Storage Rules

- Store money, units, NAV, and fees as decimal strings or fixed-scale decimal
  values, never binary floats in the ledger.
- Store timestamps in UTC and retain exchange/local calendar dates separately.
- Use UUIDs for jobs, reports, conversations, advice, portfolios, proposals, and
  transactions.
- Keep provider secrets outside SQLite and outside browser storage.
- Redact secrets before persistence, not only before display.
- Raw provider payload retention is configurable and must exclude secrets.

## Shared Module Boundaries

Recommended ownership:

```text
tradingagents/domain/          enums and immutable domain records
tradingagents/persistence/     SQLite repositories and migrations
tradingagents/trust/           evidence and deterministic trust rules
tradingagents/advice/          advice versioning and action eligibility
tradingagents/dataflows/       provider-specific retrieval/normalization
tradingagents/services/        use-case orchestration
tradingagents/web/             HTTP/SSE mapping only
```

HTTP routes must not contain portfolio math, trust rules, provider parsing, or
LLM prompt construction.
