"""View all tracked funds in the database"""
import sqlite3

conn = sqlite3.connect('data/fund_leaders.db')
cursor = conn.cursor()

cursor.execute('''
    SELECT sector_name, fund_symbol, fund_name, rank_in_sector, performance_3year
    FROM tracked_funds
    ORDER BY sector_name, rank_in_sector
''')

rows = cursor.fetchall()
current_sector = None

for row in rows:
    sector, symbol, name, rank, perf = row
    if sector != current_sector:
        print(f"\n{sector}:")
        current_sector = sector
    print(f"  {rank}. {symbol} - {name} ({perf:.2f}%)")

conn.close()
