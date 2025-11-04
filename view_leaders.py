"""
View Leaders - Display and query saved leader data
"""
import sys
import logging
from db_manager import DatabaseManager
from utils import load_config, load_env, setup_logging, print_header, print_colored, Colors
from tabulate import tabulate

logger = logging.getLogger(__name__)


def display_all_leaders(db, limit=50):
    """Display THE top leader for each sector"""
    print_header("Top Leader Per Sector")

    leaders = db.get_all_leaders(limit)

    if not leaders:
        print_colored("No leaders found in database", Colors.WARNING)
        return

    # Get only the top leader per sector
    sectors_seen = set()
    top_leaders = []

    for row in leaders:
        sector = row['sector']
        if sector not in sectors_seen:
            sectors_seen.add(sector)
            top_leaders.append({
                'Sector': sector,
                'Symbol': row['company_symbol'],
                'Company': row['company_name'] or 'N/A',
                'Times Held': f"{row['times_held']}/5",
                'Avg Weight': f"{row['avg_weight']:.2f}%",
                'Analysis Date': row['analysis_date']
            })

    # Display as table
    print(tabulate(top_leaders, headers='keys', tablefmt='grid'))
    print_colored(f"\nTotal sectors: {len(top_leaders)}", Colors.OKGREEN)


def display_sector_leaders(db, sector_name, limit=10):
    """Display leaders for a specific sector"""
    print_header(f"Leaders in {sector_name}")

    leaders = db.get_leaders_by_sector(sector_name, limit)

    if not leaders:
        print_colored(f"No leaders found for {sector_name}", Colors.WARNING)
        return

    leaders_data = []
    for i, row in enumerate(leaders, 1):
        leaders_data.append({
            'Rank': i,
            'Symbol': row['company_symbol'],
            'Company': row['company_name'] or 'N/A',
            'Times Held': row['times_held'],
            'Total Weight': f"{row['total_weight']:.2f}%",
            'Avg Weight': f"{row['avg_weight']:.2f}%",
            'Analysis Date': row['analysis_date']
        })

    print(tabulate(leaders_data, headers='keys', tablefmt='grid'))
    print_colored(f"\nShowing top {len(leaders)} leaders", Colors.OKGREEN)


def list_available_sectors(db):
    """List all available sectors in database"""
    print_header("Available Sectors")

    try:
        cursor = db.conn.cursor()
        cursor.execute("SELECT name FROM sectors ORDER BY name")
        sectors = cursor.fetchall()

        if not sectors:
            print_colored("No sectors found in database", Colors.WARNING)
            return

        print("Available sectors:")
        for i, row in enumerate(sectors, 1):
            print(f"  {i}. {row['name']}")

        print_colored(f"\nTotal sectors: {len(sectors)}", Colors.OKGREEN)

    except Exception as e:
        logger.error(f"Error listing sectors: {e}")
        print_colored(f"Error: {str(e)}", Colors.FAIL)


def export_leaders_csv(db, filepath='output/all_leaders.csv'):
    """Export all leaders to CSV"""
    import csv
    import os

    leaders = db.get_all_leaders(500)

    if not leaders:
        print_colored("No leaders to export", Colors.WARNING)
        return

    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Sector', 'Symbol', 'Company', 'Times Held', 'Total Weight %', 'Avg Weight %', 'Analysis Date'])

        for row in leaders:
            writer.writerow([
                row['sector'],
                row['company_symbol'],
                row['company_name'] or 'N/A',
                row['times_held'],
                f"{row['total_weight']:.2f}",
                f"{row['avg_weight']:.2f}",
                row['analysis_date']
            ])

    print_colored(f"Exported {len(leaders)} leaders to {filepath}", Colors.OKGREEN)


def main():
    """Main function for viewing leaders"""
    # Setup
    load_env()
    setup_logging(log_level='INFO')
    config = load_config()

    # Initialize database
    db_path = os.getenv('DATABASE_PATH', 'data/fund_leaders.db')
    db = DatabaseManager(db_path)

    # Command line interface
    if len(sys.argv) < 2:
        print("Fund Leader Tracker - View Leaders")
        print("\nUsage:")
        print("  python view_leaders.py all              - Show all leaders")
        print("  python view_leaders.py sectors           - List available sectors")
        print("  python view_leaders.py sector <name>     - Show leaders for specific sector")
        print("  python view_leaders.py export [path]     - Export leaders to CSV")
        print("\nExamples:")
        print("  python view_leaders.py all")
        print("  python view_leaders.py sector 'Tech & AI'")
        print("  python view_leaders.py export output/leaders.csv")
        sys.exit(0)

    command = sys.argv[1].lower()

    try:
        if command == 'all':
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 50
            display_all_leaders(db, limit)

        elif command == 'sectors':
            list_available_sectors(db)

        elif command == 'sector':
            if len(sys.argv) < 3:
                print_colored("Error: Sector name required", Colors.FAIL)
                print("Usage: python view_leaders.py sector '<sector name>'")
                sys.exit(1)
            sector_name = sys.argv[2]
            limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10
            display_sector_leaders(db, sector_name, limit)

        elif command == 'export':
            filepath = sys.argv[2] if len(sys.argv) > 2 else 'output/all_leaders.csv'
            export_leaders_csv(db, filepath)

        else:
            print_colored(f"Unknown command: {command}", Colors.FAIL)
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error: {e}")
        print_colored(f"Error: {str(e)}", Colors.FAIL)
        sys.exit(1)
    finally:
        db.close()


if __name__ == '__main__':
    import os
    main()
