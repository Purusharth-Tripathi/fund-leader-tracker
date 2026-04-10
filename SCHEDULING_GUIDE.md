# Fund Leader Tracker - Refresh & Review Scheduling Guide

This planner now uses a **staged refresh + cache-first review** operating model so it behaves cleanly under the Alpha Vantage free tier.

## Core schedule

- **10 sectors total**
- **5 ETFs tracked per sector**
- **25 calls/day budget**
- **Refresh cadence:** daily alternating batches of 5 sectors
- **Review cadence:** weekly using stored holdings snapshots for all 10 sectors
- **Action cadence:** monthly manual execution window

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

This review is cache-first and intended to work even when no live calls are made during the review run.

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

## Why this model fits the free tier

A full live review of all 10 sectors would require roughly 50 ETF holdings calls.

The staged model avoids that:

- daily refresh updates only **25 ETF snapshots max**
- weekly review reads from stored cache across **all 10 sectors**
- stale data remains visible through freshness reporting instead of forcing live fetches

## Operational advice

- Prefer `FMP_API_KEY` when available; it remains the first live holdings provider.
- Keep `ALPHA_VANTAGE_API_KEY` configured as fallback only.
- If you skip refreshes, the review will still run, but stale or missing sectors will be flagged explicitly.
- Do not treat the output as auto-trading instructions; the workflow is advisory/manual only.
