"""
Holdings Fetcher for Fund Leader Tracker
Fetches fund holdings data from Alpha Vantage API
"""
import requests
import time
import logging
import os
import json
from utils import print_progress

logger = logging.getLogger(__name__)

# Load cached company names
COMPANY_NAMES_CACHE = {}
try:
    cache_file = os.path.join(os.path.dirname(__file__), 'company_names.json')
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            COMPANY_NAMES_CACHE = json.load(f)
        logger.info(f"Loaded {len(COMPANY_NAMES_CACHE)} company names from cache")
except Exception as e:
    logger.warning(f"Could not load company names cache: {e}")


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

    def get_company_name(self, symbol):
        """
        Get company name for a stock symbol
        First checks cache, then falls back to API if needed

        Args:
            symbol: Stock symbol

        Returns:
            str: Company name or symbol if not found
        """
        # Check cache first
        if symbol in COMPANY_NAMES_CACHE:
            return COMPANY_NAMES_CACHE[symbol]

        # Only use API for critical lookups (disabled by default to save quota)
        # To enable API lookups, set use_api_lookup = True
        use_api_lookup = False

        if not use_api_lookup:
            return symbol  # Return symbol as-is if not in cache

        # API lookup (only if enabled)
        try:
            params = {
                'function': 'OVERVIEW',
                'symbol': symbol,
                'apikey': self.api_key
            }

            response = requests.get(
                self.base_url,
                params=params,
                timeout=10,
                verify=self.verify_ssl
            )
            data = response.json()

            # Get company name from overview
            company_name = data.get('Name', symbol)
            return company_name if company_name else symbol

        except Exception as e:
            logger.debug(f"Could not fetch name for {symbol}: {e}")
            return symbol

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
                    stock_symbol = holding.get('symbol', 'N/A')
                    company_name = holding.get('name', 'Unknown')

                    # If name is Unknown, try to fetch it from cache
                    if company_name == 'Unknown' and stock_symbol not in ['N/A', 'n/a', '']:
                        company_name = self.get_company_name(stock_symbol)

                    holdings.append({
                        'symbol': stock_symbol,
                        'name': company_name,
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
            'aerospace': ['ITA', 'XAR', 'PPA', 'DFEN', 'XTN'],
            'defense': ['ITA', 'XAR', 'PPA', 'DFEN', 'XTN'],
            'aviation': ['ITA', 'XAR', 'PPA', 'JETS', 'SOAR'],
            'military': ['ITA', 'XAR', 'PPA', 'DFEN', 'XTN'],
            'renewable': ['ICLN', 'TAN', 'QCLN', 'PBW', 'FAN'],
            'solar': ['TAN', 'RAYS', 'ICLN', 'PBW', 'QCLN'],
            'wind': ['FAN', 'ICLN', 'PBW', 'TAN', 'QCLN'],
            'healthcare': ['XLV', 'VHT', 'IHI', 'IBB', 'XBI'],
            'biotech': ['IBB', 'XBI', 'BBH', 'VHT', 'XLV'],
            'pharmaceutical': ['XLV', 'VHT', 'IBB', 'XBI', 'IHI'],
            'medical': ['XLV', 'VHT', 'IHI', 'IBB', 'XBI'],
            'health': ['XLV', 'VHT', 'IHI', 'IBB', 'XBI'],
            'automotive': ['CARZ', 'DRIV', 'IDRV', 'XLY', 'VCR'],
            'automobile': ['CARZ', 'DRIV', 'IDRV', 'XLY', 'VCR'],
            'electric vehicle': ['DRIV', 'IDRV', 'CARZ', 'LIT', 'KARS'],
            'ev': ['DRIV', 'IDRV', 'CARZ', 'LIT', 'KARS'],
            'car': ['CARZ', 'DRIV', 'IDRV', 'XLY', 'VCR'],
            'gold': ['GLD', 'GDX', 'GDXJ', 'IAU', 'GLDM'],
            'silver': ['SLV', 'SILJ', 'GDX', 'GDXJ', 'SIL'],
            'platinum': ['GDX', 'GDXJ', 'GLD', 'IAU', 'RING'],
            'precious metals': ['GLD', 'GDX', 'GDXJ', 'IAU', 'SLV'],
            'mining': ['GDX', 'GDXJ', 'XME', 'PICK', 'SIL'],
            'consumer staples': ['XLP', 'VDC', 'FSTA', 'KXI', 'IYK'],
            'food': ['XLP', 'VDC', 'FSTA', 'PBJ', 'MOO'],
            'beverage': ['XLP', 'VDC', 'PBJ', 'FSTA', 'KXI'],
            'household': ['XLP', 'VDC', 'FSTA', 'KXI', 'IYK'],
            'retail': ['XRT', 'RTH', 'XLP', 'VDC', 'FSTA'],
            'technology': ['XLK', 'VGT', 'QTEC', 'SKYY', 'IGM'],
            'artificial intelligence': ['BOTZ', 'IRBO', 'ROBO', 'AIQ', 'THNQ'],
            'AI': ['BOTZ', 'IRBO', 'ROBO', 'AIQ', 'THNQ'],
            'software': ['XLK', 'VGT', 'IGV', 'SKYY', 'QTEC'],
            'cloud': ['SKYY', 'CLOU', 'XLK', 'VGT', 'QTEC'],
            'financial': ['XLF', 'VFH', 'KBE', 'KRE', 'IAI'],
            'banking': ['KBE', 'KRE', 'XLF', 'VFH', 'IAI'],
            'insurance': ['KIE', 'IAK', 'XLF', 'VFH', 'PIC'],
            'fintech': ['FINX', 'IPAY', 'ARKF', 'TPAY', 'XLF'],
            'asset management': ['XLF', 'VFH', 'IAI', 'KCE', 'PFI'],
            'infrastructure': ['PAVE', 'IGF', 'NFRA', 'IFRA', 'PKB'],
            'construction': ['PAVE', 'ITB', 'XHB', 'PKB', 'IGF'],
            'utilities': ['XLU', 'VPU', 'IDU', 'FUTY', 'UTG'],
            'industrial': ['XLI', 'VIS', 'FIDU', 'IYJ', 'IGF'],
            'real estate': ['VNQ', 'IYR', 'XLRE', 'SCHH', 'RWR'],
            'reit': ['VNQ', 'IYR', 'XLRE', 'SCHH', 'RWR'],
            'property': ['VNQ', 'IYR', 'XLRE', 'SCHH', 'ICF'],
            'residential': ['VNQ', 'IYR', 'XLRE', 'REZ', 'ITB'],
            'commercial': ['VNQ', 'IYR', 'XLRE', 'SCHH', 'RWR']
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
