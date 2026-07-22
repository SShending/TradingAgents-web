# Phase 4: Real Portfolio and Trade Proposals

## Outcome

Maintain a real local portfolio from confirmed transactions, evaluate it under a
user-defined risk policy, and produce a non-executing trade proposal with target
weights, approximate amounts, and short reasons.

## Scope

- Portfolio and risk-policy records.
- CSV opening-position import with preview and validation.
- Confirmed transaction ledger and derived positions/cash.
- Draft/submitted/confirmed/failed/cancelled transaction workflow.
- Weekly, event-triggered, and on-demand portfolio evaluations.
- Target weights and deterministic constraint enforcement.
- System proposal and user-proposed-plan comparison.
- Subscribe/redeem/convert proposal semantics.
- Approximate fees/friction and QDII settlement awareness.
- Versioned proposals linked to data, trust, risk, and advice snapshots.

## Non-Goals

- Brokerage or sales-platform API connection.
- Automatic execution or automatic confirmation.
- Tax-lot optimization or accounting-grade statements.
- Multi-user/shared portfolios.
- Unlimited free-form optimization without user risk constraints.

## Portfolio Domain

### Portfolio

```text
id
name
base_currency
created_at
archived_at
active_risk_policy_id
```

### Risk Policy

```text
risk_level: conservative | balanced | growth
investment_horizon_months
max_acceptable_drawdown
max_instrument_weight
max_sector_weight
minimum_cash_weight
rebalance_threshold
minimum_holding_days
```

All percentages are explicit decimals and validated. Policy changes create a new
version; old evaluations retain the policy version they used.

### Transaction

```text
id
portfolio_id
instrument_id
type
status
requested_at
submitted_at
confirmed_at
currency
requested_amount
requested_unit_fraction
confirmed_units
confirmed_nav
estimated_fee
actual_fee
sales_platform
source_proposal_id
notes
```

Initial imported holdings become confirmed `opening_balance` ledger entries.
Conversions become linked `convert_out` and `convert_in` legs after confirmation.

### Position

Derived from confirmed transactions:

```text
confirmed_units
cost_basis
total_invested
estimated_market_value
unrealized_return
first_purchase_date
last_confirmed_transaction_date
sales_platforms[]
```

Never update position units from a proposal or submitted transaction.

### Trade Proposal

```text
id and version
portfolio_snapshot_id
risk_policy_version
data_snapshot/trust IDs
available_cash
declared_contribution_or_withdrawal
current_weights
target_weights
items[]
constraint_results[]
confidence
executable_status
created_at
expires_at
```

Each item includes action, current/target weight, proposed amount or unit
percentage, approximate friction, short reason, trust status, and blocked reason.

## Opening CSV Import

Provide a downloadable UTF-8 CSV template. Required logical fields:

```text
fund_code
fund_name
share_class
confirmed_units
total_invested
cost_basis
first_purchase_date
last_transaction_date
sales_platform
```

Portfolio-level cash is imported separately or in a dedicated row. Optional
fields include currency, notes, and actual accumulated fees.

Import flow:

1. upload/choose a local CSV through the localhost UI;
2. parse without committing;
3. resolve every code and show mismatches/duplicates;
4. validate decimal/date values and share class;
5. display resulting opening positions and totals;
6. require explicit confirmation; and
7. commit opening-balance transactions atomically.

One invalid row blocks commit but not preview. Re-import is idempotent by import
batch ID and row hash.

## Cash and New Money

Default proposals use only confirmed portfolio cash plus cash expected from
proposed redemptions. An evaluation request may declare:

```text
new_contribution_amount
planned_withdrawal_amount
```

These values belong to that evaluation and do not change real cash until a
confirmed transaction records them. The engine must never assume unlimited new
capital.

## Evaluation Cadence

- Scheduled default: once per week.
- Event-triggered: trust failure, risk-limit breach, material allocation drift,
  or a user-configured material event.
- On-demand: user requests evaluation or proposes a change.

Daily data refresh does not automatically create a trade proposal. A cooldown
and minimum holding-period rule suppress unnecessary churn unless a hard risk
constraint is breached.

## Evaluation Pipeline

```text
confirmed ledger
  -> portfolio snapshot
  -> current trusted fund data
  -> benchmark and exposure calculation
  -> deterministic risk/constraint evaluation
  -> candidate target weights
  -> action eligibility and cash feasibility
  -> LLM qualitative ranking/short reasons
  -> deterministic final validation
  -> immutable trade proposal
```

The LLM cannot change ledger balances, bypass a trust block, exceed policy
constraints, or create cash. A final deterministic validator rejects an invalid
LLM suggestion.

## Target Weights

The first optimizer should be transparent and constraint-based rather than a
black-box return maximizer. It may:

- reduce violated single-fund or sector concentration;
- preserve minimum cash;
- respect user horizon/risk level;
- reduce excessive correlation and duplicated exposure;
- limit turnover and minimum transaction size; and
- prefer no action when improvements are not material.

Expected returns generated solely by an LLM must not drive exact weights. Every
target-weight change requires deterministic constraint or evidence reason codes.

## User-Proposed Plan Comparison

The user may describe intended operations such as redeeming one fund and buying
another. The system computes three comparable snapshots:

```text
current portfolio
portfolio after user plan
portfolio after system alternative
```

Compare expected concentration, drawdown proxy, volatility, correlation,
benchmark exposure, cash, approximate friction, data trust, and policy violations.
The system preserves user intent and presents an alternative; it does not
silently rewrite or execute the user's plan.

