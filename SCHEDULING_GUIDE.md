# Fund Leader Tracker - Refresh & Review Scheduling Guide

This planner uses a **staged refresh + hard cache-only review** operating model with Alpha Vantage as the only live holdings source, so it behaves cleanly under the Alpha Vantage free tier.

## Workflow separation

| Workflow             | Command                          | Live Alpha Vantage calls? | Spends daily budget? |
|----------------------|----------------------------------|---------------------------|----------------------|
| `refresh`            | `python3 main.py refresh`        | Yes, ETF holdings only    | Yes                  |
| `review`             | `python3 main.py review`         | **No** (cache-only)       | No                   |
| `maintenance`        | `python3 initialize_tracked_funds.py` | Yes, performance scoring | Yes (first Sunday)  |
| `manual_diagnostic`  | `python3 main.py doctor`         | No                        | No                   |

Each workflow is tagged on every Alpha Vantage call in the persistent ledger (`alpha_vantage_usage` table in `data/fund_leaders.db`). The ledger enforces the daily budget across workflows and across process restarts.

## Core schedule

- **10 sectors total**
- **5 ETFs tracked per sector**
- tracked ETFs are selected during maintenance and treated as the static daily monitoring list
- **25 calls/day budget** (enforced by the persistent ledger)
- **Refresh cadence:** daily alternating batches of 5 sectors (only workflow that consumes the holdings budget)
- **Review cadence:** weekly, **hard cache-only** across all sectors
- **Action cadence:** monthly manual execution window
- **Maintenance cadence:** **first Sunday of every month** for tracked-ETF maintenance / re-ranking only (gated by default)

## Commands

### Daily staged refresh

```bash
python3 main.py refresh
```

Optional explicit forms:

```bash
python3 main.py refresh 2026-04-10 batch_a
python3 main.py refresh 2026-04-11 batch_b
```

### Weekly strategy review

```bash
python3 main.py review
```

This review is **hard cache-only**. The analyzer forces `fetch_mode=cache_only` and the ledger blocks any Alpha Vantage call with reason `workflow_disallows_live_calls`. Stale or missing snapshots surface through freshness reporting rather than being papered over with live fetches.

### Diagnostics

```bash
python3 main.py doctor
python3 main.py latest
```

## Batch layout

`batch_a`
- Aerospace & Defense
- Renewable Energy
- Healthcare & Biotech
- Automotive
- Precious Metals

`batch_b`
- Consumer Staples
- Tech & AI
- Financial Services
- Infrastructure
- Real Estate

Default rule:
- `batch_a` on even ordinal dates
- `batch_b` on odd ordinal dates

## Recommended automation

### Monday-Sunday

Run daily refresh:

```bash
python3 main.py refresh
```

### Weekly review day

Run:

```bash
python3 main.py review
```

Then manually inspect:
- stale sectors
- cache-miss sectors
- watch/switch decisions
- ETF fallback sectors
- actionable trades

### Monthly action window

Manually consider only `initiate` / `switch` trades during the configured monthly action window unless the review marks a significant-change override.

### Monthly maintenance window

Use the **first Sunday of every month** for tracked-ETF maintenance only:

```bash
python3 initialize_tracked_funds.py --force
```

The command refuses to run outside this window unless you pass
`--allow-outside-maintenance`. Use the override only for the first-ever
bootstrap or an explicit ad-hoc maintenance decision.

During maintenance:

- re-rank / reselect the 5 ETFs per sector only if needed
- update the stored tracked ETF list
- avoid running the normal daily refresh/review jobs in parallel with this maintenance work
- avoid any other Alpha Vantage-consuming validation or diagnostics during this window

### Alpha Vantage usage ledger

All Alpha Vantage call attempts are logged to the `alpha_vantage_usage`
table in `data/fund_leaders.db` with columns for workflow, function,
symbol, status (`consumed` / `blocked`), and outcome/reason.

- `refresh` and `review` run summaries include this telemetry:
  workflow, live-call allowance, calls attempted/successful/failed/blocked,
  and remaining daily budget.
- `python3 main.py doctor` reads the ledger but does **not** write to it.

## Why this model fits the free tier

A full live review of all 10 sectors would require roughly 50 ETF holdings calls.

The staged model avoids that:

- daily refresh updates only **25 ETF snapshots max**
- weekly review reads from stored cache across **all 10 sectors**
- stale data remains visible through freshness reporting instead of forcing live fetches

## Operational advice

- Use `ALPHA_VANTAGE_API_KEY` as the live holdings provider.
- Keep the alternating daily refresh cadence so the 25-call/day budget is not exhausted.
- If Alpha Vantage quota is exhausted mid-refresh, the run should stop early and leave the remaining ETFs for the next reset instead of grinding through the rest of the batch.
- If you skip refreshes, the review will still run, but stale or missing sectors will be flagged explicitly.
- Do not treat the output as auto-trading instructions; the workflow is advisory/manual only.
