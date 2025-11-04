"""
Holdings Fetcher for Fund Leader Tracker
Fetches fund holdings data from Alpha Vantage API
"""
import requests
import time
import logging
import os
from utils import print_progress

logger = logging.getLogger(__name__)


class HoldingsFetcher:
    """Fetches fund holdings data from Alpha Vantage API"""

    def __init__(self, api_key, requests_per_minute=5, verify_ssl=False):
        """
        Initialize the Holdings Fetcher

        Args:
            api_key: Alpha Vantage API key
            requests_per_minute: API rate limit
            verify_ssl: Whether to verify SSL certificates
        """
        self.api_key = api_key
        self.base_url = "https://www.alphavantage.co/query"
        self.requests_per_minute = requests_per_minute
        self.verify_ssl = verify_ssl
        self.request_delay = 60 / requests_per_minute  # Delay between requests

    def get_etf_profile(self, symbol):
        """
        Get ETF profile information

        Args:
            symbol: ETF symbol (e.g., 'SPY')

        Returns:
            dict: ETF profile data or None if failed
        """
        params = {
            'function': 'ETF_PROFILE',
            'symbol': symbol,
            'apikey': self.api_key
        }

        try:
            response = requests.get(
                self.base_url,
                params=params,
                timeout=15,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            data = response.json()

            # Check for API errors
            if 'Error Message' in data:
                logger.error(f"API Error for {symbol}: {data['Error Message']}")
                return None
            elif 'Information' in data:
                logger.warning(f"API Rate limit message for {symbol}: {data['Information']}")
                return None
            elif 'Note' in data:
                logger.warning(f"API Note for {symbol}: {data['Note']}")
                return None

            logger.info(f"Successfully fetched profile for {symbol}")
            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error fetching profile for {symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching profile for {symbol}: {e}")
            return None

    def get_fund_holdings(self, symbol):
        """
        Get fund top holdings

        Args:
            symbol: Fund/ETF symbol

        Returns:
            list: List of holdings with symbol, name, and weight
        """
        # Note: Alpha Vantage free tier may not have full holdings data
        # This is a simplified implementation
        # In production, you might use additional data sources

        profile = self.get_etf_profile(symbol)
        if not profile:
            return []

        holdings = []
        try:
            # Extract holdings from profile if available
            if 'holdings' in profile:
                for holding in profile['holdings']:
                    holdings.append({
                        'symbol': holding.get('symbol', 'N/A'),
                        'name': holding.get('name', 'Unknown'),
                        'weight': float(holding.get('weight', 0))
                    })
            else:
                logger.warning(f"No holdings data found for {symbol}")

        except (KeyError, ValueError) as e:
            logger.error(f"Error parsing holdings for {symbol}: {e}")

        return holdings

    def get_quote(self, symbol):
        """
        Get stock quote using GLOBAL_QUOTE function

        Args:
            symbol: Stock symbol

        Returns:
            dict: Quote data or None if failed
        """
        params = {
            'function': 'GLOBAL_QUOTE',
            'symbol': symbol,
            'apikey': self.api_key
        }

        try:
            response = requests.get(
                self.base_url,
                params=params,
                timeout=15,
                verify=self.verify_ssl
            )
            data = response.json()

            if 'Global Quote' in data and data['Global Quote']:
                return data['Global Quote']
            else:
                logger.warning(f"No quote data for {symbol}")
                return None

        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
            return None

    def search_funds_by_keywords(self, keywords):
        """
        Search for funds matching sector keywords

        Note: This is a placeholder. In production, you would:
        1. Use a fund screening API
        2. Maintain a pre-populated list of sector funds
        3. Use a financial data provider with fund classification

        Args:
            keywords: List of keywords to search

        Returns:
            list: List of fund symbols
        """
        logger.info(f"Searching funds with keywords: {keywords}")

        # Placeholder implementation - returns sample funds
        # In production, implement actual fund search logic
        sample_funds = {
            'aerospace': ['ITA', 'XAR', 'PPA'],
            'defense': ['ITA', 'XAR', 'PPA'],
            'renewable': ['ICLN', 'TAN', 'QCLN', 'PBW', 'FAN'],
            'solar': ['TAN', 'RAYS'],
            'healthcare': ['XLV', 'VHT', 'IHI', 'IBB', 'XBI'],
            'biotech': ['IBB', 'XBI', 'BBH'],
            'automotive': ['CARZ', 'DRIV', 'IDRV'],
            'gold': ['GLD', 'GDX', 'GDXJ', 'IAU'],
            'silver': ['SLV', 'SILJ'],
            'consumer': ['XLP', 'VDC', 'FSTA'],
            'technology': ['XLK', 'VGT', 'QTEC', 'SKYY'],
            'AI': ['BOTZ', 'IRBO', 'ROBO'],
            'financial': ['XLF', 'VFH', 'KBE', 'KRE'],
            'fintech': ['FINX', 'IPAY'],
            'infrastructure': ['PAVE', 'IGF'],
            'real estate': ['VNQ', 'IYR', 'XLRE', 'SCHH']
        }

        found_funds = set()
        for keyword in keywords:
            keyword_lower = keyword.lower()
            for key, funds in sample_funds.items():
                if keyword_lower in key:
                    found_funds.update(funds)

        return list(found_funds)[:5]  # Return top 5

    def batch_fetch_holdings(self, fund_symbols):
        """
        Fetch holdings for multiple funds with rate limiting

        Args:
            fund_symbols: List of fund symbols

        Returns:
            dict: Dictionary mapping fund symbols to their holdings
        """
        all_holdings = {}
        total = len(fund_symbols)

        for i, symbol in enumerate(fund_symbols, 1):
            print_progress(i, total, f"Fetching holdings for {symbol}")

            holdings = self.get_fund_holdings(symbol)
            if holdings:
                all_holdings[symbol] = holdings

            # Rate limiting - wait between requests
            if i < total:
                time.sleep(self.request_delay)

        return all_holdings

    def get_fund_performance(self, symbol):
        """
        Get fund performance metrics

        Note: This is simplified. In production, use proper fund data APIs

        Args:
            symbol: Fund symbol

        Returns:
            dict: Performance data
        """
        quote = self.get_quote(symbol)
        if not quote:
            return None

        try:
            return {
                'symbol': symbol,
                'price': float(quote.get('05. price', 0)),
                'change_percent': quote.get('10. change percent', '0%'),
                'volume': int(quote.get('06. volume', 0))
            }
        except (ValueError, KeyError) as e:
            logger.error(f"Error parsing performance for {symbol}: {e}")
            return None
