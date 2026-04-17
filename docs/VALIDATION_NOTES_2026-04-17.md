# Validation Notes — 2026-04-17

## Scope
Validated the workflow-separation and Alpha Vantage budget-ledger changes introduced in commit `118f47e`.

## What was validated

### 1. Doctor is quota-safe
- `python3 main.py doctor`
- Result: no Alpha Vantage ledger consumption
- Observed: `consumed=0`, `blocked=0` before/after doctor

### 2. Review is hard cache-only in practice
- `python3 main.py review`
- Result: completed successfully without live Alpha Vantage calls
- Observed: review run showed `attempted=0`, `blocked=0`, `consumed=0`
- Conclusion: review is operationally cache-only, not just architecturally intended to be

### 3. Refresh is the live holdings spender
- `python3 main.py refresh 2026-04-17 batch_b`
- Result: refreshed only batch_b sectors and consumed Alpha Vantage quota as expected
- Observed: `attempted=17`, `successful=17`, `blocked=0`; persistent ledger moved to `consumed=17`
- Conclusion: refresh is the intended normal live-call workflow

### 4. Maintenance gate works
- `python3 initialize_tracked_funds.py --force`
- Result: refused outside first Sunday
- Exit code: `2`
- Ledger unchanged by refusal

### 5. Maintenance override works, but timing matters
- `python3 initialize_tracked_funds.py --force --allow-outside-maintenance`
- Result: tracked funds updated and selection metadata refreshed
- Observed: maintenance started with only 8 calls of daily budget remaining after refresh
- Outcome: early provider rate limiting; maintenance summary showed `attempted=2`, `successful=1`, `failed=1`, `blocked=43`, `rate_limited=True`
- Consequence: most sector re-ranking degraded into `manifest_fallback_return` scoring rather than full live performance scoring

### 6. Docs were aligned to current config
- Corrected 10-sector / 5+5 wording to match current reality:
  - 9 active sectors
  - `batch_a = 5 sectors`
  - `batch_b = 4 sectors`

## Operational conclusion
The workflow separation and persistent ledger changes are validated and working as intended.

- `doctor` = safe
- `review` = safe/cache-only
- `refresh` = intended live spender
- `maintenance` = correctly gated
- `maintenance override` = works, but should not be run late in the day after refresh if clean live scoring is desired

## Recommended run order
Best-practice operating sequence:

1. **First Sunday maintenance first** (start of fresh quota day)
   - `python3 initialize_tracked_funds.py --force`
2. **Do not run refresh before maintenance on that day**
3. After maintenance completes, run review if desired
   - `python3 main.py review`
4. Resume normal daily refresh cadence afterward
   - `python3 main.py refresh`

## Caution
If maintenance is run after refresh has already consumed a meaningful portion of the day's Alpha Vantage budget, provider rate limiting may cause maintenance to fall back mostly to manifest-based ranking. That makes the resulting tracked ETF universe operationally usable, but not the cleanest basis for strategic reselection.
