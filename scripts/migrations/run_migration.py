"""
Execute PostgreSQL migration script with validation.

Usage:
    python run_migration.py 001_add_metadata_flags_and_natureza_v3.sql
"""
import sys
import os
from pathlib import Path
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def execute_migration(sql_file: Path):
    """Execute a SQL migration file against PostgreSQL."""
    
    if not sql_file.exists():
        print(f"[ERROR] Migration file not found: {sql_file}")
        sys.exit(1)
    
    print("=" * 80)
    print(f"EXECUTING MIGRATION: {sql_file.name}")
    print("=" * 80)
    
    # Read SQL
    with open(sql_file, 'r', encoding='utf-8') as f:
        sql = f.read()
    
    # Connect to PostgreSQL
    try:
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
        conn.autocommit = False  # Use transaction
        cursor = conn.cursor()
        
        print(f"\n[OK] Connected to PostgreSQL: {os.getenv('VOX_POPULAR_DB')}")
        
    except Exception as e:
        print(f"[ERROR] Failed to connect to PostgreSQL: {e}")
        sys.exit(1)
    
    # Split SQL into statements (skip comments and validation queries)
    statements = []
    current_stmt = []
    in_comment_block = False
    
    for line in sql.split('\n'):
        stripped = line.strip()
        
        # Skip comment blocks
        if stripped.startswith('--'):
            continue
        
        # Accumulate statement
        if stripped:
            current_stmt.append(line)
        
        # Statement complete when we hit semicolon
        if stripped.endswith(';'):
            stmt = '\n'.join(current_stmt).strip()
            if stmt and not stmt.startswith('--'):
                statements.append(stmt)
            current_stmt = []
    
    print(f"\n[INFO] Found {len(statements)} SQL statements to execute")
    
    # Execute DDL statements (ALTER TABLE, COMMENT ON, etc.)
    # Skip SELECT validation queries (will run those separately)
    executed = 0
    for i, stmt in enumerate(statements):
        stmt_type = stmt.split()[0].upper()
        
        # Skip SELECT queries (validation only)
        if stmt_type == 'SELECT':
            continue
        
        try:
            print(f"\n[{i+1}/{len(statements)}] Executing {stmt_type}...")
            cursor.execute(stmt)
            executed += 1
            print(f"  [OK] Success")
        except Exception as e:
            print(f"  [ERROR] Error: {e}")
            print(f"\n[ROLLBACK] Transaction rolled back due to error")
            conn.rollback()
            cursor.close()
            conn.close()
            sys.exit(1)
    
    # Commit transaction
    print(f"\n[COMMIT] Committing {executed} DDL statements...")
    conn.commit()
    print("  [OK] Transaction committed")
    
    # Run validation queries
    print("\n" + "=" * 80)
    print("VALIDATION QUERIES")
    print("=" * 80)
    
    # Validation 1: Check new columns exist
    print("\n[1] New columns:")
    cursor.execute("""
        SELECT column_name, data_type, is_nullable 
        FROM information_schema.columns 
        WHERE table_name = 'ticket_insights' 
          AND column_name IN ('is_proactive', 'has_interaction')
        ORDER BY column_name
    """)
    for row in cursor.fetchall():
        print(f"  [OK] {row[0]:20s} {row[1]:10s} nullable={row[2]}")
    
    # Validation 2: Check constraint
    print("\n[2] CHECK constraint:")
    cursor.execute("""
        SELECT conname, pg_get_constraintdef(oid) 
        FROM pg_constraint 
        WHERE conname = 'check_root_cause_values'
    """)
    row = cursor.fetchone()
    if row:
        print(f"  [OK] Constraint exists: {row[0]}")
        # Count how many values in constraint
        constraint_def = row[1]
        value_count = constraint_def.count("'")  # Rough estimate (each value has 2 quotes)
        print(f"  [OK] Estimated values in constraint: ~{value_count // 2}")
    else:
        print("  [ERROR] Constraint not found!")
    
    # Validation 3: Current data distribution
    print("\n[3] Current root_cause distribution (top 10):")
    cursor.execute("""
        SELECT root_cause, COUNT(*) as count,
               ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as pct
        FROM ticket_insights
        WHERE root_cause IS NOT NULL
        GROUP BY root_cause
        ORDER BY count DESC
        LIMIT 10
    """)
    for row in cursor.fetchall():
        print(f"  {row[0]:30s} {row[1]:6d} ({row[2]:5.1f}%)")
    
    # Validation 4: NULL counts for new columns
    print("\n[4] New columns (should be 100% NULL until reprocessing):")
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(is_proactive) as is_proactive_filled,
            COUNT(has_interaction) as has_interaction_filled
        FROM ticket_insights
    """)
    row = cursor.fetchone()
    print(f"  Total tickets: {row[0]:,}")
    print(f"  is_proactive filled: {row[1]:,} ({100*row[1]/row[0]:.1f}%)")
    print(f"  has_interaction filled: {row[2]:,} ({100*row[2]/row[0]:.1f}%)")
    
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 80)
    print("MIGRATION COMPLETE")
    print("=" * 80)
    print("\n[OK] Schema updated successfully")
    print("\nNext step: Run Golden Set reprocessing")
    print("  python scripts/reprocess_tickets_full_taxonomy.py --limit 1000 --save-to-db")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python run_migration.py <migration_file.sql>")
        sys.exit(1)
    
    migration_file = Path(__file__).parent / sys.argv[1]
    execute_migration(migration_file)
