# Deployment Guide

## Recommended deployment shape

For a small production deployment:
- Python 3.11+
- persistent volume for `data/`, `logs/`, and `output/`
- scheduled tracked-fund refresh (weekly or monthly)
- scheduled daily analysis job
- Streamlit dashboard behind basic authentication or private network access

## Environment variables

Use `.env` locally and secret management in hosted environments.
At minimum configure:
- `ALPHA_VANTAGE_API_KEY`
- `DATABASE_PATH`

## Suggested hosted pattern

- analysis job: cron / task scheduler
- dashboard: separate always-on service
- SMTP credentials: secret store only

## Production warning

Alpha Vantage is acceptable for prototyping and lightweight production experiments, but not ideal for institutional-grade holdings coverage, reliability, or SLA-backed operation. Plan to swap in a stronger provider via `data_providers.py` and `holdings_fetcher.py`.
