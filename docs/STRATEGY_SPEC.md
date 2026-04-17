# ETF-Only Sector Leadership Strategy Spec

## Objective

This repository is an **advisory/manual-trading sector rotation planner**.

The system reviews a curated list of sector ETFs, inspects their stored holdings snapshots, and recommends one position per sector:

- the **confirmed stock leader** within that sector, or
- the configured **sector ETF fallback** when no stock leader meets the rules.

It does **not** place live orders.

## Operating model

### Universe and budget

- **9 active sectors total** (per current `config.yaml`)
- **5 tracked ETFs per sector**
- tracked ETFs are **not** meant to be re-ranked during normal daily operation
- the tracked ETF list is selected once and then treated as a static monitoring universe until an explicit maintenance refresh is run
- **25 API calls/day budget target**
- therefore the refresh workflow is split into **2 alternating batches**: `batch_a` with 5 sectors and `batch_b` with 4 sectors

### Cadence

- **Holdings snapshot refresh:** daily, alternating `batch_a` / `batch_b`
- **Strategy review:** weekly, **hard cache-only** across all 9 active sectors
- **Action cadence:** monthly
- **Maintenance window:** first Sunday of every month for tracked-ETF maintenance / re-ranking; `initialize_tracked_funds.py` is gated to this window by default
- during the maintenance window, do **not** run other Alpha Vantage-consuming checks in parallel
- **Override:** if a significant change occurs, a confirmed switch may be actioned before month-end

### Workflow separation

The planner recognises four workflows. Each one is tagged on every Alpha Vantage call so the persistent daily-budget ledger can attribute usage:

| Workflow             | Live AV calls?   | Consumes daily budget? |
|----------------------|------------------|------------------------|
| `refresh`            | Yes (holdings)   | Yes                    |
| `review`             | **No**           | No                     |
| `maintenance`        | Yes (performance)| Yes                    |
| `manual_diagnostic`  | No               | No                     |

The review workflow forces `fetch_mode=cache_only` inside `FundAnalyzer` and the ledger independently refuses any live call with reason `workflow_disallows_live_calls`. This is deliberately redundant so neither configuration drift nor a caller mistake can turn a review into a live burst.

### Alpha Vantage daily budget ledger

Persistent table `alpha_vantage_usage` in `data/fund_leaders.db` records every call attempt:

- `call_date`, `call_timestamp`
- `workflow`
- `function` (e.g. `ETF_PROFILE`, `TIME_SERIES_MONTHLY_ADJUSTED`, `GLOBAL_QUOTE`)
- `symbol`
- `status`: `consumed` (call dispatched to provider) or `blocked` (refused by the ledger)
- `outcome`: for `consumed`, `success` or `failure`; for `blocked`, the reason code

Blocked reason codes:

- `workflow_disallows_live_calls`
- `alpha_vantage_api_key_not_configured`
- `daily_budget_exhausted`
- `rate_limit_signalled_by_provider`

The `requests_per_day` value under `api:` in `config.yaml` is the configured daily budget. The ledger enforces it by counting `consumed` rows for today before allowing each call.

## Refresh vs review

### Refresh holdings snapshots

Purpose: update local ETF holdings cache only.

- refreshes 5 sectors per day
- refreshes up to 25 ETF snapshots per run
- uses provider order from config (`cache`, then `alpha_vantage` by default)
- stores holdings snapshots to local cache for later review

### Review strategy

Purpose: evaluate all sectors from the latest stored snapshots.

- reviews all 9 active sectors every run
- is **hard cache-only** — Alpha Vantage calls are blocked by the ledger
- exposes stale or missing data instead of silently hiding it

## Decision rules

For each sector:

1. Use the latest stored ETF holdings snapshots.
2. Aggregate company exposure across tracked ETFs.
3. Treat a company as a valid leader candidate only if it meets config thresholds:
   - minimum funds holding it
   - minimum prevalence across tracked ETFs
   - minimum average portfolio weight
4. Compare the current candidate with the previously active recommendation.
5. If the candidate changes, require confirmation across multiple reviews before switching.
6. Only switch on the monthly action window unless the move qualifies as a significant change.
7. If no valid stock leader exists, recommend the sector ETF fallback instead.

## Confirmation logic

Default behavior:

- a new leader must appear for **2 consecutive review runs** before a switch is allowed
- once confirmed, the switch is still deferred to the monthly action window
- exception: a **significant change** can unlock the switch sooner

## Significant change logic

Default significant change triggers:

- candidate average weight exceeds the active leader by at least `1.5%`, or
- candidate prevalence exceeds the active leader by at least `20 percentage points`, or
- the current active stock is no longer valid and the strategy must fall back to the sector ETF

## Portfolio framing

- one recommendation per sector
- equal-weight target across covered sectors
- outputs are **manual trade suggestions**, not execution instructions

## Freshness and stale-data behavior

Each ETF snapshot carries explicit metadata:

- `data_status`
- `cached_at`
- `age_hours` / `age_days`
- `freshness`
- `source`

Each sector review also carries aggregate freshness:

- sector freshness label
- ETF coverage ratio
- average snapshot age
- stale ETF count
- cache-miss ETF count

The planner is allowed to review from stale cache, but stale inputs must remain visible in output and reports.

## Persistence

Each review run stores:

- top leader evidence
- per-sector active recommendation
- pending switch candidate and confirmation count
- sector freshness metadata
- run summary and portfolio plan
- manual review report paths

This lets the planner compare the current review with prior state across runs.
