"""Quick check: processing_phase column validation"""
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

print("Validation: processing_phase column")
print("=" * 60)

# Column metadata
cursor.execute("""
    SELECT column_name, data_type, character_maximum_length, is_nullable 
    FROM information_schema.columns 
    WHERE table_name = 'ticket_insights' 
      AND column_name = 'processing_phase'
""")
row = cursor.fetchone()
if row:
    print(f"[OK] Column exists: {row[0]}")
    print(f"     Type: {row[1]}({row[2]})")
    print(f"     Nullable: {row[3]}")
else:
    print("[ERROR] Column not found!")

# Distribution
print("\nCurrent distribution:")
cursor.execute("""
    SELECT 
        processing_phase,
        COUNT(*) as count,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as pct
    FROM ticket_insights
    GROUP BY processing_phase
    ORDER BY count DESC
""")
for row in cursor.fetchall():
    phase = row[0] if row[0] else 'NULL (not reprocessed)'
    print(f"  {phase:30s} {row[1]:6d} ({row[2]:5.1f}%)")

cursor.close()
conn.close()
