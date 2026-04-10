"""Fetch holdings and lightweight market data for Fund Leader Tracker."""
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

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
    logger.warning(f'Could not load company names cache: {e}')


class HoldingsFetcher:
    """Fetch ETF holdings with provider fallback and stale-safe disk cache."""

    DEFAULT_PROVIDER_ORDER = ('fmp', 'cache', 'alpha_vantage')

    def __init__(
        self,
        api_key,
        requests_per_minute=5,
        verify_ssl=True,
        retry_attempts=3,
        retry_delay=5,
        cache_directory='data/cache',
        cache_ttl_hours=168,
        holdings_provider_order: Optional[Sequence[str]] = None,
        fmp_api_key: Optional[str] = None,
        fmp_base_url: str = 'https://financialmodelingprep.com',
    ):
        self.api_key = api_key
        self.base_url = 'https://www.alphavantage.co/query'
        self.requests_per_minute = requests_per_minute
        self.verify_ssl = verify_ssl
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.request_delay = max(60 / max(requests_per_minute, 1), 0)
        self.universe_repo = FundUniverseRepository(os.path.join(os.path.dirname(__file__), 'fund_universe.yaml'))
        self.cache_directory = cache_directory
        self.cache_ttl_hours = cache_ttl_hours
        self.holdings_provider_order = self._normalize_provider_order(holdings_provider_order)
        self.fmp_api_key = fmp_api_key or os.getenv('FMP_API_KEY', '')
        self.fmp_base_url = fmp_base_url.rstrip('/')
        os.makedirs(self.cache_directory, exist_ok=True)

    def _normalize_provider_order(self, provider_order: Optional[Sequence[str]]) -> Tuple[str, ...]:
        normalized = []
        for provider in (provider_order or self.DEFAULT_PROVIDER_ORDER):
            name = str(provider).strip().lower()
            if name and name not in normalized:
                normalized.append(name)
        return tuple(normalized or self.DEFAULT_PROVIDER_ORDER)

    def _request(self, params: Dict[str, str], timeout: int = 15) -> Optional[Dict]:
        for attempt in range(1, self.retry_attempts + 1):
            try:
                response = requests.get(self.base_url, params={**params, 'apikey': self.api_key}, timeout=timeout, verify=self.verify_ssl)
                response.raise_for_status()
                data = response.json()
                if 'Error Message' in data or 'Information' in data or 'Note' in data:
                    logger.warning('API non-data response for %s: %s', params, data)
                    return None
                return data
            except requests.exceptions.RequestException as exc:
                logger.warning('Request failed for %s on attempt %s/%s: %s', params, attempt, self.retry_attempts, exc)
                if attempt == self.retry_attempts:
                    return None
                time.sleep(self.retry_delay)
        return None

    def _fmp_request(self, path: str, params: Optional[Dict[str, str]] = None, timeout: int = 20):
        if not self.fmp_api_key:
            return None
        request_params = {**(params or {}), 'apikey': self.fmp_api_key}
        url = f'{self.fmp_base_url}{path}'
        for attempt in range(1, self.retry_attempts + 1):
            try:
                response = requests.get(url, params=request_params, timeout=timeout, verify=self.verify_ssl)
                response.raise_for_status()
                data = response.json()
                if isinstance(data, dict) and any(key in data for key in ('Error Message', 'Information', 'Note', 'error')):
                    logger.warning('FMP non-data response for %s %s: %s', path, params, data)
                    return None
                return data
            except requests.exceptions.RequestException as exc:
                logger.warning('FMP request failed for %s on attempt %s/%s: %s', path, attempt, self.retry_attempts, exc)
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

    def _cache_path(self, symbol: str) -> str:
        return os.path.join(self.cache_directory, f'{symbol.upper()}_holdings.json')

    def _read_cached_holdings(self, symbol: str) -> Optional[Dict]:
        path = self._cache_path(symbol)
        if not os.path.exists(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                return json.load(handle)
        except Exception as exc:
            logger.warning('Failed reading holdings cache for %s: %s', symbol, exc)
            return None

    def _write_cached_holdings(self, symbol: str, holdings: List[Dict], source: str):
        payload = {
            'symbol': symbol,
            'cached_at': datetime.utcnow().isoformat(),
            'source': source,
            'holdings': holdings,
        }
        with open(self._cache_path(symbol), 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, indent=2)

    def _build_cache_result(self, cached: Dict, status: str) -> Dict:
        return {
            'holdings': cached.get('holdings', []),
            'data_status': status,
            'cached_at': cached.get('cached_at'),
            'source': cached.get('source', 'cache'),
        }

    def _get_cached_holdings_result(self, symbol: str, require_fresh: bool) -> Optional[Dict]:
        cached = self._read_cached_holdings(symbol)
        if not cached:
            return None
        try:
            cached_at = datetime.fromisoformat(cached['cached_at'])
        except (KeyError, TypeError, ValueError):
            logger.warning('Invalid cache timestamp for %s', symbol)
            return None

        is_fresh = datetime.utcnow() - cached_at <= timedelta(hours=self.cache_ttl_hours)
        if require_fresh and not is_fresh:
            return None
        return self._build_cache_result(cached, 'fresh_cache' if is_fresh else 'stale_cache')

    def _parse_fmp_weight(self, holding: Dict) -> float:
        raw_weight = holding.get('weightPercentage')
        if raw_weight is None:
            raw_weight = holding.get('weight')
        if raw_weight is None:
            raw_weight = holding.get('holdingPercent')
        value = float(raw_weight or 0)
        return value * 100 if value <= 1 else value

    def _parse_fmp_holdings(self, symbol: str, payload) -> List[Dict]:
        rows = payload if isinstance(payload, list) else payload.get('holdings', []) if isinstance(payload, dict) else []
        holdings = []
        for holding in rows:
            if not isinstance(holding, dict):
                continue
            stock_symbol = holding.get('asset') or holding.get('symbol') or holding.get('holdingSymbol') or 'N/A'
            company_name = holding.get('name') or holding.get('holdingName') or self.get_company_name(stock_symbol)
            try:
                parsed = {
                    'symbol': stock_symbol,
                    'name': company_name,
                    'weight': self._parse_fmp_weight(holding),
                }
                shares = holding.get('sharesNumber') or holding.get('shares') or holding.get('share')
                if shares not in (None, ''):
                    try:
                        parsed['shares'] = int(float(shares))
                    except (TypeError, ValueError):
                        pass
                holdings.append(parsed)
            except (TypeError, ValueError) as exc:
                logger.warning('Error parsing FMP holding for %s: %s | %s', symbol, exc, holding)
        return holdings

    def _fetch_fmp_holdings(self, symbol: str) -> Optional[Dict]:
        if not self.fmp_api_key:
            logger.info('Skipping FMP holdings for %s because FMP_API_KEY is not configured', symbol)
            return None

        candidate_requests = [
            ('/api/v3/etf-holder/{symbol}', {}),
            ('/stable/etf-holder', {'symbol': symbol}),
        ]
        for path_template, params in candidate_requests:
            path = path_template.format(symbol=symbol)
            payload = self._fmp_request(path, params=params)
            if not payload:
                continue
            holdings = self._parse_fmp_holdings(symbol, payload)
            if holdings:
                self._write_cached_holdings(symbol, holdings, source='fmp_etf_holdings')
                return {
                    'holdings': holdings,
                    'data_status': 'live',
                    'cached_at': datetime.utcnow().isoformat(),
                    'source': 'fmp_etf_holdings',
                }
        return None

    def _fetch_alpha_vantage_holdings(self, symbol: str) -> Optional[Dict]:
        if not self.api_key or self.api_key == 'your_api_key_here':
            logger.info('Skipping Alpha Vantage holdings for %s because ALPHA_VANTAGE_API_KEY is not configured', symbol)
            return None

        profile = self.get_etf_profile(symbol)
        if not profile:
            return None

        holdings = []
        try:
            for holding in profile.get('holdings', []):
                stock_symbol = holding.get('symbol', 'N/A')
                company_name = holding.get('name') or self.get_company_name(stock_symbol)
                weight = float(holding.get('weight', 0)) * 100
                parsed = {'symbol': stock_symbol, 'name': company_name, 'weight': weight}
                shares = holding.get('shares')
                if shares not in (None, ''):
                    try:
                        parsed['shares'] = int(float(shares))
                    except (TypeError, ValueError):
                        pass
                holdings.append(parsed)
        except (TypeError, ValueError, KeyError) as e:
            logger.error(f'Error parsing holdings for {symbol}: {e}')

        if holdings:
            self._write_cached_holdings(symbol, holdings, source='alpha_vantage_etf_profile')
            return {
                'holdings': holdings,
                'data_status': 'live',
                'cached_at': datetime.utcnow().isoformat(),
                'source': 'alpha_vantage_etf_profile',
            }
        return None

    def get_fund_holdings(self, symbol):
        stale_cache_result = None
        for provider in self.holdings_provider_order:
            if provider == 'cache':
                cache_result = self._get_cached_holdings_result(symbol, require_fresh=False)
                if cache_result:
                    if cache_result['data_status'] == 'fresh_cache':
                        return cache_result
                    stale_cache_result = stale_cache_result or cache_result
                continue
            if provider == 'fmp':
                result = self._fetch_fmp_holdings(symbol)
            elif provider in {'alpha_vantage', 'alphavantage', 'av'}:
                result = self._fetch_alpha_vantage_holdings(symbol)
            else:
                logger.warning('Unknown holdings provider configured: %s', provider)
                result = None
            if result and result.get('holdings'):
                return result

        if stale_cache_result:
            return stale_cache_result
        return {'holdings': [], 'data_status': 'unavailable', 'cached_at': None, 'source': 'none'}

    def get_quote(self, symbol):
        data = self._request({'function': 'GLOBAL_QUOTE', 'symbol': symbol})
        return data.get('Global Quote') if data else None

    def search_funds_by_keywords(self, keywords, sector_name=None):
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

        seen = set()
        deduped = []
        for symbol in results:
            if symbol not in seen:
                seen.add(symbol)
                deduped.append(symbol)
        return deduped

    def batch_fetch_holdings(self, fund_symbols: List[str]):
        all_holdings = {}
        statuses = {}
        total = len(fund_symbols)
        for i, symbol in enumerate(fund_symbols, 1):
            print_progress(i, total, f'Fetching holdings for {symbol}')
            result = self.get_fund_holdings(symbol)
            holdings = result.get('holdings', [])
            statuses[symbol] = {
                'data_status': result.get('data_status', 'unavailable'),
                'cached_at': result.get('cached_at'),
                'source': result.get('source'),
            }
            if holdings:
                all_holdings[symbol] = holdings
            if i < total and self.request_delay and result.get('data_status') == 'live':
                time.sleep(self.request_delay)
        return all_holdings, statuses

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
            logger.error(f'Error parsing performance for {symbol}: {e}')
            return None
