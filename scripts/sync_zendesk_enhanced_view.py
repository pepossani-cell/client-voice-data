import sys
import os
import io
from pathlib import Path

# Fix encoding on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Add project root to path for local imports
_PROJECT_ROOT = str(Path(__file__).parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)

from src.utils.snowflake_connection import run_query

def rematerialize_view_v6():
    print("[v6] Rematerializing ZENDESK_TICKETS_ENHANCED_V1...")
    print("  New: full_conversation (DESCRIPTION + first 5 COMMENTS)")
    
    # Claudinha ID confirmed: 19753766791956
    
    ddl = """
    CREATE OR REPLACE VIEW CAPIM_DATA_DEV.POSSANI_SANDBOX.ZENDESK_TICKETS_ENHANCED_V1 AS
    WITH raw_tickets AS (
        SELECT 
            t.ticket_id as zendesk_ticket_id,
            t.ticket_created_at,
            t.ticket_updated_at,
            t.status,
            t.priority,
            t.type,
            t.subject,
            t.requester_id,
            t.assignee_id,
            t.organization_id,
            t.group_id,
            t.tags,
            t.channel as via_channel,
            t.from_messaging_channel as is_messaging,
            t.satisfaction_rating,
            
            -- Deterministic Bot Identification
            CASE 
                WHEN t.assignee_id = 19753766791956 THEN TRUE 
                ELSE FALSE 
            END as is_claudinha_assigned,
            
            -- Semantic Routing (Layered)
            CASE 
                WHEN ARRAY_CONTAINS('saas__maquininha'::VARIANT, SPLIT(t.tags, ',')) THEN 'B2B_POS'
                WHEN ARRAY_CONTAINS('saas_suporte'::VARIANT, SPLIT(t.tags, ',')) THEN 'B2B_SUPPORT'
                WHEN ARRAY_CONTAINS('grupo_cobranca'::VARIANT, SPLIT(t.tags, ',')) THEN 'B2C_FINANCE'
                WHEN t.assignee_id = 19753766791956 THEN 'AGENT_CLAUDINHA'
                ELSE 'ROUTER_NEEDED' 
            END as ticket_domain_heuristic
            
        FROM CAPIM_DATA.SOURCE_STAGING.SOURCE_ZENDESK_TICKETS t
    ),
    
    -- Get description from ZENDESK_TICKETS_RAW (dbt-enriched version)
    tickets_with_description AS (
        SELECT 
            zendesk_ticket_id,
            description
        FROM CAPIM_DATA.CAPIM_ANALYTICS.ZENDESK_TICKETS_RAW
        WHERE description IS NOT NULL
    ),
    
    -- Aggregate first 5 comments per ticket (mirrors backfill_tickets_mvp.py logic)
    comments_aggregated AS (
        SELECT 
            TICKET_ID as zendesk_ticket_id,
            LISTAGG(
                '--- Comment ' || comment_num || ' by ' || COALESCE(COMMENT_AUTHOR_ID::STRING, 'unknown') || ' ---\n' || 
                LEFT(FULL_COMMENT, 500),
                '\n\n'
            ) WITHIN GROUP (ORDER BY comment_num) as comments_text
        FROM (
            SELECT 
                TICKET_ID,
                COMMENT_AUTHOR_ID,
                FULL_COMMENT,
                ROW_NUMBER() OVER (PARTITION BY TICKET_ID ORDER BY COMMENT_CREATED_AT) as comment_num
            FROM CAPIM_DATA.SOURCE_STAGING.SOURCE_ZENDESK_COMMENTS
            WHERE FULL_COMMENT IS NOT NULL
            QUALIFY comment_num <= 5
        )
        GROUP BY TICKET_ID
    ),
    
    -- Zendesk Organizations: external_id IS the Capim clinic_id
    -- (Mirrors dbt logic from capim_analytics.zendesk_tickets_raw.sql line 30)
    zendesk_orgs AS (
        SELECT ORGANIZATION_ID, EXTERNAL_ID as org_external_id
        FROM CAPIM_DATA.SOURCE_STAGING.SOURCE_ZENDESK_ORGANIZATIONS
        WHERE EXTERNAL_ID IS NOT NULL
    ),
    
    -- dbt-enriched clinic_id (covers org_external_id + end_user_external_id + dash/lu)
    -- This captures the "requests" source (~8.6% additional coverage)
    dbt_enriched AS (
        SELECT ZENDESK_TICKET_ID, CLINIC_ID as dbt_clinic_id
        FROM CAPIM_DATA.CAPIM_ANALYTICS.ZENDESK_TICKETS_RAW
        WHERE CLINIC_ID IS NOT NULL
    ),
    
    users_sensitive AS (
        SELECT DISTINCT USER_EMAIL as email, CLINIC_ID as id 
        FROM CAPIM_DATA.RESTRICTED.USERS_SENSITIVE_INFORMATION
        WHERE USER_EMAIL IS NOT NULL
    ),
    
    zendesk_users AS (
        SELECT USER_ID as id, USER_NAME as name, USER_EMAIL as email 
        FROM CAPIM_DATA.SOURCE_STAGING.SOURCE_ZENDESK_USERS
    )

    SELECT 
        r.*,
        -- Assignee Details (Requested 2026-02-03)
        au.name as assignee_name,
        au.email as assignee_email,
        
        -- Enhancement Logic: Business Identification
        -- FIX v4 2026-02-10: Use org_external_id (real Capim clinic_id) not organization_id (Zendesk internal)
        -- FIX v5 2026-02-13: Add dbt CLINIC_ID as fallback for "requests" source (~36K extra tickets)
        -- NEW v6 2026-02-13: Add full_conversation (DESCRIPTION + first 5 COMMENTS)
        -- Priority: 1) org_external_id, 2) dbt enrichment, 3) RESTRICTED users table
        COALESCE(
            TRY_TO_NUMBER(og.org_external_id),
            dbt.dbt_clinic_id,
            TRY_TO_NUMBER(u.id)
        ) as clinic_id_enhanced,
        CASE 
            WHEN og.org_external_id IS NOT NULL THEN 'org'
            WHEN dbt.dbt_clinic_id IS NOT NULL THEN 'requests'
            WHEN u.id IS NOT NULL THEN 'restricted' 
            ELSE 'none' 
        END as clinic_id_source,
        
        -- Full Conversation: DESCRIPTION + COMMENTS (max ~7K chars, mirrors backfill logic)
        LEFT(
            '=== DESCRIPTION ===\n' || COALESCE(desc.description, '[No description]') || '\n\n' ||
            '=== COMMENTS ===\n' || COALESCE(c.comments_text, '[No comments]'),
            7000
        ) as full_conversation
        
    FROM raw_tickets r
    LEFT JOIN tickets_with_description desc ON r.zendesk_ticket_id = desc.zendesk_ticket_id
    LEFT JOIN comments_aggregated c ON r.zendesk_ticket_id = c.zendesk_ticket_id
    LEFT JOIN zendesk_orgs og ON r.organization_id = og.ORGANIZATION_ID
    LEFT JOIN dbt_enriched dbt ON r.zendesk_ticket_id = dbt.ZENDESK_TICKET_ID
    LEFT JOIN zendesk_users zu ON r.requester_id = zu.id
    LEFT JOIN zendesk_users au ON r.assignee_id = au.id
    LEFT JOIN users_sensitive u ON zu.email = u.email
    """
    
    try:
        run_query(ddl)
        print("[OK] View successfully upgraded!")
        
        # Verify: Check full_conversation field
        df = run_query("""
            SELECT 
                zendesk_ticket_id, 
                assignee_name, 
                is_claudinha_assigned,
                LENGTH(full_conversation) as conv_length,
                LEFT(full_conversation, 200) as conv_preview
            FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.ZENDESK_TICKETS_ENHANCED_V1 
            WHERE full_conversation IS NOT NULL
            ORDER BY ticket_created_at DESC
            LIMIT 5
        """)
        if df is not None:
             print("\n--- SAMPLE TICKETS WITH FULL_CONVERSATION ---")
             print(df.to_string(index=False))
             
        # Coverage stats
        df_stats = run_query("""
            SELECT 
                COUNT(*) as total_tickets,
                COUNT(full_conversation) as with_conversation,
                ROUND(COUNT(full_conversation) * 100.0 / COUNT(*), 1) as pct_coverage,
                AVG(LENGTH(full_conversation)) as avg_length
            FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.ZENDESK_TICKETS_ENHANCED_V1
        """)
        if df_stats is not None:
             print("\n--- CONVERSATION COVERAGE STATS ---")
             print(df_stats.to_string(index=False))
             
    except Exception as e:
        print(f"[ERROR] DDL Failed: {e}")

if __name__ == "__main__":
    rematerialize_view_v6()
