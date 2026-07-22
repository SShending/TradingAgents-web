# Phases 2-4 Development Roadmap

- Status: development-ready specification
- Confirmed: 2026-07-22
- Product: `SShending/TradingAgents-web`
- Deployment: local-first, single-user, open source, non-commercial

## Objective

Turn the Fund Mode Web MVP into a trustworthy personal research and portfolio
decision system. The system may recommend actions, but it never executes a
trade or mutates real holdings from a recommendation alone.

## Read Order

1. [DOMAIN_AND_TRUST.md](DOMAIN_AND_TRUST.md)
2. [PHASE_2_BETA_STABILIZATION.md](PHASE_2_BETA_STABILIZATION.md)
3. [PHASE_3_CHINA_FUNDS.md](PHASE_3_CHINA_FUNDS.md)
4. [PHASE_4_PORTFOLIO.md](PHASE_4_PORTFOLIO.md)
5. [CODEX_HANDOFF.md](CODEX_HANDOFF.md)

The cross-phase domain and trust contract takes precedence. A later phase may
extend it but must not silently redefine an earlier state or data meaning.

## Confirmed Product Decisions

- The product is for personal local use and remains open source.
- The browser and API bind to localhost by default.
- CIII is the primary third-party LLM provider. Local Ollama support is not a
  requirement for these phases.
- Automated paid-provider tests are allowed only behind explicit opt-in and
  enforceable token/request/retry budgets.
- An analysis date is the price cutoff. Latest fund profile and holdings data may
  be used, but their real observation/disclosure dates must be visible.
- Public internet data is acceptable only when every normalized field remains
  traceable to source and time.
- Untrusted critical data blocks an executable trade proposal. Research may
  continue with warnings.
- Listed instruments use buy/hold/sell. Off-exchange funds use subscribe, hold,
  partial redeem, full redeem, and platform-supported convert.
- Default portfolio evaluation is weekly, with extra evaluations for risk events
  or an explicit user request.
- Report chat may query fresh data, but it cannot overwrite formal advice. Only
  an explicit re-evaluation creates a new advice version.
- Real holdings come from an opening import followed by confirmed ledger entries.
- Advice and actual transactions are separate records. Only confirmed
  transactions affect real units and cost.
- The system may generate a transaction list, but the user executes it outside
  the application and records the confirmed result.

## Dependency Order

```text
Phase 2: persistence, trust, usage budgets, chat, deterministic test/runtime
   |
   v
Phase 3: China public-fund identity, data adapters, single-fund actions
   |
   v
Phase 4: real portfolio ledger, risk policy, target weights, trade proposals
```

Do not implement the phases in one branch. Each phase starts only after the
previous phase is merged and its Definition of Done is met.

Recommended branches:

```text
feat/beta-persistence-trust
feat/china-fund-data
feat/portfolio-ledger-advice
```

## Recommendation Boundary

This project provides personal research and decision support. A recommendation
must always state:

- the action and confidence;
- a short reason;
- the data cutoff and latest-only fields;
- the benchmark;
- the critical warnings;
- whether it is executable or observation-only; and
- the constraints that produced any amount or target weight.

No phase adds brokerage credentials, platform automation, or automatic order
execution.

## Stage Gates

Phase 2 must be complete before a China-fund provider is integrated. Phase 3
must resolve and trust-gate the confirmed acceptance catalog before portfolio
advice can use those funds. Phase 4 must derive holdings from confirmed ledger
entries rather than creating a second mutable position store.
