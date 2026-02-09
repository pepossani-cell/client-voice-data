import sys
import os

# Path to capim-meta-ontology/src
UTILS_PATH = r"c:\Users\pedro.possani_capim\capim-meta-ontology\src"
if sys.path[0] != UTILS_PATH:
    sys.path.insert(0, UTILS_PATH)

from utils.snowflake_connection import run_query

def rematerialize_view_v3():
    print("👷 Rematerializing ZENDESK_TICKETS_ENHANCED_V1 with Assignee Details & Deterministic Flags...")
    
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
        COALESCE(r.organization_id, try_to_numeric(u.id)) as clinic_id_enhanced,
        CASE 
            WHEN r.organization_id IS NOT NULL THEN 'org'
            WHEN u.id IS NOT NULL THEN 'restricted' 
            ELSE 'none' 
        END as clinic_id_source
        
    FROM raw_tickets r
    LEFT JOIN zendesk_users zu ON r.requester_id = zu.id
    LEFT JOIN zendesk_users au ON r.assignee_id = au.id
    LEFT JOIN users_sensitive u ON zu.email = u.email
    """
    
    try:
        run_query(ddl)
        print("✅ View successfully upgraded!")
        
        # Verify
        df = run_query("SELECT zendesk_ticket_id, assignee_name, is_claudinha_assigned, ticket_domain_heuristic FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.ZENDESK_TICKETS_ENHANCED_V1 WHERE is_claudinha_assigned = TRUE LIMIT 5")
        if df is not None:
             print("\n--- SAMPLE UPGRADED TICKETS (CLAUDINHA) ---")
             print(df.to_string(index=False))
             
    except Exception as e:
        print(f"❌ DDL Failed: {e}")

if __name__ == "__main__":
    rematerialize_view_v3()
