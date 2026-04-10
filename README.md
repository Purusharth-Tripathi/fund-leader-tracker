# ETF Sector Leadership Planner

Advisory-only investment planning workflow for tracking sector leadership through ETF holdings and producing manual trading recommendations.

## What this system does

For each configured sector, the planner:

- tracks a curated set of sector/thematic ETFs
- analyzes the underlying holdings to infer the strongest stock leader
- requires confirmation before switching away from the current leader
- only acts on the monthly window unless a significant-change override applies
- falls back to a sector ETF when no stock leader qualifies
- exports a manual review report and suggested buy/sell list

## What it does not do

- no live broker execution
- no automatic order placement
- no claim of fully institutional data quality

## Core operating model

- **Review cadence:** weekly
- **Action cadence:** monthly
- **Confirmation:** consecutive review confirmations required before switching
- **Override:** significant-change rule can unlock an earlier switch
- **Fallback:** sector ETF if no valid stock leader exists
- **Data resilience:** uses local holdings cache when Alpha Vantage is unavailable or rate-limited

See `docs/STRATEGY_SPEC.md` for the canonical strategy definition.

## Quick start

### 1) Create environment

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2) Configure secrets

```bash
cp .env.example .env
```

Set `ALPHA_VANTAGE_API_KEY` in `.env`.

### 3) Validate local setup

```bash
python main.py doctor
```

### 4) Initialize the tracked ETF universe

```bash
python initialize_tracked_funds.py --force
```

### 5) Run a review

```bash
python main.py
# or
python main.py review 2026-04-10
```

### 6) Inspect the latest saved run

```bash
python main.py latest
```

## Key outputs

- `output/leaders.csv`
- `output/leaders.json`
- `output/reports/manual_review_*.txt`
- `output/reports/manual_review_*.json`
- SQLite state in `data/fund_leaders.db`

## Key files

- `config.yaml` - sector, cadence, fallback, confirmation, and threshold config
- `initialize_tracked_funds.py` - ranks and stores the ETF universe per sector
- `fund_analyzer.py` - sector review orchestration and export flow
- `strategy_engine.py` - confirmation/stateful recommendation logic
- `manual_report.py` - advisory/manual-trading report generation
- `holdings_fetcher.py` - Alpha Vantage holdings fetch + stale-safe cache
- `db_manager.py` - SQLite schema and persisted run/strategy state
- `docs/STRATEGY_SPEC.md` - actual in-repo strategy spec

## Production caveat

Alpha Vantage is acceptable for prototyping and light personal workflow use, but not ideal for institutional production. The code now degrades more safely via cached holdings, yet a better data provider is still the right next upgrade.
