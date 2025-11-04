"""
Reprocess Existing Holdings Data
Analyzes existing holdings in database to identify leaders with correct threshold
"""
import sqlite3
import logging
from collections import defaultdict
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reprocess_holdings():
    """Reprocess existing holdings data to identify leaders"""
    conn = sqlite3.connect('data/fund_leaders.db')
    cursor = conn.cursor()

    try:
        print("=" * 60)
        print("Reprocessing Existing Holdings Data")
        print("=" * 60)

        # Get all sectors
        cursor.execute("SELECT id, name FROM sectors")
        sectors = cursor.fetchall()

        min_threshold = 0.01  # 1% as decimal

        for sector_id, sector_name in sectors:
            print(f"\n[{sector_name}]")

            # Get all funds for this sector
            cursor.execute("SELECT id, symbol FROM funds WHERE sector_id = ?", (sector_id,))
            funds = cursor.fetchall()

            if not funds:
                print(f"  No funds found")
                continue

            print(f"  Analyzing {len(funds)} funds...")

            # Aggregate holdings across funds
            company_stats = defaultdict(lambda: {
                'times_held': 0,
                'total_weight': 0.0,
                'weights': [],
                'name': None
            })

            for fund_id, fund_symbol in funds:
                cursor.execute("""
                    SELECT company_symbol, company_name, weight
                    FROM holdings
                    WHERE fund_id = ? AND weight >= ?
                """, (fund_id, min_threshold))

                holdings = cursor.fetchall()

                for symbol, name, weight in holdings:
                    if symbol and symbol != 'n/a':
                        company_stats[symbol]['times_held'] += 1
                        company_stats[symbol]['total_weight'] += weight
                        company_stats[symbol]['weights'].append(weight)
                        if not company_stats[symbol]['name']:
                            company_stats[symbol]['name'] = name if name != 'Unknown' else symbol

            # Create leaders list
            leaders = []
            for symbol, stats in company_stats.items():
                avg_weight = stats['total_weight'] / stats['times_held']
                prevalence = (stats['times_held'] / len(funds)) * 100

                leaders.append({
                    'symbol': symbol,
                    'name': stats['name'],
                    'times_held': stats['times_held'],
                    'total_weight': stats['total_weight'],
                    'avg_weight': avg_weight,
                    'prevalence': prevalence
                })

            # Sort by times held, then avg weight
            leaders.sort(key=lambda x: (x['times_held'], x['avg_weight']), reverse=True)

            print(f"  Found {len(leaders)} potential leaders")

            if leaders:
                # Save ONLY top leader
                top_leader = leaders[0]

                # Delete existing leader for this sector
                cursor.execute("DELETE FROM industry_leaders WHERE sector_id = ?", (sector_id,))

                # Insert new leader
                cursor.execute("""
                    INSERT INTO industry_leaders
                    (sector_id, company_symbol, company_name, times_held, total_weight, avg_weight, analysis_date)
                    VALUES (?, ?, ?, ?, ?, ?, date('now', 'localtime'))
                """, (
                    sector_id,
                    top_leader['symbol'],
                    top_leader['name'],
                    top_leader['times_held'],
                    top_leader['total_weight'],
                    top_leader['avg_weight']
                ))

                print(f"  TOP LEADER: {top_leader['symbol']} ({top_leader['name']})")
                print(f"    - Held by {top_leader['times_held']}/{len(funds)} funds ({top_leader['prevalence']:.1f}%)")
                print(f"    - Avg weight: {top_leader['avg_weight']*100:.2f}%")
            else:
                print(f"  No leaders identified")

        conn.commit()

        print("\n" + "=" * 60)
        print("[SUCCESS] Reprocessing complete!")
        print("=" * 60)

        # Show summary
        cursor.execute("""
            SELECT s.name, il.company_symbol, il.company_name, il.times_held, il.avg_weight
            FROM industry_leaders il
            JOIN sectors s ON il.sector_id = s.id
            WHERE il.analysis_date = date('now', 'localtime')
            ORDER BY s.name
        """)

        current_leaders = cursor.fetchall()
        print("\nCurrent Leaders:")
        for row in current_leaders:
            print(f"  {row[0]:<25} -> {row[1]:<8} ({row[2][:30]})")

        print()

    except Exception as e:
        logger.error(f"Error reprocessing data: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    reprocess_holdings()
