# ETF Sector Leadership Planner

Advisory-only investment planning workflow for tracking sector leadership through ETF holdings snapshots and producing manual trading recommendations.

## What this system does

For each of the configured 10 sectors, the planner:

- tracks a curated set of 5 sector/thematic ETFs
- refreshes ETF holdings snapshots on a staged 5-sector / 5-sector alternating-day cycle
- reviews all 10 sectors weekly using the latest stored holdings snapshots first
- analyzes underlying holdings to infer the strongest stock leader
- requires confirmation before switching away from the current leader
- only acts on the monthly window unless a significant-change override applies
- falls back to a sector ETF when no stock leader qualifies
- exports a manual review report and suggested buy/sell list

## What it does not do

- no live broker execution
- no automatic order placement
- no claim of fully institutional data quality

## Core operating model

- **Universe:** 10 sectors total, 5 tracked ETFs per sector
- **Tracked ETF list:** selected during maintenance, then treated as **static** for daily operations
- **Snapshot refresh:** alternating-day batches of 5 sectors / 5 sectors (daily refresh is the only workflow that spends Alpha Vantage daily budget for ETF holdings)
- **API budget fit:** 25 calls/day = 5 sectors × 5 ETFs via Alpha Vantage
- **Review cadence:** weekly, **hard cache-only** (no live Alpha Vantage calls)
- **Action cadence:** monthly
- **Confirmation:** consecutive review confirmations required before switching
- **Override:** significant-change rule can unlock an earlier switch
- **Fallback:** sector ETF if no valid stock leader exists
- **Freshness reporting:** explicit per ETF and per sector in reports/output
- **Maintenance window:** first Sunday of every month — `initialize_tracked_funds.py` refuses to run outside this window unless `--allow-outside-maintenance` is passed

### Workflow separation

| Workflow             | Command                          | Live Alpha Vantage calls? | Spends daily budget? |
|----------------------|----------------------------------|---------------------------|----------------------|
| `refresh`            | `python3 main.py refresh`        | Yes, ETF holdings only    | Yes                  |
| `review`             | `python3 main.py review`         | **No** (cache-only)       | No                   |
| `maintenance`        | `python3 initialize_tracked_funds.py` | Yes, performance scoring | Yes (first Sunday)  |
| `manual_diagnostic`  | `python3 main.py doctor`         | No                        | No                   |

A persistent ledger in SQLite (`alpha_vantage_usage` table in `data/fund_leaders.db`) enforces the daily budget across workflows and across process restarts. Every attempted Alpha Vantage call is recorded as either `consumed` or `blocked` with the reason.

See `docs/STRATEGY_SPEC.md` for the canonical strategy definition.

## Quick start

### 1) Create environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2) Configure secrets

```bash
cp .env.example .env
```

Set `ALPHA_VANTAGE_API_KEY` in `.env` for ETF holdings/performance data.

The planner refreshes ETF holdings on alternating days and reviews from cache first, using this provider order:

```yaml
api:
  holdings_provider_order: ["cache", "alpha_vantage"]
```

### 3) Validate local setup

```bash
python3 main.py doctor
```

### 4) Initialize the tracked ETF universe

```bash
# First-time bootstrap (outside the first-Sunday maintenance window):
python3 initialize_tracked_funds.py --force --allow-outside-maintenance

# Normal recurring maintenance (first Sunday of the month):
python3 initialize_tracked_funds.py --force
```

Maintenance is gated to the first Sunday of each month to avoid competing
with the daily refresh job for Alpha Vantage budget. Use
`--allow-outside-maintenance` only for the first-ever bootstrap or explicit
ad-hoc maintenance.

### 5) Refresh holdings snapshots

```bash
python3 main.py refresh
# or explicit batch/date
python3 main.py refresh 2026-04-10 batch_a
python3 main.py refresh 2026-04-11 batch_b
```

By default the planner chooses `batch_a` on even ordinal dates and `batch_b` on odd ordinal dates.

### 6) Run a weekly review

```bash
python3 main.py review
# or
python3 main.py review 2026-04-10
```

The review is **hard cache-only** and evaluates all sectors from the latest stored holdings snapshots. It never issues live Alpha Vantage calls, regardless of provider order configuration.

### 7) Inspect the latest saved run

```bash
python3 main.py latest
```

## Operating cadence

Recommended routine:

1. Run `python3 main.py refresh` daily. This is the only workflow that consumes Alpha Vantage daily budget for ETF holdings.
2. Let the alternating schedule refresh 5 sectors each day.
3. Run `python3 main.py review` weekly. It is cache-only and does not spend Alpha Vantage budget.
4. Only action `initiate`/`switch` recommendations manually during the monthly window unless a significant-change override applies.
5. On the first Sunday of each month, optionally run `python3 initialize_tracked_funds.py --force` for tracked-ETF re-ranking. Do **not** run the daily refresh job in parallel with maintenance.

## Freshness semantics

Each ETF snapshot now reports:

- `data_status`: `live`, `fresh_cache`, `stale_cache`, `cache_miss`, etc.
- `cached_at`
- `age_hours` / `age_days`
- `freshness`: `fresh`, `stale`, `very_stale`, or `unknown`

Each sector review also reports aggregate freshness and stale coverage so stale inputs are visible before any manual decision.

## Key outputs

- `output/leaders.csv`
- `output/leaders.json`
- `output/reports/manual_review_*.txt`
- `output/reports/manual_review_*.json`
- SQLite state in `data/fund_leaders.db`
- ETF holdings cache under `data/cache/`

## Key files

- `config.yaml` - sector, cadence, fallback, confirmation, thresholds, and refresh batches
- `initialize_tracked_funds.py` - ranks and stores the ETF universe per sector
- `fund_analyzer.py` - refresh/review orchestration and export flow
- `strategy_engine.py` - confirmation/stateful recommendation logic
- `manual_report.py` - advisory/manual-trading report generation
- `holdings_fetcher.py` - cache-first ETF holdings fetcher with Alpha Vantage live fallback and freshness metadata
- `db_manager.py` - SQLite schema and persisted run/strategy state
- `docs/STRATEGY_SPEC.md` - actual in-repo strategy spec

## Production caveat

The free-tier-safe model assumes you refresh holdings snapshots in staged batches and review from cache. If you skip refreshes for too long, the review will still run, but freshness reporting will show stale or missing inputs explicitly.
