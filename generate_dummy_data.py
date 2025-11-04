"""
Generate Dummy Data for Testing Dashboard
Creates realistic sample data to test dashboard features
"""
import os
import sqlite3
from datetime import datetime, timedelta
import random
from utils import load_env

# Sample data
SAMPLE_LEADERS = {
    'Aerospace & Defense': [
        ('LMT', 'Lockheed Martin Corporation', 4, 5.8),
        ('BA', 'The Boeing Company', 5, 6.2),
        ('RTX', 'Raytheon Technologies Corp', 3, 4.1),
        ('NOC', 'Northrop Grumman Corporation', 4, 5.5),
    ],
    'Renewable Energy': [
        ('NEE', 'NextEra Energy Inc', 5, 7.1),
        ('ENPH', 'Enphase Energy Inc', 4, 5.9),
        ('TSLA', 'Tesla Inc', 5, 8.5),
        ('FSLR', 'First Solar Inc', 3, 4.2),
    ],
    'Healthcare & Biotech': [
        ('UNH', 'UnitedHealth Group Inc', 5, 8.9),
        ('JNJ', 'Johnson & Johnson', 4, 7.2),
        ('PFE', 'Pfizer Inc', 5, 6.8),
        ('ABBV', 'AbbVie Inc', 4, 6.1),
    ],
    'Automotive': [
        ('TSLA', 'Tesla Inc', 5, 9.2),
        ('F', 'Ford Motor Company', 4, 5.3),
        ('GM', 'General Motors Company', 4, 5.8),
        ('TM', 'Toyota Motor Corporation', 3, 4.7),
    ],
    'Precious Metals': [
        ('GLD', 'SPDR Gold Trust', 5, 6.5),
        ('NEM', 'Newmont Corporation', 4, 5.1),
        ('GOLD', 'Barrick Gold Corporation', 3, 3.8),
        ('AEM', 'Agnico Eagle Mines', 4, 4.9),
    ],
    'Consumer Staples': [
        ('PG', 'Procter & Gamble Co', 5, 7.8),
        ('KO', 'The Coca-Cola Company', 4, 6.9),
        ('WMT', 'Walmart Inc', 5, 8.3),
        ('COST', 'Costco Wholesale Corp', 4, 7.1),
    ],
    'Tech & AI': [
        ('NVDA', 'NVIDIA Corporation', 5, 10.5),
        ('MSFT', 'Microsoft Corporation', 5, 9.8),
        ('GOOGL', 'Alphabet Inc', 4, 8.2),
        ('META', 'Meta Platforms Inc', 4, 7.5),
    ],
    'Financial Services': [
        ('JPM', 'JPMorgan Chase & Co', 5, 8.1),
        ('BAC', 'Bank of America Corp', 4, 6.5),
        ('WFC', 'Wells Fargo & Company', 5, 7.2),
        ('GS', 'Goldman Sachs Group Inc', 3, 5.4),
    ],
    'Infrastructure': [
        ('CAT', 'Caterpillar Inc', 5, 7.3),
        ('DE', 'Deere & Company', 4, 6.2),
        ('UNP', 'Union Pacific Corporation', 4, 5.9),
        ('NSC', 'Norfolk Southern Corp', 3, 4.8),
    ],
    'Real Estate': [
        ('AMT', 'American Tower Corporation', 5, 6.7),
        ('PLD', 'Prologis Inc', 4, 5.8),
        ('CCI', 'Crown Castle Inc', 4, 5.3),
        ('EQIX', 'Equinix Inc', 3, 4.6),
    ]
}

