"""Initialize tracked funds using a curated manifest and provider-based ranking.

This is the **maintenance** workflow. It is the only path that should
reshuffle the tracked ETF list and it is expected to run on the first Sunday
of each month. By default the command refuses to run outside that window so
that daily refresh/review jobs and monthly maintenance do not both consume
the same daily Alpha Vantage budget.

Pass ``--allow-outside-maintenance`` to override the gate (e.g. first-ever
bootstrap, or an explicit ad-hoc maintenance decision).
"""
import logging
import os
import sys
from datetime import datetime

from data_providers import (
    AlphaVantageBudgetLedger,
    AlphaVantageClient,
    AlphaVantagePerformanceProvider,
    FundSelectionService,
    FundUniverseRepository,
    WORKFLOW_MAINTENANCE,
)
from db_manager import DatabaseManager
from utils import Colors, load_config, load_env, print_colored, print_header, setup_logging

logger = logging.getLogger(__name__)


def is_first_sunday_of_month(today=None) -> bool:
    today = today or datetime.now().date()
    # weekday(): Monday=0 ... Sunday=6. First Sunday is day 1-7.
    return today.weekday() == 6 and today.day <= 7


def build_selection_service(config, api_key, ledger):
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
            ledger=ledger,
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

    print_header("FUND LEADER TRACKER - TRACKED FUND MAINTENANCE", "=")
    print("This command ranks a curated sector fund universe and stores the top tracked funds.")
    print("Maintenance is intended for the first Sunday of each month.\n")

    force = '--force' in sys.argv
    allow_outside = '--allow-outside-maintenance' in sys.argv
    today = datetime.now().date()

    if not is_first_sunday_of_month(today) and not allow_outside:
        print_colored(
            f"Refusing to run maintenance on {today.isoformat()} (weekday={today.strftime('%A')}).",
            Colors.FAIL,
        )
        print_colored(
            "Tracked-ETF reranking is gated to the first Sunday of each month so it does not",
            Colors.WARNING,
        )
        print_colored(
            "compete with daily refresh for the Alpha Vantage budget.",
            Colors.WARNING,
        )
        print_colored(
            "Pass --allow-outside-maintenance to override this gate for bootstrap or ad-hoc maintenance.",
            Colors.WARNING,
        )
        sys.exit(2)

    if allow_outside and not is_first_sunday_of_month(today):
        print_colored(
            "WARNING: --allow-outside-maintenance in effect; running tracked-ETF maintenance "
            "outside the first-Sunday window. Ensure no refresh job runs in parallel.",
            Colors.WARNING,
        )

    api_key = os.getenv('ALPHA_VANTAGE_API_KEY', '')
    api_key_present = bool(api_key and api_key != 'your_api_key_here')

    db_path = config.get('output', {}).get('database_path', 'data/fund_leaders.db')
    db = DatabaseManager(db_path)

    ledger = AlphaVantageBudgetLedger(
        db=db,
        workflow=WORKFLOW_MAINTENANCE,
        daily_budget=config.get('api', {}).get('requests_per_day', 25),
        live_calls_allowed=True,
        api_key_present=api_key_present,
    )
    print_colored(
        f"Workflow: {WORKFLOW_MAINTENANCE} | live AV calls allowed: True | "
        f"AV budget today: consumed={ledger.consumed_today()}/{ledger.daily_budget} "
        f"remaining={ledger.remaining_today()}",
        Colors.OKCYAN,
    )

    selection_service = build_selection_service(config, api_key, ledger)
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

    print_header("Maintenance Complete")
    print_colored(f"Successful sectors: {successful}", Colors.OKGREEN)
    if failed:
        print_colored(f"Failed sectors: {failed}", Colors.FAIL)

    summary = ledger.run_summary()
    print_header('Alpha Vantage Usage (this run)')
    print(f"Workflow: {summary['workflow']}")
    print(f"Live calls allowed: {summary['live_calls_allowed']}")
    print(f"API key configured: {summary['api_key_present']}")
    print(f"Daily budget: {summary['daily_budget']}")
    print(f"Consumed today (persistent): {summary['consumed_today']}")
    print(f"Remaining today (persistent): {summary['remaining_today']}")
    print(
        f"This run: attempted={summary['attempted_this_run']} "
        f"successful={summary['successful_this_run']} "
        f"failed={summary['failed_this_run']} "
        f"blocked={summary['blocked_this_run']} "
        f"rate_limited={summary['rate_limited']}"
    )

    db.close()
    sys.exit(0 if failed == 0 else 1)


if __name__ == '__main__':
    main()
