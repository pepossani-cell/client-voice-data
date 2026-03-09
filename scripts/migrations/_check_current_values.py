"""Quick check: what root_cause values exist in the table?"""
import os
import sys
from pathlib import Path
import psycopg2
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
load_dotenv()

connect_args = {
    'host': os.getenv('VOX_POPULAR_HOST'),
    'dbname': os.getenv('VOX_POPULAR_DB'),
    'user': os.getenv('VOX_POPULAR_USER'),
    'password': os.getenv('VOX_POPULAR_PASSWORD'),
}
port = os.getenv('VOX_POPULAR_PORT')
if port:
    connect_args['port'] = port

conn = psycopg2.connect(**connect_args)

cursor = conn.cursor()

print("Current root_cause values in ticket_insights:")
print("=" * 60)

cursor.execute("""
    SELECT root_cause, COUNT(*) as count
    FROM ticket_insights
    WHERE root_cause IS NOT NULL
    GROUP BY root_cause
    ORDER BY count DESC
""")

total = 0
for row in cursor.fetchall():
    print(f"  {row[0]:30s} {row[1]:6d}")
    total += row[1]

print("=" * 60)
print(f"Total: {total:,} tickets")

cursor.close()
conn.close()
