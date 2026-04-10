# ETF-Only Sector Leadership Strategy Spec

## Objective

This repository is an **advisory/manual-trading sector rotation planner**.

The system reviews a curated list of sector ETFs, inspects their stored holdings snapshots, and recommends one position per sector:

- the **confirmed stock leader** within that sector, or
- the configured **sector ETF fallback** when no stock leader meets the rules.

It does **not** place live orders.

## Operating model

### Universe and budget

- **10 sectors total**
- **5 tracked ETFs per sector**
- **25 API calls/day budget target**
- therefore the refresh workflow is split into **2 alternating batches of 5 sectors each**

### Cadence

- **Holdings snapshot refresh:** daily, alternating `batch_a` / `batch_b`
- **Strategy review:** weekly, cache-first across all 10 sectors
- **Action cadence:** monthly
- **Override:** if a significant change occurs, a confirmed switch may be actioned before month-end

## Refresh vs review

### Refresh holdings snapshots

Purpose: update local ETF holdings cache only.

- refreshes 5 sectors per day
- refreshes up to 25 ETF snapshots per run
- uses provider order from config (`fmp`, then `cache`, then `alpha_vantage` by default)
- stores holdings snapshots to local cache for later review

### Review strategy

Purpose: evaluate all sectors from the latest stored snapshots.

- reviews all 10 sectors every run
- should primarily use cached holdings snapshots
- does **not** require live ETF calls to produce a review
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
