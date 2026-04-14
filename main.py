"""ETF sector leadership planner main entry point."""
import os
import sys

from fund_analyzer import FundAnalyzer
from strategy_engine import parse_review_date
from utils import Colors, ensure_directories, load_config, load_env, print_colored, print_header, setup_logging


def check_api_keys():
    alpha_vantage_key = os.getenv('ALPHA_VANTAGE_API_KEY')
    has_alpha_vantage = bool(alpha_vantage_key and alpha_vantage_key != 'your_api_key_here')

    if has_alpha_vantage:
        print_colored('Alpha Vantage ETF holdings/performance provider configured.', Colors.OKGREEN)
    else:
        print_colored('Warning: Alpha Vantage API key not configured. Holdings refresh will be cache-only.', Colors.WARNING)

    return has_alpha_vantage


def display_welcome(config):
    print_header('ETF SECTOR LEADERSHIP PLANNER', '=')
    print('Advisory-only workflow: weekly review, monthly action, confirmed switches, ETF fallback.')
    print('Operating model: refresh holdings snapshots separately, then run cache-first strategy review.')
    print(f"Database: {config.get('output', {}).get('database_path', 'data/fund_leaders.db')}")
    print(f"Report directory: {config.get('output', {}).get('report_directory', 'output/reports')}")
    print()


def run_analysis(config, review_date=None):
    api_key = os.getenv('ALPHA_VANTAGE_API_KEY', '')
    analyzer = FundAnalyzer(config, api_key, review_date=review_date)
    results = analyzer.analyze_all_sectors(fetch_mode='cache_only')
    if not results:
        print_colored('No results generated', Colors.WARNING)
        return False

    analyzer.export_results()
    payload = analyzer.build_run_payload()
    summary = payload['summary']
    portfolio = payload['portfolio_plan']

    print_header('Manual Review Summary')
    print(f"Sectors analyzed: {summary['sectors_analyzed']}")
    print(f"Leaders identified: {summary['total_leaders']}")
    print(f"Switches proposed: {summary['switches']}")
    print(f"ETF fallback sectors: {summary['fallbacks']}")
    print(f"Stale sectors: {summary.get('stale_sectors', 0)}")
    print(f"Cache-miss sectors: {summary.get('cache_miss_sectors', 0)}")
    print(f"Actionable trades: {portfolio['actionable_sector_count']}")
    for decision in payload['sectors']:
        freshness = (decision.get('sector_freshness') or {}).get('freshness', 'unknown')
        print(
            f"  {decision['sector']:<25} -> {decision['target_symbol']:<8} "
            f"({decision['target_kind']}, {decision['action']}, freshness={freshness})"
        )
    if analyzer.report_paths:
        print('\nManual reports:')
        for label, path in analyzer.report_paths.items():
            print(f'  {label}: {path}')
    return True


def run_refresh(config, review_date=None, batch_name=None):
    api_key = os.getenv('ALPHA_VANTAGE_API_KEY', '')
    analyzer = FundAnalyzer(config, api_key, review_date=review_date)
    result = analyzer.refresh_holdings_snapshots(batch_name=batch_name)
    sectors = result.get('sectors', [])
    if not sectors:
        print_colored('No snapshot refresh work completed.', Colors.WARNING)
        return False

    print_header('Snapshot Refresh Summary')
    print(f"Batch: {result.get('batch')}")
    print(f"Review date: {result.get('review_date')}")
    print(f"Sector count: {len(sectors)}")
    print(f"API daily budget: {result['api_budget']['requests_per_day']} calls")
    for sector in sectors:
        freshness = sector.get('sector_freshness') or {}
        requested = sector.get('requested_funds', sector.get('refreshed_funds', 0))
        status = sector.get('status', 'ok')
        print(
            f"  {sector['sector']:<25} -> funds={sector.get('refreshed_funds', 0)}/{requested} "
            f"live={sector.get('live_fetches', 0)} freshness={freshness.get('freshness', 'unknown')} status={status}"
        )
        if sector.get('quota_exhausted') and sector.get('quota_note'):
            print(f"    quota: {sector['quota_note']}")
    return True


def run_doctor(config):
    print_header('Environment Doctor')
    checks = {
        'config.yaml present': os.path.exists('config.yaml'),
        'fund_universe.yaml present': os.path.exists('fund_universe.yaml'),
        'output directory writable': os.access('output', os.W_OK),
        'data directory writable': os.access('data', os.W_OK),
        '10 sectors configured': len(config.get('sectors', [])) == 10,
    }
    for name, status in checks.items():
        print(f"[{'OK' if status else 'FAIL'}] {name}")

    provider_order = config.get('api', {}).get('holdings_provider_order', ['cache', 'alpha_vantage'])
    refresh_batches = config.get('refresh', {}).get('sector_batches', {})
    print(f"[INFO] holdings provider order: {provider_order}")
    print(f"[INFO] ALPHA_VANTAGE_API_KEY configured: {'yes' if os.getenv('ALPHA_VANTAGE_API_KEY') not in (None, '', 'your_api_key_here') else 'no'}")
    print(f"[INFO] refresh batches: {refresh_batches}")
    return all(checks.values())


def print_usage():
    print('Usage:')
    print('  python3 main.py                             Run cache-first strategy review using today as review date')
    print('  python3 main.py review [YYYY-MM-DD]         Run cache-first review for a specific review date')
    print('  python3 main.py refresh [YYYY-MM-DD] [batch_a|batch_b]')
    print('                                             Refresh holdings snapshots for the alternating 5-sector batch')
    print('  python3 main.py doctor                      Validate local setup')
    print('  python3 main.py latest                      Show latest saved strategy run')
    print('  python3 initialize_tracked_funds.py [--force]')


def show_latest_run(config):
    from db_manager import DatabaseManager

    db = DatabaseManager(config.get('output', {}).get('database_path', 'data/fund_leaders.db'))
    latest = db.get_latest_strategy_run()
    if not latest:
        print('No strategy runs saved yet.')
        return 1
    print_header('Latest Strategy Run')
    print(f"Review date: {latest['review_date']}")
    print(f"Timestamp: {latest['run_timestamp']}")
    print(f"Report text: {latest.get('report_text_path')}")
    print(f"Report json: {latest.get('report_json_path')}")
    print(f"Summary: {latest.get('summary')}")
    return 0


def main():
    load_env()
    ensure_directories()
    config = load_config()
    setup_logging(os.getenv('LOG_FILE', 'logs/fund_tracker.log'), os.getenv('LOG_LEVEL', 'INFO'))
    display_welcome(config)
    check_api_keys()

    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        if command in ['-h', '--help', 'help']:
            print_usage()
            sys.exit(0)
        if command == 'doctor':
            sys.exit(0 if run_doctor(config) else 1)
        if command == 'latest':
            sys.exit(show_latest_run(config))
        if command == 'review':
            review_date = parse_review_date(sys.argv[2] if len(sys.argv) > 2 else None)
            sys.exit(0 if run_analysis(config, review_date=review_date) else 1)
        if command == 'refresh':
            review_date = parse_review_date(sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] not in {'batch_a', 'batch_b'} else None)
            batch_name = None
            if len(sys.argv) > 2 and sys.argv[2] in {'batch_a', 'batch_b'}:
                batch_name = sys.argv[2]
            elif len(sys.argv) > 3:
                batch_name = sys.argv[3]
            sys.exit(0 if run_refresh(config, review_date=review_date, batch_name=batch_name) else 1)
        print_colored(f'Unknown command: {command}', Colors.FAIL)
        print_usage()
        sys.exit(1)

    success = run_analysis(config, review_date=parse_review_date(None))
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
