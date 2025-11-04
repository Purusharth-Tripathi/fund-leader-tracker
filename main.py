"""
Fund Leader Tracker - Main Entry Point
Identifies industry leaders based on top fund holdings across 10 sectors
"""
import sys
import os
import logging
from utils import (
    load_config, load_env, setup_logging, ensure_directories,
    print_header, print_colored, Colors, get_timestamp
)
from fund_analyzer import FundAnalyzer
from email_alerts import EmailAlerts

logger = logging.getLogger(__name__)


def check_api_key():
    """Check if API key is configured"""
    api_key = os.getenv('ALPHA_VANTAGE_API_KEY')

    if not api_key or api_key == 'your_api_key_here':
        print_colored("\nERROR: Alpha Vantage API key not configured!", Colors.FAIL)
        print("\nPlease follow these steps:")
        print("1. Copy .env.example to .env")
        print("2. Edit .env and add your Alpha Vantage API key")
        print("3. Get a free key at: https://www.alphavantage.co/support/#api-key")
        print()
        return False

    return True


def display_welcome():
    """Display welcome message and configuration"""
    print_header("FUND LEADER TRACKER", "=")
    print_colored("Financial Research Tool - Industry Leader Identification\n", Colors.OKCYAN)

    print("Configuration:")
    print(f"  API Key: {os.getenv('ALPHA_VANTAGE_API_KEY', 'NOT SET')[:8]}...")
    print(f"  Database: {os.getenv('DATABASE_PATH', 'data/fund_leaders.db')}")
    print(f"  Email Alerts: {'Enabled' if os.getenv('EMAIL_ENABLED', 'false').lower() == 'true' else 'Disabled'}")
    print()


def run_analysis(config, api_key):
    """
    Run the fund analysis

    Args:
        config: Configuration dictionary
        api_key: Alpha Vantage API key

    Returns:
        bool: True if successful
    """
    try:
        # Create analyzer
        analyzer = FundAnalyzer(config, api_key)

        # Run analysis
        results = analyzer.analyze_all_sectors()

        if not results:
            print_colored("\nNo results generated", Colors.WARNING)
            return False

        # Export results
        analyzer.export_results()

        # Get summary
        summary = analyzer.get_summary()

        # Send email if configured (only if changes detected or always send is enabled)
        email_config = config.get('email_alerts', {})
        send_email = False

        if email_config.get('send_on_completion', False):
            send_email = True
        elif email_config.get('send_on_change_only', True):
            # Only send if there are leadership changes
            send_email = summary.get('has_changes', False)

        if send_email:
            email = EmailAlerts(config)
            changes = analyzer.get_leadership_changes()
            email.send_analysis_complete(results, summary, changes)

        # Display summary
        print_header("Analysis Summary")
        print_colored(f"Sectors analyzed: {summary['sectors_analyzed']}", Colors.OKGREEN)
        print_colored(f"Leaders identified: {summary['total_leaders']} (1 per sector)", Colors.OKGREEN)

        print("\nTop Leader by Sector:")
        for sector_name, data in results.items():
            leader = data.get('top_leader')
            if leader:
                print(f"  {sector_name:<25} -> {leader['symbol']:<8} ({leader['name'][:30]})")

        print_colored("\nAnalysis completed successfully!", Colors.OKGREEN)
        print("\nResults saved to:")
        print(f"  - CSV: output/leaders.csv")
        print(f"  - JSON: output/leaders.json")
        print(f"  - Database: data/fund_leaders.db")
        print("\nView results: python view_leaders.py all")
        print()

        return True

    except KeyboardInterrupt:
        print_colored("\n\nAnalysis interrupted by user", Colors.WARNING)
        return False
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        print_colored(f"\nAnalysis failed: {str(e)}", Colors.FAIL)

        # Send error alert if email is configured
        if config.get('email_alerts', {}).get('enabled', False):
            email = EmailAlerts(config)
            email.send_error_alert(str(e))

        return False


def main():
    """Main entry point"""
    # Setup environment
    load_env()
    ensure_directories()

    # Load configuration
    config = load_config()

    # Setup logging
    log_file = os.getenv('LOG_FILE', 'logs/fund_tracker.log')
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    setup_logging(log_file, log_level)

    logger.info("=" * 60)
    logger.info("Fund Leader Tracker started")
    logger.info(f"Timestamp: {get_timestamp()}")
    logger.info("=" * 60)

    # Display welcome
    display_welcome()

    # Check API key
    if not check_api_key():
        sys.exit(1)

    api_key = os.getenv('ALPHA_VANTAGE_API_KEY')

    # Parse command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command in ['-h', '--help', 'help']:
            print_usage()
            sys.exit(0)
        elif command == 'test':
            print_colored("Running API connectivity test...", Colors.OKBLUE)
            test_api_connection(api_key)
            sys.exit(0)
        else:
            print_colored(f"Unknown command: {command}", Colors.FAIL)
            print_usage()
            sys.exit(1)

    # Run analysis
    success = run_analysis(config, api_key)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


def print_usage():
    """Print usage information"""
    print("\nFund Leader Tracker - Usage")
    print("=" * 60)
    print("\nCommands:")
    print("  python main.py              Run full analysis")
    print("  python main.py test         Test API connectivity")
    print("  python main.py help         Show this help message")
    print("\nView Results:")
    print("  python view_leaders.py all                Show all leaders")
    print("  python view_leaders.py sectors            List sectors")
    print("  python view_leaders.py sector '<name>'    Show sector leaders")
    print("  python view_leaders.py export [path]      Export to CSV")
    print()


def test_api_connection(api_key):
    """Test Alpha Vantage API connectivity"""
    import requests
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    print("Testing Alpha Vantage API connection...")

    try:
        url = "https://www.alphavantage.co/query"
        params = {
            'function': 'GLOBAL_QUOTE',
            'symbol': 'IBM',
            'apikey': api_key
        }

        response = requests.get(url, params=params, timeout=10, verify=False)
        data = response.json()

        if 'Global Quote' in data:
            print_colored("[OK] API connection successful!", Colors.OKGREEN)
            print(f"  Sample quote retrieved for IBM")
            print(f"  Price: {data['Global Quote'].get('05. price', 'N/A')}")
        elif 'Information' in data:
            print_colored("[WAIT] API rate limit reached", Colors.WARNING)
            print(f"  {data['Information']}")
        elif 'Error Message' in data:
            print_colored("[ERROR] API error", Colors.FAIL)
            print(f"  {data['Error Message']}")
        else:
            print_colored("[?] Unexpected response", Colors.WARNING)
            print(f"  {data}")

    except Exception as e:
        print_colored(f"[ERROR] Connection failed: {str(e)}", Colors.FAIL)


if __name__ == '__main__':
    main()
