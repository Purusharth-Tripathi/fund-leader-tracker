# Production Roadmap

## Phase 1 - Now implemented in this repo

- ETF-only sector leadership planning workflow
- documented in-repo strategy spec
- weekly review / monthly action operating model
- confirmation-based switching and significant-change override logic
- sector ETF fallback when no valid stock leader exists
- persisted sector recommendation state across runs
- manual advisory report export (text + JSON)
- stale-safe holdings cache for Alpha Vantage outages or rate limits

## Phase 2 - Next high-value work

1. **Provider upgrade**
   - replace Alpha Vantage holdings/performance endpoints with institutional-grade provider(s)
   - persist provider freshness timestamps and source audit fields per ETF

2. **Portfolio realism**
   - add configurable sector weights instead of equal-weight default
   - model transaction cost / tax friction before suggesting switches
   - add cash-handling rules for uncovered sectors

3. **Testing**
   - unit tests for strategy confirmation logic, fallback logic, and DB persistence
   - fixture-based integration tests for holdings snapshots and report generation

4. **Operations**
   - structured JSON logging
   - scheduled weekly review and monthly action runbooks
   - stale-cache warnings and data health dashboarding

5. **Manual broker workflow**
   - generate broker-ready order tickets for human review
   - optional future IBKR integration behind explicit manual approval gates

## Phase 3 - Institutional-grade enhancements

- multi-provider reconciliation for holdings accuracy
- confidence scoring and sector evidence quality metrics
- historical attribution of leader changes vs. realized performance
- API service layer for dashboard and downstream consumers
- authenticated dashboard and packaged deployment
