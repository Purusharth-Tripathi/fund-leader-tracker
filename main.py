"""ETF sector leadership planner main entry point."""
import os
import sys

from fund_analyzer import FundAnalyzer
from strategy_engine import parse_review_date
from utils import Colors, ensure_directories, load_config, load_env, print_colored, print_header, setup_logging


def check_api_keys():
    alpha_vantage_key = os.getenv('ALPHA_VANTAGE_API_KEY')
    fmp_key = os.getenv('FMP_API_KEY')
    has_alpha_vantage = bool(alpha_vantage_key and alpha_vantage_key != 'your_api_key_here')
    has_fmp = bool(fmp_key and fmp_key != 'your_api_key_here')

    if has_fmp:
        print_colored('FMP ETF holdings provider configured.', Colors.OKGREEN)
    else:
        print_colored('Warning: FMP_API_KEY not configured. Holdings flow will fall back to cache/Alpha Vantage.', Colors.WARNING)

    if not has_alpha_vantage:
        print_colored('Warning: Alpha Vantage API key not configured. Cached/FMP-only mode may still work.', Colors.WARNING)

    return has_fmp or has_alpha_vantage


def display_welcome(config):
    print_header('ETF SECTOR LEADERSHIP PLANNER', '=')
    print('Advisory-only workflow: weekly review, monthly action, confirmed switches, ETF fallback.')
    print(f"Database: {config.get('output', {}).get('database_path', 'data/fund_leaders.db')}")
    print(f"Report directory: {config.get('output', {}).get('report_directory', 'output/reports')}")
    print()


def run_analysis(config, review_date=None):
    api_key = os.getenv('ALPHA_VANTAGE_API_KEY', '')
    analyzer = FundAnalyzer(config, api_key, review_date=review_date)
    results = analyzer.analyze_all_sectors()
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
    print(f"Actionable trades: {portfolio['actionable_sector_count']}")
    for decision in payload['sectors']:
        print(f"  {decision['sector']:<25} -> {decision['target_symbol']:<8} ({decision['target_kind']}, {decision['action']})")
    if analyzer.report_paths:
        print('\nManual reports:')
        for label, path in analyzer.report_paths.items():
            print(f'  {label}: {path}')
    return True


def run_doctor(config):
    print_header('Environment Doctor')
    checks = {
        'config.yaml present': os.path.exists('config.yaml'),
        'fund_universe.yaml present': os.path.exists('fund_universe.yaml'),
        'output directory writable': os.access('output', os.W_OK),
        'data directory writable': os.access('data', os.W_OK),
    }
    for name, status in checks.items():
        print(f"[{'OK' if status else 'FAIL'}] {name}")

    provider_order = config.get('api', {}).get('holdings_provider_order', ['fmp', 'cache', 'alpha_vantage'])
    print(f"[INFO] holdings provider order: {provider_order}")
    print(f"[INFO] FMP_API_KEY configured: {'yes' if os.getenv('FMP_API_KEY') not in (None, '', 'your_api_key_here') else 'no'}")
    print(f"[INFO] ALPHA_VANTAGE_API_KEY configured: {'yes' if os.getenv('ALPHA_VANTAGE_API_KEY') not in (None, '', 'your_api_key_here') else 'no'}")
    return all(checks.values())


def print_usage():
    print('Usage:')
    print('  python main.py                        Run weekly/manual review using today as review date')
    print('  python main.py review [YYYY-MM-DD]    Run review for a specific review date')
    print('  python main.py doctor                 Validate local setup')
    print('  python main.py latest                 Show latest saved strategy run')
    print('  python initialize_tracked_funds.py [--force]')


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
        print_colored(f'Unknown command: {command}', Colors.FAIL)
        print_usage()
        sys.exit(1)

    success = run_analysis(config, review_date=parse_review_date(None))
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
