# Codex Handoff for Phases 2-4

## Required Reading

Before implementing any phase, read all documents in this directory in the order
listed by README.md, then read the implemented MVP documents and relevant code.

Do not implement phases 2-4 in one branch. Complete and merge one phase before
starting the next.

## Repository Rules

```text
origin   -> SShending/TradingAgents-web
upstream -> TauricResearch/TradingAgents
```

- Feature pull requests target the fork's `main`.
- Preserve unrelated changes and existing stock/crypto/CLI behavior.
- Do not send a pull request to official upstream unless explicitly instructed.
- Never commit `.env`, CIII credentials, real portfolio data, raw private chat,
  local SQLite databases, backups, or live-provider payloads.
- Use synthetic or safely recorded fixtures in CI.

## Cross-Phase Constraints

- Trust, numeric calculations, action eligibility, ledger posting, cash, and risk
  constraints are deterministic code, not LLM decisions.
- Current-only data always keeps its true date in historical analysis.
- Advice is immutable/versioned and separate from transactions.
- Only confirmed transactions change real holdings.
- The browser never receives provider credentials.
- The application binds locally and remains single-user.
- No automatic execution or brokerage integration.

## Phase 2 Start Prompt

```text
Implement Phase 2 from docs/next-phases/PHASE_2_BETA_STABILIZATION.md.
Read README.md and DOMAIN_AND_TRUST.md first. Work on
feat/beta-persistence-trust from the fork main after the MVP is merged. Deliver
SQLite migrations/repositories, restart-safe jobs/events/reports, source evidence
and trust foundations, CIII usage budgets, persistent report chat, explicit
advice re-evaluation, backup/restore, UI/API changes, deterministic tests, and
one-command local startup. Do not begin China-fund or portfolio work. Run all
quality gates and verify the full pytest process exits normally.
```

## Phase 3 Start Prompt

```text
Implement Phase 3 from docs/next-phases/PHASE_3_CHINA_FUNDS.md only after Phase 2
is merged. Start with the required provider technical spike and checked-in
coverage matrix; do not assume a public endpoint is stable before probing it.
Deliver six-digit code/name resolution, share-class identity, capability-based
public data adapters, provenance/freshness/trust gates, benchmark and QDII rules,
fund-specific subscribe/hold/redeem/convert advice, API/UI changes, and validation
of the full 20-fund acceptance catalog. Insufficient critical data must produce
observation-only research, never an executable list.
```

## Phase 4 Start Prompt

```text
Implement Phase 4 from docs/next-phases/PHASE_4_PORTFOLIO.md only after Phase 3
is merged. Deliver versioned portfolio/risk records, CSV opening import, a
decimal confirmed-transaction ledger, derived positions/cash, weekly and
on-demand evaluation, transparent target weights, user-plan comparison,
trust-gated non-executing trade proposals, draft/submitted/confirmed workflows,
API/UI changes, and complete deterministic/Playwright tests. Never update real
holdings from advice or an unconfirmed transaction and do not add brokerage
execution.
```

## Per-Phase Execution Protocol

1. Confirm the previous phase is merged and the worktree is clean.
2. Create the exact feature branch from the fork's current `main`.
3. Inspect existing ownership boundaries before choosing modules.
4. Establish backend/frontend test and lint baselines.
5. Create a plan matching the implementation slices in the phase document.
6. Implement one tested vertical slice per reviewable commit.
7. Keep schema migrations forward-only and test every migration path.
8. Run deterministic quality gates after each slice.
9. Run opt-in live tests only with explicit budget configuration.
10. Start local services and verify desktop/mobile workflows with Playwright.
11. Report omitted live checks, exact limits, source coverage, and residual risk.

## Completion Report

For each phase, report:

- delivered user behavior;
- schema migrations and recovery behavior;
- API and UI changes;
- trust/budget/risk rules added;
- deterministic test/lint/build/Playwright results;
- opt-in live provider tests and actual usage;
- known provider/data gaps; and
- the branch, commit, and fork pull-request URL.
