# Fund Leader Tracker

Production-oriented research workflow for identifying sector leaders from the top holdings of curated thematic and sector ETFs.

## What changed

This repo no longer relies on fake keyword-to-fund mappings or hash-based simulated performance.

Instead it now uses:
- a versioned **curated fund universe** in `fund_universe.yaml`
- provider-based fund ranking in `data_providers.py`
- live 3-year annualized return calculation via Alpha Vantage monthly adjusted data when available
- deterministic manifest fallback scores when live ranking data is unavailable or rate-limited
- tracked-fund initialization stored in SQLite before daily analysis

That makes the current implementation production-credible even though it still uses Alpha Vantage as the live data source and still needs a stronger institutional data provider for full production deployment.

## Current architecture

1. `initialize_tracked_funds.py`
   - ranks each sector's curated candidate fund universe
   - stores the top tracked funds in SQLite
   - prefers live 3Y annualized returns from Alpha Vantage
   - falls back to manifest-defined ranking metadata if needed

2. `main.py`
   - loads tracked funds from SQLite
   - fetches ETF holdings for those funds
   - identifies the most commonly/high-conviction company leader per sector
   - stores results and exports CSV/JSON

3. `dashboard.py`
   - reads SQLite and shows current/historical leaders

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

### 4) Initialize tracked funds

```bash
python initialize_tracked_funds.py --force
```

### 5) Run analysis

```bash
python main.py
```

### 6) Launch dashboard

```bash
streamlit run dashboard.py
```

## Important operating notes

- `initialize_tracked_funds.py` should be rerun whenever you want to refresh the tracked fund list.
- `main.py` assumes tracked funds already exist unless `allow_uninitialized_sector_fallback` is enabled in `config.yaml`.
- Alpha Vantage free-tier limits are restrictive. For true production deployment, replace the performance/holdings providers with institutional-grade data sources.

## Repo guide

- `data_providers.py` - ranking providers and curated-universe loader
- `fund_universe.yaml` - explicit sector fund candidates
- `initialize_tracked_funds.py` - tracked-fund bootstrap job
- `holdings_fetcher.py` - holdings and quote retrieval
- `fund_analyzer.py` - analysis orchestration
- `db_manager.py` - SQLite schema and migrations
- `docs/PRODUCTION_ROADMAP.md` - next implementation phases

## Documentation

- `docs/PRODUCTION_ROADMAP.md`
- `QUICK_START.md`
- `DEPLOYMENT_GUIDE.md`
- `DASHBOARD_GUIDE.md`
- `SCHEDULING_GUIDE.md`
