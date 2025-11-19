"""Quick script to check tracked funds in database"""
from db_manager import DatabaseManager

db = DatabaseManager('data/fund_leaders.db')
cursor = db.conn.cursor()

print("\n" + "="*60)
print("TRACKED FUNDS IN DATABASE")
print("="*60)

cursor.execute('SELECT sector_name, COUNT(*) as count FROM tracked_funds GROUP BY sector_name')
results = cursor.fetchall()

if results:
    for row in results:
        sector = row[0]
        count = row[1]
        print(f"{sector:<35} {count} funds")

    cursor.execute('SELECT COUNT(*) as total FROM tracked_funds')
    total = cursor.fetchone()[0]
    print("-"*60)
    print(f"TOTAL: {total} funds tracked across all sectors")
else:
    print("No tracked funds found in database")

print("="*60 + "\n")

db.close()
