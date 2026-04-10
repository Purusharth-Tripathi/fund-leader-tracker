"""Initialize tracked funds using a curated manifest and provider-based ranking."""
import logging
import os
import sys

from data_providers import AlphaVantageClient, AlphaVantagePerformanceProvider, FundSelectionService, FundUniverseRepository
from db_manager import DatabaseManager
from utils import Colors, load_config, load_env, print_colored, print_header, setup_logging

logger = logging.getLogger(__name__)


def build_selection_service(config, api_key):
    api_config = config.get('api', {})
    repo = FundUniverseRepository(os.path.join(os.path.dirname(__file__), 'fund_universe.yaml'))
    performance_provider = None

    if api_key and api_key != 'your_api_key_here':
        client = AlphaVantageClient(
            api_key=api_key,
            timeout=api_config.get('timeout_seconds', 20),
            verify_ssl=api_config.get('verify_ssl', True),
            retry_attempts=api_config.get('retry_attempts', 3),
            retry_delay=api_config.get('retry_delay', 5),
        )
        performance_provider = AlphaVantagePerformanceProvider(client)

    return FundSelectionService(repo, performance_provider)


def initialize_sector_funds(config, selection_service, sector_config, db, force=False):
    sector_name = sector_config['name']
    top_n = config.get('analysis', {}).get('top_funds_per_sector', 5)

    print_header(f"Initializing: {sector_name}")

    if db.has_tracked_funds(sector_name) and not force:
        print_colored(f"Tracked funds already exist for {sector_name} (use --force to replace)", Colors.WARNING)
        return True

    if force:
        db.clear_tracked_funds(sector_name)

    ranked = selection_service.rank_sector_funds(sector_name, top_n=top_n)
    if not ranked:
        print_colored(f"No curated fund candidates found for {sector_name}", Colors.FAIL)
        return False

    print(f"{'Rank':<6} {'Symbol':<8} {'Score':<10} {'Source':<30} Name")
    print('-' * 100)

    for rank, fund in enumerate(ranked, 1):
        print(f"{rank:<6} {fund.symbol:<8} {fund.score_used:<10.2f} {fund.ranking_source:<30} {fund.name}")
        db.save_tracked_fund(
            sector_name=sector_name,
            fund_symbol=fund.symbol,
            fund_name=fund.name,
            performance_3year=fund.annualized_return_3y,
            rank=rank,
            selection_source=fund.ranking_source,
            selection_score=fund.score_used,
        )

    print_colored(f"Saved {len(ranked)} tracked funds for {sector_name}", Colors.OKGREEN)
    return True


def main():
    load_env()
    config = load_config()
    setup_logging(os.getenv('LOG_FILE', 'logs/fund_tracker.log'), os.getenv('LOG_LEVEL', 'INFO'))

    print_header("FUND LEADER TRACKER - TRACKED FUND INITIALIZATION", "=")
    print("This command ranks a curated sector fund universe and stores the top tracked funds.\n")

    force = '--force' in sys.argv
    api_key = os.getenv('ALPHA_VANTAGE_API_KEY', '')
    selection_service = build_selection_service(config, api_key)

    db_path = config.get('output', {}).get('database_path', 'data/fund_leaders.db')
    db = DatabaseManager(db_path)
    sectors = config.get('sectors', [])

    successful = 0
    failed = 0
    for sector in sectors:
        try:
            if initialize_sector_funds(config, selection_service, sector, db, force=force):
                successful += 1
            else:
                failed += 1
        except Exception as exc:
            failed += 1
            logger.exception("Failed to initialize %s: %s", sector['name'], exc)
            print_colored(f"Error initializing {sector['name']}: {exc}", Colors.FAIL)

    print_header("Initialization Complete")
    print_colored(f"Successful sectors: {successful}", Colors.OKGREEN)
    if failed:
        print_colored(f"Failed sectors: {failed}", Colors.FAIL)

    db.close()
    sys.exit(0 if failed == 0 else 1)


if __name__ == '__main__':
    main()
