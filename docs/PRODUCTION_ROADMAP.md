# Production Roadmap

## Phase 1 - Completed in this repo

- Replace fake keyword-based fund selection with curated manifest-driven fund universe
- Replace simulated 3Y performance with provider-based live calculation + deterministic fallback
- Add database migrations for tracked-fund ranking metadata
- Tighten config/env/setup flow
- Align README and setup docs with actual code path

## Phase 2 - Next high-value work

1. **Provider upgrade**
   - Replace Alpha Vantage holdings/performance endpoints with institutional-grade provider(s)
   - Add provider health checks and explicit stale-data monitoring

2. **Data quality controls**
   - Persist per-run source timestamps and provider response status
   - Add sector coverage completeness checks
   - Add “insufficient evidence” outcomes when too few funds/holdings are available

3. **Testing**
   - Add unit tests for fund ranking, leader identification, and DB migrations
   - Add integration tests using recorded provider fixtures

4. **Operations**
   - Add structured JSON logging
   - Add retry/backoff metrics and alerting
   - Add scheduled weekly refresh for tracked funds and daily analysis runbooks

5. **Security and deployment**
   - Add secrets management examples for hosted deployment
   - Put dashboard behind auth
   - Package app with Docker / compose or equivalent

## Phase 3 - Institutional-grade enhancements

- Multi-provider reconciliation for holdings accuracy
- Factor-adjusted leader scoring instead of simple consensus/weight ranking only
- Sector taxonomy versioning and governance workflow
- Historical attribution and confidence scoring per leader
- API service layer for dashboard and downstream consumers
