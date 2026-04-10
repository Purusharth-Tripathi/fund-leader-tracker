# ETF-Only Sector Leadership Strategy Spec

## Objective

This repository is now designed as an **advisory/manual-trading sector rotation planner**.

The system reviews a curated list of sector ETFs, inspects their underlying holdings, and recommends one position per sector:

- the **confirmed stock leader** within that sector, or
- the configured **sector ETF fallback** when no stock leader meets the rules.

It does **not** place live orders.

## Operating model

### Cadence

- **Review cadence:** weekly
- **Action cadence:** monthly
- **Override:** if a significant change occurs, a confirmed switch may be actioned before month-end

### Decision rules

For each sector:

1. Rank and track a curated ETF set.
2. Pull ETF holdings using Alpha Vantage when available.
3. Reuse cached holdings when the API is rate-limited or unavailable.
4. Aggregate company exposure across tracked ETFs.
5. Treat a company as a valid leader candidate only if it meets config thresholds:
   - minimum funds holding it
   - minimum prevalence across tracked ETFs
   - minimum average portfolio weight
6. Compare the current candidate with the previously active recommendation.
7. If the candidate changes, require confirmation across multiple reviews before switching.
8. Only switch on the monthly action window unless the move qualifies as a significant change.
9. If no valid stock leader exists, recommend the sector ETF fallback instead.

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

## Persistence

Each run stores:

- current top leader evidence
- per-sector active recommendation
- pending switch candidate and confirmation count
- run summary and portfolio plan
- manual review report paths

This lets the planner compare the current review with prior state across runs.

## Alpha Vantage / stale-safe behavior

Alpha Vantage free-tier limits are restrictive.

To keep the workflow usable:

- ETF holdings responses are cached on disk under `data/cache/`
- fresh cache is reused before hitting the API again
- stale cache is used as a fallback if live calls fail
- outputs explicitly label data status (`live`, `fresh_cache`, `stale_cache`, etc.)

## Future IBKR-ready manual workflow

This repo intentionally stops at **recommendation + report generation**.

A future manual-to-IBKR bridge could add:

1. broker account mapping for each sector sleeve
2. pre-trade compliance checks
3. order ticket export for manual upload/review
4. optional human-approved order staging via IBKR APIs

That future workflow should remain gated by an explicit manual approval step.
