"""Production-oriented data providers for fund selection and performance."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging
import math
import time

import requests
import yaml

logger = logging.getLogger(__name__)


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
    """Thin client around Alpha Vantage with conservative retries."""

    def __init__(self, api_key: str, timeout: int = 20, verify_ssl: bool = True, retry_attempts: int = 3, retry_delay: int = 5):
        self.api_key = api_key
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.base_url = "https://www.alphavantage.co/query"
        self.session = requests.Session()

    def _get(self, params: Dict[str, str]) -> Optional[Dict[str, Any]]:
        for attempt in range(1, self.retry_attempts + 1):
            try:
                response = self.session.get(self.base_url, params={**params, "apikey": self.api_key}, timeout=self.timeout, verify=self.verify_ssl)
                response.raise_for_status()
                payload = response.json()
                if any(key in payload for key in ("Error Message", "Information", "Note")):
                    logger.warning("Alpha Vantage returned non-data response for %s: %s", params, payload)
                    return None
                return payload
            except requests.RequestException as exc:
                logger.warning("Alpha Vantage request failed on attempt %s/%s: %s", attempt, self.retry_attempts, exc)
                if attempt == self.retry_attempts:
                    return None
                time.sleep(self.retry_delay)
        return None

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