def generate_dummy_data():
    """Generate and insert dummy data into database"""
    print("=" * 60)
    print("Fund Leader Tracker - Dummy Data Generator")
    print("=" * 60)
    print()

    # Load environment
    load_env()
    db_path = os.getenv('DATABASE_PATH', 'data/fund_leaders.db')

    print(f"Database: {db_path}")

    if not os.path.exists(db_path):
        print("Error: Database not found. Please run main.py first to initialize.")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Generate 30 days of historical data
        print("\nGenerating 30 days of historical data...")
        print("This will create:")
        print("  - 30 analysis runs")
        print("  - ~300 leader records (10 sectors x 30 days)")
        print("  - Several leadership changes")
        print()

        base_date = datetime.now() - timedelta(days=30)

        for day in range(30):
            current_date = base_date + timedelta(days=day)
            date_str = current_date.strftime('%Y-%m-%d')

            print(f"  Generating data for {date_str}...", end=" ")

            leaders_count = 0

            for sector_name, leaders_list in SAMPLE_LEADERS.items():
                # Get or create sector
                cursor.execute("SELECT id FROM sectors WHERE name = ?", (sector_name,))
                sector_row = cursor.fetchone()

                if not sector_row:
                    cursor.execute(
                        "INSERT INTO sectors (name, keywords) VALUES (?, ?)",
                        (sector_name, 'test,dummy')
                    )
                    sector_id = cursor.lastrowid
                else:
                    sector_id = sector_row[0]

                # Select leader for this day
                # First 15 days: use first leader
                # Days 15-25: gradually transition to second leader for some sectors
                # Last 5 days: some sectors switch to third leader

                if day < 15:
                    # Stable period - first leader
                    leader_idx = 0
                elif day < 25:
                    # Transition period - some sectors change
                    if sector_name in ['Tech & AI', 'Renewable Energy', 'Automotive']:
                        leader_idx = 1  # Leadership change!
                    else:
                        leader_idx = 0
                else:
                    # Recent period - more changes
                    if sector_name == 'Tech & AI':
                        leader_idx = 0  # Change back to original
                    elif sector_name in ['Financial Services', 'Healthcare & Biotech']:
                        leader_idx = 2  # Another change
                    elif sector_name in ['Renewable Energy', 'Automotive']:
                        leader_idx = 1
                    else:
                        leader_idx = 0

                # Get leader data
                if leader_idx < len(leaders_list):
                    symbol, name, times_held, avg_weight = leaders_list[leader_idx]
                else:
                    symbol, name, times_held, avg_weight = leaders_list[0]

                # Add some randomness to weights
                weight_variation = random.uniform(-0.5, 0.5)
                adjusted_weight = max(1.0, avg_weight + weight_variation)
                total_weight = adjusted_weight * times_held

                # Insert leader
                cursor.execute("""
                    INSERT INTO industry_leaders
                    (sector_id, company_symbol, company_name, times_held, total_weight, avg_weight, analysis_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (sector_id, symbol, name, times_held, total_weight, adjusted_weight, date_str))

                leaders_count += 1

            # Create analysis run record
            cursor.execute("""
                INSERT INTO analysis_runs
                (run_date, sectors_analyzed, funds_analyzed, leaders_found, status, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (current_date.strftime('%Y-%m-%d %H:%M:%S'), 10, 50, leaders_count, 'completed', 'Dummy data'))

            print(f"[OK] ({leaders_count} leaders)")

        conn.commit()
        print()
        print("=" * 60)
        print("[SUCCESS] Dummy data generated successfully!")
        print("=" * 60)
        print()
        print("Data Summary:")
        print(f"  - 30 days of historical data")
        print(f"  - {30 * 10} leader records across 10 sectors")
        print(f"  - 30 analysis runs")
        print()
        print("Notable Leadership Changes:")
        print("  - Day 15-25: Tech & AI (leadership changed)")
        print("  - Day 15-25: Renewable Energy (leadership changed)")
        print("  - Day 15-25: Automotive (leadership changed)")
        print("  - Day 25+: Tech & AI (changed back)")
        print("  - Day 25+: Financial Services (new leader)")
        print("  - Day 25+: Healthcare & Biotech (new leader)")
        print()
        print("[CURRENT] Leaders (as of today):")

        # Show current leaders
        cursor.execute("""
            SELECT s.name, il.company_symbol, il.company_name, il.times_held, il.avg_weight
            FROM industry_leaders il
            JOIN sectors s ON il.sector_id = s.id
            WHERE il.id IN (
                SELECT MAX(id)
                FROM industry_leaders
                GROUP BY sector_id
            )
            ORDER BY s.name
        """)

        current = cursor.fetchall()
        for row in current:
            print(f"  {row[0]:<25} -> {row[1]:<6} ({row[2][:35]})")

        print()
        print("=" * 60)
        print("[DASHBOARD] Refresh your dashboard to see the data!")
        print("            URL: http://localhost:8501")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\nError: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == '__main__':
    generate_dummy_data()
