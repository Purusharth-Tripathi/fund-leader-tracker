"""Fetch holdings and lightweight market data for Fund Leader Tracker."""
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

import requests

from data_providers import AlphaVantageBudgetLedger, FundUniverseRepository
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

    DEFAULT_PROVIDER_ORDER = ('cache', 'alpha_vantage')
    STALE_AFTER_HOURS_MULTIPLIER = 2

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
        ledger: Optional[AlphaVantageBudgetLedger] = None,
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
        self.ledger = ledger
        self.alpha_vantage_quota_exhausted = False
        self.last_rate_limit_note: Optional[str] = None
        os.makedirs(self.cache_directory, exist_ok=True)

    def _normalize_provider_order(self, provider_order: Optional[Sequence[str]]) -> Tuple[str, ...]:
        normalized = []
        for provider in (provider_order or self.DEFAULT_PROVIDER_ORDER):
            name = str(provider).strip().lower()
            if name and name not in normalized:
                normalized.append(name)
        return tuple(normalized or self.DEFAULT_PROVIDER_ORDER)

    def _request(self, params: Dict[str, str], timeout: int = 15) -> Optional[Dict]:
        function = params.get('function', 'UNKNOWN')
        symbol = params.get('symbol')
        if self.ledger is not None:
            allowed, reason = self.ledger.try_consume(function, symbol=symbol)
            if not allowed:
                logger.info(
                    'Alpha Vantage call blocked by ledger (%s/%s): %s',
                    function, symbol, reason,
                )
                if reason == AlphaVantageBudgetLedger.BLOCK_REASON_DAILY_BUDGET:
                    self.alpha_vantage_quota_exhausted = True
                    self.last_rate_limit_note = 'daily budget exhausted (persistent ledger)'
                elif reason == AlphaVantageBudgetLedger.BLOCK_REASON_RATE_LIMIT:
                    self.alpha_vantage_quota_exhausted = True
                return None

        payload: Optional[Dict] = None
        note: Optional[str] = None
        rate_limited = False
        try:
            for attempt in range(1, self.retry_attempts + 1):
                try:
                    response = requests.get(
                        self.base_url,
                        params={**params, 'apikey': self.api_key},
                        timeout=timeout,
                        verify=self.verify_ssl,
                    )
                    response.raise_for_status()
                    data = response.json()
                    if 'Error Message' in data or 'Information' in data or 'Note' in data:
                        logger.warning('API non-data response for %s: %s', params, data)
                        note = str(
                            data.get('Information') or data.get('Note') or data.get('Error Message') or ''
                        )
                        if note and 'rate limit' in note.lower():
                            self.alpha_vantage_quota_exhausted = True
                            self.last_rate_limit_note = note
                            rate_limited = True
                        payload = None
                        break
                    payload = data
                    break
                except requests.exceptions.RequestException as exc:
                    note = f'request_error: {exc}'
                    logger.warning('Request failed for %s on attempt %s/%s: %s', params, attempt, self.retry_attempts, exc)
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

    def _coerce_timestamp(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except (TypeError, ValueError):
            logger.warning('Invalid timestamp value: %s', value)
            return None

    def _freshness_label(self, age_hours: Optional[float]) -> str:
        if age_hours is None:
            return 'unknown'
        if age_hours <= self.cache_ttl_hours:
            return 'fresh'
        if age_hours <= self.cache_ttl_hours * self.STALE_AFTER_HOURS_MULTIPLIER:
            return 'stale'
        return 'very_stale'

    def _build_freshness_metadata(self, symbol: str, cached_at: Optional[str], data_status: str, source: str, holdings_count: int) -> Dict:
        cached_dt = self._coerce_timestamp(cached_at)
        age_hours = None
        age_days = None
        if cached_dt:
            age_seconds = max((datetime.utcnow() - cached_dt).total_seconds(), 0)
            age_hours = round(age_seconds / 3600, 2)
            age_days = round(age_hours / 24, 2)
        return {
            'symbol': symbol,
            'source': source,
            'data_status': data_status,
            'cached_at': cached_at,
            'age_hours': age_hours,
            'age_days': age_days,
            'freshness': self._freshness_label(age_hours),
            'ttl_hours': self.cache_ttl_hours,
            'holdings_count': holdings_count,
        }

    def _attach_freshness(self, symbol: str, result: Dict) -> Dict:
        payload = dict(result)
        payload['freshness'] = self._build_freshness_metadata(
            symbol=symbol,
            cached_at=payload.get('cached_at'),
            data_status=payload.get('data_status', 'unavailable'),
            source=payload.get('source', 'none'),
            holdings_count=len(payload.get('holdings', []) or []),
        )
        return payload

    def _build_cache_result(self, symbol: str, cached: Dict, status: str) -> Dict:
        return self._attach_freshness(symbol, {
            'holdings': cached.get('holdings', []),
            'data_status': status,
            'cached_at': cached.get('cached_at'),
            'source': cached.get('source', 'cache'),
        })

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
        return self._build_cache_result(symbol, cached, 'fresh_cache' if is_fresh else 'stale_cache')

    def _fetch_alpha_vantage_holdings(self, symbol: str) -> Optional[Dict]:
        if self.ledger is not None and not self.ledger.live_calls_allowed:
            logger.info(
                'Skipping Alpha Vantage holdings for %s because current workflow disallows live calls',
                symbol,
            )
            return None
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
            cached_at = datetime.utcnow().isoformat()
            self._write_cached_holdings(symbol, holdings, source='alpha_vantage_etf_profile')
            return self._attach_freshness(symbol, {
                'holdings': holdings,
                'data_status': 'live',
                'cached_at': cached_at,
                'source': 'alpha_vantage_etf_profile',
            })
        return None

    def get_fund_holdings(self, symbol, mode: str = 'auto'):
        normalized_mode = (mode or 'auto').strip().lower()
        stale_cache_result = None
        providers = self.holdings_provider_order
        if normalized_mode == 'cache_only':
            providers = tuple(provider for provider in self.holdings_provider_order if provider == 'cache') or ('cache',)
        elif self.ledger is not None and not self.ledger.live_calls_allowed:
            # Hard safety: even if caller asked for 'auto', a workflow that
            # forbids live calls must not reach Alpha Vantage. Downgrade the
            # provider list to cache-only for this call.
            providers = tuple(provider for provider in self.holdings_provider_order if provider == 'cache') or ('cache',)
            normalized_mode = 'cache_only'
        for provider in providers:
            if provider == 'cache':
                cache_result = self._get_cached_holdings_result(symbol, require_fresh=False)
                if cache_result:
                    if cache_result['data_status'] == 'fresh_cache':
                        return cache_result
                    stale_cache_result = stale_cache_result or cache_result
                continue
            if provider in {'alpha_vantage', 'alphavantage', 'av'}:
                result = self._fetch_alpha_vantage_holdings(symbol)
            else:
                logger.warning('Unknown holdings provider configured: %s', provider)
                result = None
            if result and result.get('holdings'):
                return result

        if stale_cache_result:
            return stale_cache_result
        unavailable_status = 'cache_miss' if normalized_mode == 'cache_only' else 'unavailable'
        return self._attach_freshness(symbol, {'holdings': [], 'data_status': unavailable_status, 'cached_at': None, 'source': 'none'})

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

    def batch_fetch_holdings(self, fund_symbols: List[str], mode: str = 'auto'):
        all_holdings = {}
        statuses = {}
        total = len(fund_symbols)
        self.alpha_vantage_quota_exhausted = False
        self.last_rate_limit_note = None
        for i, symbol in enumerate(fund_symbols, 1):
            print_progress(i, total, f'Fetching holdings for {symbol}')
            result = self.get_fund_holdings(symbol, mode=mode)
            holdings = result.get('holdings', [])
            statuses[symbol] = result.get('freshness', {})
            if holdings:
                all_holdings[symbol] = holdings
            if self.alpha_vantage_quota_exhausted:
                logger.warning('Stopping holdings batch early after Alpha Vantage quota exhaustion on %s', symbol)
                break
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
