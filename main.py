"""Fund Leader Tracker main entry point."""
import os
import sys
import logging

from email_alerts import EmailAlerts
from fund_analyzer import FundAnalyzer
from utils import Colors, ensure_directories, load_config, load_env, print_colored, print_header, setup_logging

logger = logging.getLogger(__name__)


def check_api_key():
    api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
    if not api_key or api_key == 'your_api_key_here':
        print_colored('ERROR: Alpha Vantage API key not configured.', Colors.FAIL)
        print('Copy .env.example to .env and set ALPHA_VANTAGE_API_KEY before live analysis.')
        return False
    return True


def display_welcome(config):
    print_header('FUND LEADER TRACKER', '=')
    print('Production-oriented fund leadership tracker')
    print(f"Database: {config.get('output', {}).get('database_path', 'data/fund_leaders.db')}")
    print(f"Tracked funds required: {not config.get('analysis', {}).get('allow_uninitialized_sector_fallback', False)}")
    print()


def run_analysis(config, api_key):
    analyzer = FundAnalyzer(config, api_key)
    results = analyzer.analyze_all_sectors()
    if not results:
        print_colored('No results generated', Colors.WARNING)
        return False

    analyzer.export_results()
    summary = analyzer.get_summary()
    email_config = config.get('email_alerts', {})
    send_email = email_config.get('send_on_completion', False) or (
        email_config.get('send_on_change_only', True) and summary.get('has_changes', False)
    )
    if send_email:
        EmailAlerts(config).send_analysis_complete(results, summary, analyzer.get_leadership_changes())

    print_header('Analysis Summary')
    print(f"Sectors analyzed: {summary['sectors_analyzed']}")
    print(f"Leaders identified: {summary['total_leaders']}")
    for sector_name, data in results.items():
        leader = data.get('top_leader')
        if leader:
            print(f"  {sector_name:<25} -> {leader['symbol']:<8} ({leader['name'][:30]})")
    return True


def run_doctor(config):
    print_header('Environment Doctor')
    checks = {
        'config.yaml present': os.path.exists('config.yaml'),
        'fund_universe.yaml present': os.path.exists('fund_universe.yaml'),
        '.env present': os.path.exists('.env'),
        'output directory writable': os.access('output', os.W_OK),
        'data directory writable': os.access('data', os.W_OK),
    }
    for name, status in checks.items():
        print(f"[{ 'OK' if status else 'FAIL' }] {name}")
    return all(checks.values())


def print_usage():
    print('Usage:')
    print('  python main.py             Run full analysis')
    print('  python main.py test        Test Alpha Vantage connectivity')
    print('  python main.py doctor      Validate local setup')
    print('  python initialize_tracked_funds.py [--force]')


def test_api_connection(api_key):
    from holdings_fetcher import HoldingsFetcher
    fetcher = HoldingsFetcher(api_key=api_key)
    quote = fetcher.get_quote('IBM')
    if quote:
        print_colored('[OK] API connection successful', Colors.OKGREEN)
        print(f"IBM price: {quote.get('05. price', 'N/A')}")
    else:
        print_colored('[FAIL] API connectivity failed or rate-limited', Colors.FAIL)


def main():
    load_env()
    ensure_directories()
    config = load_config()
    setup_logging(os.getenv('LOG_FILE', 'logs/fund_tracker.log'), os.getenv('LOG_LEVEL', 'INFO'))
    display_welcome(config)

    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        if command in ['-h', '--help', 'help']:
            print_usage()
            sys.exit(0)
        if command == 'doctor':
            sys.exit(0 if run_doctor(config) else 1)
        if command == 'test':
            if not check_api_key():
                sys.exit(1)
            test_api_connection(os.getenv('ALPHA_VANTAGE_API_KEY'))
            sys.exit(0)
        print_colored(f'Unknown command: {command}', Colors.FAIL)
        print_usage()
        sys.exit(1)

    if not check_api_key():
        sys.exit(1)

    success = run_analysis(config, os.getenv('ALPHA_VANTAGE_API_KEY'))
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
