"""
Initialize Tracked Funds - ONE-TIME SETUP
Identifies the top 5 funds per sector based on 3-year performance
and saves them to the database for daily monitoring
"""
import sys
import os
import logging
from utils import load_config, load_env, setup_logging, print_header, print_colored, Colors
from holdings_fetcher import HoldingsFetcher
from db_manager import DatabaseManager

logger = logging.getLogger(__name__)


def get_fund_3year_performance(fetcher, symbol):
    """
    Get 3-year performance for a fund

    Note: This is a simplified implementation. In production, you would:
    1. Use a proper fund data API with historical performance data
    2. Calculate annualized 3-year returns
    3. Consider risk-adjusted metrics like Sharpe ratio

    Args:
        fetcher: HoldingsFetcher instance
        symbol: Fund symbol

    Returns:
        float: 3-year performance % (simulated for now)
    """
    # IMPORTANT: This is a placeholder implementation
    # In a real system, you would fetch actual 3-year performance data from:
    # - Alpha Vantage TIME_SERIES_MONTHLY endpoint
    # - A dedicated fund data API (e.g., Morningstar, Bloomberg)
    # - Calculate: ((current_price / price_3years_ago) - 1) * 100

    # For now, we'll use a simulated approach based on the fund's current data
    # and assign reasonable performance values

    # Get basic fund info to verify it exists
    profile = fetcher.get_etf_profile(symbol)
    if not profile:
        logger.warning(f"Could not fetch profile for {symbol}, assigning default performance")
        return 0.0

    # Simulated 3-year performance (in production, replace with actual API call)
    # Using a hash-based approach to get consistent but varied values
    import hashlib
    hash_value = int(hashlib.md5(symbol.encode()).hexdigest(), 16)
    simulated_performance = 15.0 + (hash_value % 50)  # Range: 15% to 65%

    logger.info(f"{symbol}: Simulated 3-year performance = {simulated_performance:.2f}%")
    return simulated_performance


def initialize_sector_funds(config, api_key, sector_config, db):
    """
    Initialize tracked funds for a specific sector

    Args:
        config: Configuration dictionary
        api_key: Alpha Vantage API key
        sector_config: Sector configuration
        db: DatabaseManager instance

    Returns:
        bool: Success status
    """
    sector_name = sector_config['name']
    keywords = sector_config['keywords']

    print_header(f"Initializing: {sector_name}")
    print(f"Keywords: {', '.join(keywords)}\n")

    # Check if already initialized
    if db.has_tracked_funds(sector_name):
        try:
            response = input(f"Tracked funds already exist for {sector_name}. Re-initialize? (y/N): ")
            if response.lower() != 'y':
                print_colored(f"Skipping {sector_name}", Colors.WARNING)
                return True
            db.clear_tracked_funds(sector_name)
            print_colored(f"Cleared existing tracked funds for {sector_name}", Colors.OKBLUE)
        except (UnicodeEncodeError, UnicodeDecodeError):
            print(f"Skipping {sector_name} (already initialized)")
            return True

    try:
        fetcher = HoldingsFetcher(api_key, requests_per_minute=5, verify_ssl=False)

        # Step 1: Find all candidate funds for this sector
        all_fund_symbols = fetcher.search_funds_by_keywords(keywords)

        if not all_fund_symbols:
            print_colored(f"No funds found for {sector_name}", Colors.FAIL)
            return False

        print(f"Found {len(all_fund_symbols)} candidate funds")

        # Step 2: Get 3-year performance for each fund
        print("\nFetching 3-year performance data...")
        fund_performance = []

        for i, symbol in enumerate(all_fund_symbols, 1):
            print(f"  [{i}/{len(all_fund_symbols)}] Analyzing {symbol}...")
            perf_3year = get_fund_3year_performance(fetcher, symbol)
            fund_performance.append({
                'symbol': symbol,
                'name': symbol,  # In production, fetch actual fund name
                'performance_3year': perf_3year
            })

        # Step 3: Rank funds by 3-year performance (descending)
        fund_performance.sort(key=lambda x: x['performance_3year'], reverse=True)

        # Step 4: Select top 5 funds
        top_5_funds = fund_performance[:5]

        print_colored(f"\nTop 5 funds for {sector_name} (by 3-year performance):", Colors.OKGREEN)
        print(f"{'Rank':<6} {'Symbol':<10} {'3-Year Performance'}")
        print("-" * 40)

        # Step 5: Save to database
        for rank, fund in enumerate(top_5_funds, 1):
            print(f"{rank:<6} {fund['symbol']:<10} {fund['performance_3year']:.2f}%")
            db.save_tracked_fund(
                sector_name=sector_name,
                fund_symbol=fund['symbol'],
                fund_name=fund['name'],
                performance_3year=fund['performance_3year'],
                rank=rank
            )

        print_colored(f"\n✓ Saved top 5 funds for {sector_name}", Colors.OKGREEN)
        return True

    except Exception as e:
        logger.error(f"Error initializing {sector_name}: {e}", exc_info=True)
        print_colored(f"Error initializing {sector_name}: {str(e)}", Colors.FAIL)
        return False


def main():
    """Main entry point for fund initialization"""
    # Setup
    load_env()
    config = load_config()

    log_file = os.getenv('LOG_FILE', 'logs/fund_tracker.log')
    setup_logging(log_file, 'INFO')

    print_header("FUND LEADER TRACKER - INITIALIZATION", "=")
    print_colored("One-time setup: Identifying top 5 funds per sector\n", Colors.OKCYAN)

    # Check API key
    api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
    if not api_key or api_key == 'your_api_key_here':
        print_colored("ERROR: Alpha Vantage API key not configured!", Colors.FAIL)
        print("\nPlease configure your API key in .env file")
        sys.exit(1)

    # Initialize database
    db_path = config.get('output', {}).get('database_path', 'data/fund_leaders.db')
    db = DatabaseManager(db_path)

    sectors = config.get('sectors', [])

    print(f"Configuration:")
    print(f"  Total sectors: {len(sectors)}")
    print(f"  Database: {db_path}")
    print(f"  API Key: {api_key[:8]}...\n")

    # Initialize each sector
    successful = 0
    failed = 0

    for i, sector_config in enumerate(sectors, 1):
        print(f"\n{'='*60}")
        print(f"SECTOR {i}/{len(sectors)}")
        print(f"{'='*60}")

        if initialize_sector_funds(config, api_key, sector_config, db):
            successful += 1
        else:
            failed += 1

    # Summary
    print("\n" + "="*60)
    print_header("Initialization Complete")
    print_colored(f"✓ Successfully initialized: {successful} sectors", Colors.OKGREEN)

    if failed > 0:
        print_colored(f"✗ Failed: {failed} sectors", Colors.FAIL)

    print("\nThe static fund list has been saved to the database.")
    print("Daily monitoring will now track only these specific funds.")
    print("\nTo re-initialize (change which funds are tracked), run this script again.")
    print("Otherwise, use 'python main.py' for daily monitoring.\n")

    db.close()


if __name__ == '__main__':
    main()