## Operation Semantics

- Subscribe: target amount and expected weight; confirmed units remain unknown.
- Redeem partial: percentage of confirmed units plus estimated units/value.
- Redeem all: only when minimum balance/fee legality is sufficiently known.
- Convert: only when user/platform capability confirms native conversion;
  otherwise show redeem and subscribe legs.
- Hold: explicit no-action item with re-evaluation triggers when useful.

Fees are rough friction estimates. Actual confirmed NAV, units, and fees replace
estimates in the ledger without rewriting the historical proposal.

## Transaction Workflow

The application generates a proposal. The user may:

- dismiss it;
- create draft transaction records from selected items;
- mark drafts submitted after acting on an external platform;
- later enter confirmed units/NAV/fees or mark failed/cancelled.

Only confirmation posts ledger effects. The UI always shows projected and
confirmed portfolio states separately while transactions are pending.

## Benchmark and Exposure

Each position retains its fund/strategy benchmark. Portfolio benchmark returns
are weighted using a documented weighting/rebalancing convention tied to the
portfolio snapshot. User overrides are versioned.

Sector/theme exposure must account for disclosed-holdings age. Unknown exposure
is an explicit bucket, not redistributed across known sectors.

## API Changes

```text
POST /api/portfolios
GET  /api/portfolios
GET  /api/portfolios/{portfolio_id}

GET  /api/portfolios/{portfolio_id}/import-template.csv
POST /api/portfolios/{portfolio_id}/imports/preview
POST /api/portfolios/{portfolio_id}/imports/{import_id}/commit

GET  /api/portfolios/{portfolio_id}/transactions
POST /api/portfolios/{portfolio_id}/transactions
POST /api/transactions/{transaction_id}/submit
POST /api/transactions/{transaction_id}/confirm
POST /api/transactions/{transaction_id}/fail
POST /api/transactions/{transaction_id}/cancel

GET  /api/portfolios/{portfolio_id}/risk-policy
POST /api/portfolios/{portfolio_id}/risk-policy
POST /api/portfolios/{portfolio_id}/evaluate
POST /api/portfolios/{portfolio_id}/evaluate-user-plan
GET  /api/portfolios/{portfolio_id}/proposals
GET  /api/proposals/{proposal_id}
POST /api/proposals/{proposal_id}/create-drafts
```

Confirmation endpoints require optimistic version checks so a stale browser
cannot double-confirm or overwrite a transaction.

## UI Changes

- Portfolio switcher and compact current-value/risk summary.
- Opening CSV import preview with row-level errors.
- Holdings table with units, cost, value, return, trust, and last disclosure.
- Cash and per-evaluation contribution/withdrawal controls.
- Risk-policy editor using bounded numeric controls.
- Current versus target allocation and constraint results.
- User-plan comparison in three aligned views.
- Proposal list with action, amount/unit percentage, reason, warning, and expiry.
- Draft/submitted/confirmed transaction workflow.
- Separate projected and confirmed portfolio totals.
- Weekly/on-demand evaluation history and advice-version comparison.

The default screen remains operational and compact. Do not turn every metric into
a decorative card or hide blocking trust reasons behind color alone.

## Implementation Slices

1. Portfolio/risk/transaction/proposal domain records and SQLite migrations.
2. Ledger posting rules, derived positions/cash, and property-style tests.
3. CSV template, preview, resolution, idempotency, and atomic commit.
4. Risk-policy versions and deterministic constraint evaluator.
5. Portfolio snapshots, benchmark/exposure/correlation calculations.
6. Transparent candidate target weights and cash-feasible action generation.
7. LLM qualitative layer plus final deterministic validator.
8. User-plan comparison and platform-aware conversion representation.
9. API/UI portfolio, import, risk, proposal, and transaction workflows.
10. Weekly/on-demand scheduler and end-to-end acceptance.

## Test Plan

- Decimal ledger arithmetic and no binary-float drift.
- Opening import atomicity, duplicate detection, idempotency, and rollback.
- Only confirmed transactions alter positions/cash.
- Submitted, failed, and cancelled transactions preserve real holdings.
- Subscribe, partial/full redeem, conversion legs, dividend, and fee adjustments.
- Optimistic concurrency rejects duplicate confirmation.
- Risk-policy versioning and every hard constraint.
- No unlimited cash; contribution/withdrawal scoped to one evaluation.
- Target weights sum correctly after cash and unknown exposure.
- Trust-blocked instrument cannot appear in executable proposal.
- Minimum holding/cooldown prevents churn unless hard risk limit breached.
- Current/user/system three-way comparison uses the same snapshot and policy.
- LLM output cannot bypass deterministic validation.
- QDII pending/lag cases.
- Backup/restore retains ledger and advice lineage.
- Playwright import, evaluate, proposal, submit, and confirm flows.

## Definition of Done

- A user can import real holdings through CSV and verify them before atomic commit.
- Real positions are reproducibly derived from confirmed ledger entries.
- The user can configure risk/horizon/drawdown/concentration/cash constraints.
- Weekly and on-demand evaluations generate versioned proposals.
- Proposal amounts respect confirmed cash and declared new money.
- User plans and system alternatives are compared without automatic mutation.
- Proposed/submitted/confirmed states are clearly separated in API and UI.
- Only trusted critical data produces executable proposal items.
- No brokerage credential or execution path exists.
- Deterministic backend/frontend/Playwright tests and a manual personal-portfolio
  dry run pass.
