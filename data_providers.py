"""Production-oriented data providers for fund selection and performance."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import logging
import math
import time

import requests
import yaml

logger = logging.getLogger(__name__)


# Canonical workflow identifiers. Anything that touches Alpha Vantage must be
# tagged with one of these so the persistent ledger can attribute usage.
WORKFLOW_REFRESH = "refresh"
WORKFLOW_REVIEW = "review"
WORKFLOW_MAINTENANCE = "maintenance"
WORKFLOW_MANUAL_DIAGNOSTIC = "manual_diagnostic"
WORKFLOW_MANUAL_REPORT = "manual_report"


class AlphaVantageBudgetLedger:
    """Persistent daily quota gate for Alpha Vantage calls.

    The ledger is the single place that says "yes, you may spend one call" or
    "no, you're blocked". It records every decision to SQLite so the daily
    budget is enforced across workflows and across process restarts.

    Typical use:

        allowed, reason = ledger.try_consume('ETF_PROFILE', symbol='XLK')
        if allowed:
            payload = do_the_http_call()
            ledger.record_outcome(payload is not None, note='...')
        else:
            # call was already recorded as blocked with reason
            ...
    """

    BLOCK_REASON_LIVE_DISABLED = "workflow_disallows_live_calls"
    BLOCK_REASON_NO_API_KEY = "alpha_vantage_api_key_not_configured"
    BLOCK_REASON_DAILY_BUDGET = "daily_budget_exhausted"
    BLOCK_REASON_RATE_LIMIT = "rate_limit_signalled_by_provider"

    def __init__(
        self,
        db,
        workflow: str,
        daily_budget: int,
        live_calls_allowed: bool,
        api_key_present: bool = True,
        today: Optional[date] = None,
    ):
        self.db = db
        self.workflow = workflow
        self.daily_budget = max(int(daily_budget or 0), 0)
        self.live_calls_allowed = bool(live_calls_allowed)
        self.api_key_present = bool(api_key_present)
        self._today = today or datetime.now().date()
        self.attempted = 0  # calls dispatched in this process
        self.blocked = 0    # calls blocked in this process
        self.successful = 0
        self.failed = 0
        self.rate_limited = False
        self._pending_call: Optional[Tuple[str, Optional[str]]] = None

    @property
    def today_key(self) -> str:
        return self._today.isoformat()

    def consumed_today(self) -> int:
        return self.db.count_alpha_vantage_calls_for_date(self.today_key, status='consumed')

    def remaining_today(self) -> int:
        if self.daily_budget <= 0:
            return 0
        return max(self.daily_budget - self.consumed_today(), 0)

    def try_consume(self, function: str, symbol: Optional[str] = None) -> Tuple[bool, str]:
        """Reserve one call against the budget.

        On return, if allowed the caller MUST call record_outcome() exactly
        once. If blocked, the gate has already written the block to the
        ledger and the caller must not issue the HTTP request.
        """
        if self._pending_call is not None:
            logger.warning(
                "AlphaVantageBudgetLedger: previous call was not recorded before a new try_consume(%s)",
                function,
            )
            self._pending_call = None

        if not self.live_calls_allowed:
            self._record_blocked(function, symbol, self.BLOCK_REASON_LIVE_DISABLED)
            return False, self.BLOCK_REASON_LIVE_DISABLED

        if not self.api_key_present:
            self._record_blocked(function, symbol, self.BLOCK_REASON_NO_API_KEY)
            return False, self.BLOCK_REASON_NO_API_KEY

        if self.rate_limited:
            self._record_blocked(function, symbol, self.BLOCK_REASON_RATE_LIMIT)
            return False, self.BLOCK_REASON_RATE_LIMIT

        if self.daily_budget and self.consumed_today() >= self.daily_budget:
            self._record_blocked(function, symbol, self.BLOCK_REASON_DAILY_BUDGET)
            return False, self.BLOCK_REASON_DAILY_BUDGET

        self._pending_call = (function, symbol)
        return True, "ok"

    def record_outcome(self, success: bool, note: Optional[str] = None) -> None:
        if self._pending_call is None:
            logger.warning("AlphaVantageBudgetLedger.record_outcome() called without a pending try_consume")
            return
        function, symbol = self._pending_call
        self._pending_call = None
        self.attempted += 1
        if success:
            self.successful += 1
            outcome = "success"
        else:
            self.failed += 1
            outcome = "failure"
        self.db.record_alpha_vantage_call(
            call_date=self.today_key,
            workflow=self.workflow,
            function=function,
            symbol=symbol,
            status="consumed",
            outcome=outcome,
            note=note,
        )

    def mark_rate_limited(self, note: Optional[str] = None) -> None:
        """Signal that the provider rejected the last call with a rate-limit note.

        Once set, the ledger blocks all further live calls in this process to
        avoid grinding through a depleted quota window.
        """
        self.rate_limited = True
        if note:
            logger.warning("Alpha Vantage rate limit reached: %s", note)

    def _record_blocked(self, function: str, symbol: Optional[str], reason: str) -> None:
        self.blocked += 1
        self.db.record_alpha_vantage_call(
            call_date=self.today_key,
            workflow=self.workflow,
            function=function,
            symbol=symbol,
            status="blocked",
            outcome=reason,
            note=None,
        )

    def run_summary(self) -> Dict[str, Any]:
        return {
            "workflow": self.workflow,
            "live_calls_allowed": self.live_calls_allowed,
            "api_key_present": self.api_key_present,
            "daily_budget": self.daily_budget,
            "consumed_today": self.consumed_today(),
            "remaining_today": self.remaining_today(),
            "attempted_this_run": self.attempted,
            "blocked_this_run": self.blocked,
            "successful_this_run": self.successful,
            "failed_this_run": self.failed,
            "rate_limited": self.rate_limited,
        }


@dataclass
class FundCandidate:
    symbol: str
    name: str
    category: str = "ETF"
    rationale: str = ""
    baseline_score: float = 0.0
    fallback_return_3y: Optional[float] = None


@dataclass
class FundSelectionResult:
    symbol: str
    name: str
    category: str
    annualized_return_3y: Optional[float]
    score_used: float
    ranking_source: str
    rationale: str


class FundUniverseRepository:
    """Loads the versioned fund universe manifest used for sector coverage."""

    def __init__(self, manifest_path: str = "fund_universe.yaml"):
        self.manifest_path = Path(manifest_path)
        self._manifest: Optional[Dict[str, Any]] = None

    def load(self) -> Dict[str, Any]:
        if self._manifest is None:
            with self.manifest_path.open("r", encoding="utf-8") as handle:
                self._manifest = yaml.safe_load(handle) or {}
        return self._manifest

    def get_sector_candidates(self, sector_name: str) -> List[FundCandidate]:
        manifest = self.load()
        sectors = manifest.get("sectors", [])
        for sector in sectors:
            if sector.get("name") == sector_name:
                return [FundCandidate(**candidate) for candidate in sector.get("fund_candidates", [])]
        return []

    def get_all_sectors(self) -> List[Dict[str, Any]]:
        return self.load().get("sectors", [])


class AlphaVantageClient:
    """Thin client around Alpha Vantage with conservative retries.

    When a budget ledger is provided, every live call is gated by
    ``ledger.try_consume``. The client will not issue the HTTP request if the
    ledger refuses, which is how per-workflow live-call rules and the daily
    budget are enforced.
    """

    def __init__(
        self,
        api_key: str,
        timeout: int = 20,
        verify_ssl: bool = True,
        retry_attempts: int = 3,
        retry_delay: int = 5,
        ledger: Optional["AlphaVantageBudgetLedger"] = None,
    ):
        self.api_key = api_key
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.base_url = "https://www.alphavantage.co/query"
        self.session = requests.Session()
        self.ledger = ledger

    def _get(self, params: Dict[str, str]) -> Optional[Dict[str, Any]]:
        function = params.get("function", "UNKNOWN")
        symbol = params.get("symbol")
        if self.ledger is not None:
            allowed, reason = self.ledger.try_consume(function, symbol=symbol)
            if not allowed:
                logger.info("Alpha Vantage call blocked by ledger (%s/%s): %s", function, symbol, reason)
                return None

        payload: Optional[Dict[str, Any]] = None
        note: Optional[str] = None
        rate_limited = False
        try:
            for attempt in range(1, self.retry_attempts + 1):
                try:
                    response = self.session.get(
                        self.base_url,
                        params={**params, "apikey": self.api_key},
                        timeout=self.timeout,
                        verify=self.verify_ssl,
                    )
                    response.raise_for_status()
                    data = response.json()
                    if any(key in data for key in ("Error Message", "Information", "Note")):
                        logger.warning("Alpha Vantage returned non-data response for %s: %s", params, data)
                        note = str(data.get("Information") or data.get("Note") or data.get("Error Message") or "")
                        if "rate limit" in note.lower():
                            rate_limited = True
                        payload = None
                        break
                    payload = data
                    break
                except requests.RequestException as exc:
                    note = f"request_error: {exc}"
                    logger.warning("Alpha Vantage request failed on attempt %s/%s: %s", attempt, self.retry_attempts, exc)
                    if attempt == self.retry_attempts:
                        payload = None
                        break
                    time.sleep(self.retry_delay)
            return payload
        finally:
            if self.ledger is not None:
                if rate_limited:
                    self.ledger.mark_rate_limited(note)
                self.ledger.record_outcome(success=payload is not None, note=note)

    def get_monthly_adjusted_series(self, symbol: str) -> Optional[Dict[str, Any]]:
        return self._get({"function": "TIME_SERIES_MONTHLY_ADJUSTED", "symbol": symbol})


class AlphaVantagePerformanceProvider:
    """Computes annualized 3Y returns from monthly adjusted close series."""

    def __init__(self, client: AlphaVantageClient):
        self.client = client

    def get_annualized_return_3y(self, symbol: str) -> Optional[float]:
        payload = self.client.get_monthly_adjusted_series(symbol)
        if not payload:
            return None

        series = payload.get("Monthly Adjusted Time Series") or {}
        if not series:
            return None

        observations = []
        for date_str, values in series.items():
            try:
                observations.append((datetime.strptime(date_str, "%Y-%m-%d"), float(values["5. adjusted close"])))
            except (KeyError, ValueError):
                continue

        observations.sort(key=lambda item: item[0])
        if len(observations) < 24:
            return None

        end_date, end_price = observations[-1]
        target_date = end_date - timedelta(days=365 * 3)

        start_obs = min(observations, key=lambda item: abs((item[0] - target_date).days))
        start_date, start_price = start_obs
        if start_price <= 0 or end_price <= 0:
            return None

        years = max((end_date - start_date).days / 365.25, 1.0)
        annualized = (math.pow(end_price / start_price, 1 / years) - 1) * 100
        return round(annualized, 4)


class FundSelectionService:
    """Ranks a curated fund universe using live returns when available."""

    def __init__(self, universe_repo: FundUniverseRepository, performance_provider: Optional[AlphaVantagePerformanceProvider] = None):
        self.universe_repo = universe_repo
        self.performance_provider = performance_provider

    def rank_sector_funds(self, sector_name: str, top_n: int = 5) -> List[FundSelectionResult]:
        candidates = self.universe_repo.get_sector_candidates(sector_name)
        ranked: List[FundSelectionResult] = []

        for candidate in candidates:
            live_return = None
            if self.performance_provider:
                live_return = self.performance_provider.get_annualized_return_3y(candidate.symbol)

            if live_return is not None:
                score = live_return
                source = "alpha_vantage_monthly_adjusted"
            elif candidate.fallback_return_3y is not None:
                score = candidate.fallback_return_3y
                source = "manifest_fallback_return"
            else:
                score = candidate.baseline_score
                source = "manifest_baseline_score"

            ranked.append(FundSelectionResult(
                symbol=candidate.symbol,
                name=candidate.name,
                category=candidate.category,
                annualized_return_3y=live_return,
                score_used=score,
                ranking_source=source,
                rationale=candidate.rationale,
            ))

        ranked.sort(key=lambda item: item.score_used, reverse=True)
        return ranked[:top_n]
