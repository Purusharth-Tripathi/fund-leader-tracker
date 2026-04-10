# Quick Start

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Set `ALPHA_VANTAGE_API_KEY` in `.env`.

## First-time bootstrap

```bash
python main.py doctor
python initialize_tracked_funds.py --force
```

## Daily run

```bash
python main.py
```

## Dashboard

```bash
streamlit run dashboard.py
```

## Reality check

The tracked fund list now comes from `fund_universe.yaml`, not fake keyword matching.
Live ranking uses Alpha Vantage monthly data when available; otherwise the manifest fallback ranking is used.
