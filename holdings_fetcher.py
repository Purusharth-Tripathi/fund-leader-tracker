"""Fetch holdings and lightweight market data for Fund Leader Tracker."""
import json
import logging
import os
import time
from typing import Dict, List, Optional

import requests

from data_providers import FundUniverseRepository
from utils import print_progress

logger = logging.getLogger(__name__)

COMPANY_NAMES_CACHE: Dict[str, str] = {}
try:
    cache_file = os.path.join(os.path.dirname(__file__), 'company_names.json')
    if os.path.exists(cache_file):
        with open(cache_file, 'r', encoding='utf-8') as f:
            COMPANY_NAMES_CACHE = json.load(f)
except Exception as e:
    logger.warning(f"Could not load company names cache: {e}")


class HoldingsFetcher:
    """Fetches fund holdings data from Alpha Vantage API."""

    def __init__(self, api_key, requests_per_minute=5, verify_ssl=True, retry_attempts=3, retry_delay=5):
        self.api_key = api_key
        self.base_url = "https://www.alphavantage.co/query"
        self.requests_per_minute = requests_per_minute
        self.verify_ssl = verify_ssl
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.request_delay = max(60 / max(requests_per_minute, 1), 0)
        self.universe_repo = FundUniverseRepository(os.path.join(os.path.dirname(__file__), 'fund_universe.yaml'))

    def _request(self, params: Dict[str, str], timeout: int = 15) -> Optional[Dict]:
        for attempt in range(1, self.retry_attempts + 1):
            try:
                response = requests.get(self.base_url, params={**params, 'apikey': self.api_key}, timeout=timeout, verify=self.verify_ssl)
                response.raise_for_status()
                data = response.json()
                if 'Error Message' in data or 'Information' in data or 'Note' in data:
                    logger.warning("API non-data response for %s: %s", params, data)
                    return None
                return data
            except requests.exceptions.RequestException as exc:
                logger.warning("Request failed for %s on attempt %s/%s: %s", params, attempt, self.retry_attempts, exc)
                if attempt == self.retry_attempts:
                    return None
                time.sleep(self.retry_delay)
        return None

    def get_etf_profile(self, symbol):
        return self._request({'function': 'ETF_PROFILE', 'symbol': symbol})

    def get_company_name(self, symbol):
        if symbol in COMPANY_NAMES_CACHE:
            return COMPANY_NAMES_CACHE[symbol]
        return symbol

    def get_fund_holdings(self, symbol):
        profile = self.get_etf_profile(symbol)
        if not profile:
            return []

        holdings = []
        try:
            for holding in profile.get('holdings', []):
                stock_symbol = holding.get('symbol', 'N/A')
                company_name = holding.get('name') or self.get_company_name(stock_symbol)
                weight = float(holding.get('weight', 0)) * 100
                holdings.append({'symbol': stock_symbol, 'name': company_name, 'weight': weight})
        except (TypeError, ValueError, KeyError) as e:
            logger.error(f"Error parsing holdings for {symbol}: {e}")
        return holdings

    def get_quote(self, symbol):
        data = self._request({'function': 'GLOBAL_QUOTE', 'symbol': symbol})
        return data.get('Global Quote') if data else None

    def search_funds_by_keywords(self, keywords, sector_name=None):
        """Fallback discovery sourced from the curated universe manifest, not hardcoded samples."""
        manifest = self.universe_repo.get_all_sectors()
        results = []

        if sector_name:
            sector_candidates = self.universe_repo.get_sector_candidates(sector_name)
            return [candidate.symbol for candidate in sector_candidates]

        keyword_set = {keyword.lower() for keyword in keywords}
        for sector in manifest:
            haystack = {sector.get('name', '').lower()}
            haystack.update(word.lower() for word in sector.get('keywords', []) if isinstance(word, str))
            if keyword_set & haystack:
                results.extend(candidate.symbol for candidate in self.universe_repo.get_sector_candidates(sector['name']))

        # de-duplicate while preserving order
        seen = set()
        deduped = []
        for symbol in results:
            if symbol not in seen:
                seen.add(symbol)
                deduped.append(symbol)
        return deduped

    def batch_fetch_holdings(self, fund_symbols: List[str]):
        all_holdings = {}
        total = len(fund_symbols)
        for i, symbol in enumerate(fund_symbols, 1):
            print_progress(i, total, f"Fetching holdings for {symbol}")
            holdings = self.get_fund_holdings(symbol)
            if holdings:
                all_holdings[symbol] = holdings
            if i < total and self.request_delay:
                time.sleep(self.request_delay)
        return all_holdings

    def get_fund_performance(self, symbol):
        quote = self.get_quote(symbol)
        if not quote:
            return None
        try:
            return {
                'symbol': symbol,
                'price': float(quote.get('05. price', 0)),
                'change_percent': quote.get('10. change percent', '0%'),
                'volume': int(float(quote.get('06. volume', 0)))
            }
        except (ValueError, KeyError) as e:
            logger.error(f"Error parsing performance for {symbol}: {e}")
            return None
