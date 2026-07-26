# Phase 3 Public Provider Matrix

This is the mandatory Phase 3 provider spike record. It records normalized
capabilities and failure boundaries only. It does not retain full provider
payloads, private conversations, credentials, or live fund observations.

## Selected Adapter

| Candidate | Selection | Reason | Scope |
| --- | --- | --- | --- |
| Eastmoney public fund pages | Selected | It exposes code search, dated NAV history, purchase/redemption labels, fund profile, approximate fees, disclosed benchmark text, manager, and allocation fields in one public source. | Live local mode |
| Synthetic Phase 3 fixture | Test/demo only | Covers representative share classes with deterministic evidence, dates, and partial-failure cases. | CI, tests, local demo |
| A second public provider | Deferred | Multiple-provider selection would broaden the validated Phase 3 provider surface. | Not implemented |

The adapter confines endpoint parsing to `tradingagents/china_funds/eastmoney.py`.
No application code rotates proxies, disguises user agents, or retries a provider
request indefinitely. Requests have a bounded timeout. HTTP 429 and timeout
signals remain provider failures; capability failures do not discard data from
unrelated capability groups.

## Capability Matrix

| Capability | Eastmoney public adapter | Normalized output | Cache policy | Trust consequence |
| --- | --- | --- | --- |
| Identity/share class | Code search | Code, display name, manager/company when exposed | 30 days | Ambiguous/unverified identity blocks operation |
| NAV history | `pingzhongdata` trend series | Dated NAV points, cut off at `analysis_date` | 6 hours per code/cutoff | Domestic lag >2 relevant trading days or QDII lag >5 blocks operation |
| Transaction status | Fund list status data | Subscription/redemption labels and observation time | 5 minutes | Missing, expired, or not-current-day status blocks affected action |
| Fees | Trend/profile fields | Approximate subscribe/redeem rules with warnings | 7 days | Unknown fee/holding rule blocks affected redemption |
| Manager/disclosure | Trend/profile fields | Manager and allocation; unavailable holdings remain missing | 7 days | Missing holdings lowers confidence only |
| Benchmark | Fund profile | Disclosed text and tracked-index name where exposed | 30 days | Missing benchmark blocks relative metrics, not fund-only research |
| QDII context | Catalog classification plus NAV/status data | NAV lag, date cutoff, currency, unknown market-move reflection | Derived, not separately cached | UI must state published NAV is not an execution NAV |

`provider_cache` stores only normalized JSON, source reference, original
retrieval/effective/expiry times, and a normalized-content hash. It never stores
the raw Eastmoney response. A cache hit retains original evidence timestamps. An
expired cache can support observation-only research only when a fresh provider
attempt fails; it is explicitly marked stale and cannot satisfy the identity,
NAV, or current transaction-status execution gate.

## Validation Boundary

- No user-linked fund list is checked in. CI uses reserved synthetic identifiers
  to validate dynamic code resolution, unambiguous name resolution, A/C
  separation, QDII context, and provider capability degradation without a real
  network call.
- Live validation is manual and opt-in because public provider availability,
  terms, throttling, and coverage may change. A live failure is recorded as a
  provider limitation, never converted into an invented fund value.
- The deterministic market calendar includes Shanghai Stock Exchange published
  2025-2026 closures and uses a weekday fallback outside that published range.
  QDII overseas-market holidays remain an explicit provider/data limitation; the
  app therefore does not claim to know whether an intraday overseas move is in
  the next published NAV.

Run a bounded manual probe by supplying representative codes at runtime:

```bash
python scripts/probe_china_funds.py CODE [CODE ...] --analysis-date YYYY-MM-DD --timeout 8
```

The command makes at most four public requests per supplied code in one process,
reuses only in-memory responses for the remaining capability parsers, and prints
no provider payloads. Probe code sets and observations are not committed because
they can reveal a user's research interests or holdings. Public holdings remain
a provider limitation: unavailable rows stay missing and the trust layer adds
`HOLDINGS_UNAVAILABLE` rather than inferring constituents.
