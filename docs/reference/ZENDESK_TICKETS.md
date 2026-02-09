# ZENDESK_TICKETS

> **Domain**: CLIENT_VOICE
> **Related Reference**: [ZENDESK_TICKETS_SEMANTIC.md](../../_domain/_docs/reference/ZENDESK_TICKETS_SEMANTIC.md)
> **Status**: Active
> **Last Updated**: 2026-02-03

---

## 1. Schema & Grain

**Snowflake View**: `CAPIM_DATA_DEV.POSSANI_SANDBOX.ZENDESK_TICKETS_ENHANCED_V1` (Primary)

**Alternative Sources**:
- `CAPIM_DATA.SOURCE_STAGING.SOURCE_ZENDESK_TICKETS` (Raw)
- `CAPIM_DATA.CAPIM_ANALYTICS.ZENDESK_TICKETS_RAW` (Legacy enriched)

**Grain**: 1 row per unique Zendesk Ticket

**Primary Key**: `zendesk_ticket_id`

**Business Keys**: `zendesk_ticket_id`

### Key Columns (Enhanced View)

| Column | Type | Nullable | Description |
|:---|:---|:---:|:---|
| zendesk_ticket_id | NUMBER | No | Unique identifier from Zendesk |
| ticket_created_at | TIMESTAMP | No | When the ticket was created (UTC) |
| ticket_updated_at | TIMESTAMP | Yes | Last update timestamp (UTC) |
| status | TEXT | No | open, pending, solved, closed, deleted |
| priority | TEXT | Yes | urgent, high, normal, low |
| via_channel | TEXT | Yes | Origin channel: whatsapp, api, web, email |
| is_messaging | BOOLEAN | Yes | TRUE if interaction is via Messaging API |
| end_user_id | NUMBER | No | FK to ZENDESK_USERS (requester) |
| assignee_id | NUMBER | Yes | FK to ZENDESK_USERS (assigned agent) |
| assignee_name | TEXT | Yes | Name of the agent (e.g., 'ClaudIA - Claudinha') |
| assignee_email | TEXT | Yes | Email of the agent |
| is_claudinha_assigned | BOOLEAN | No | TRUE if assignee_id = 19753766791956 (Bot) |
| clinic_id_enhanced | NUMBER | Yes | Consolidated Clinic ID (Best available) |
| clinic_id_source | TEXT | No | Source: 'org', 'restricted', 'requests', 'none' |
| ticket_domain_heuristic | TEXT | No | B2C_FINANCE, B2B_SUPPORT, B2B_POS, AGENT_CLAUDINHA, ROUTER_NEEDED |
| subject | TEXT | Yes | Ticket subject line |
| description | TEXT | Yes | Initial ticket description |
| tags | ARRAY | Yes | Array of tag strings (e.g., ['saas_suporte', 'bnpl_boleto']) |

---

## 2. Overview

| Metric | Value | As Of |
|:---|:---|:---|
| Row Count | ~430,815 | 2026-02-02 |
| Distinct Tickets | ~430,815 | 2026-02-02 |
| Distinct Clinics | ~12,084 | 2026-02-02 |
| Date Range | 2022-02-04 to 2026-02-02 | |

---

## 3. Column Profile

### Nullability (Clinic IDs)

| Column | % Null | Notes |
|:---|:---:|:---|
| clinic_id_enhanced | 49.7% | Improved from 53.6% (org-only) |
| assignee_id | ~5% | Most tickets assigned |
| priority | ~60% | Often not set |
| via_channel | ~2% | High fill rate |

### Categorical Distributions

**Column: `clinic_id_source`**

| Value | Count | % |
|:---|:---|:---|
| none | 213,951 | 49.7% |
| org | 162,858 | 37.8% |
| requests | 36,891 | 8.6% |
| restricted | 17,115 | 4.0% |

**Column: `status`**

| Value | Count | % |
|:---|:---|:---|
| closed | 396,938 | 92.1% |
| solved | 32,231 | 7.5% |
| deleted | 913 | 0.2% |
| open | 487 | 0.1% |
| pending | <0.1% | Rare |

**Column: `ticket_domain_heuristic`**

| Value | Count | % |
|:---|:---|:---|
| B2B_SUPPORT | ~180,000 | ~42% |
| B2C_FINANCE | ~130,000 | ~30% |
| ROUTER_NEEDED | ~120,000 | ~28% |

---

## 4. Temporal Drift

Monthly volume shows steady growth from ~9k tickets/month (early 2024) to ~15k (mid-2025).

| Month | Volume |
|:---|:---:|
| 2026-01 | 12,075 |
| 2025-12 | 10,113 |
| 2025-11 | 13,792 |
| 2025-10 | 14,462 |
| 2025-09 | 13,215 |

---

## 5. Relationships

| Target Entity | FK Column | Cardinality | Notes |
|:---|:---|:---:|:---|
| ZENDESK_USERS | end_user_id | N:1 | Requester (end-user) |
| ZENDESK_USERS | assignee_id | N:1 | Assigned agent |
| CLINICS | clinic_id_enhanced | N:1 | Linked to Clinic Master (B2B only) |
| ZENDESK_COMMENTS | zendesk_ticket_id | 1:N | ~9 comments per ticket on average |

---

## 6. Population Status

**Status**: Active

**Evidence**:
- Last record from 2026-02-02
- Continuous daily growth observed in drift analysis
- Ingestion via Hevo (real-time sync)

---

## 7. Data Sources & Enhancement Logic

### Identification Strategy (clinic_id_enhanced)

The `clinic_id_enhanced` field consolidates identification from multiple sources in this priority order:

1. **org_external_id**: Standard Zendesk Organization match (Primary)
2. **restricted_clinic_id**: Match via `USERS_SENSITIVE_INFORMATION.email` (PII table) — +10% uplift
3. **lu_clinic_id**: Legacy `requests` table match — Low success rate

**Query Reference**: See `queries/views/create_view_zendesk_tickets_enhanced_v1.sql`

### Heuristic Classification (ticket_domain_heuristic)

Classification logic combines:
- Tags (e.g., `grupo_cobranca` → B2C_FINANCE)
- Assignee (e.g., `is_claudinha_assigned` → AGENT_CLAUDINHA)
- Clinic presence (e.g., `clinic_id_enhanced IS NOT NULL` → B2B_SUPPORT)

**Implementation**: See semantic doc for full routing logic.

---

## 8. Query Optimization Tips

### Filtering by Date
```sql
-- Use ticket_created_at for historical analysis
WHERE ticket_created_at >= '2025-01-01'

-- Use ticket_updated_at for recent activity
WHERE ticket_updated_at >= CURRENT_DATE - 7
```

### Filtering by Domain
```sql
-- B2B (SaaS) tickets
WHERE ticket_domain_heuristic = 'B2B_SUPPORT'
  AND clinic_id_enhanced IS NOT NULL

-- B2C (Fintech) tickets
WHERE ticket_domain_heuristic = 'B2C_FINANCE'
  OR ARRAY_CONTAINS('grupo_cobranca'::VARIANT, tags)
```

### Joining with Comments
```sql
-- Get ticket with all comments
SELECT t.*, c.body_comment
FROM ZENDESK_TICKETS_ENHANCED_V1 t
LEFT JOIN SOURCE_ZENDESK_COMMENTS c 
  ON t.zendesk_ticket_id = c.ticket_id
```

---

## 9. Notes & Caveats

### Workaround Status
- This view (`ZENDESK_TICKETS_ENHANCED_V1`) is a temporary fix for the hashed email issue in `source_dash_users`
- Production queries should prefer this view over RAW tables

### Traceability Upgrade (2026-02-03)
- Added `via_channel`, `is_messaging`, `assignee_name`, `assignee_email`, `is_claudinha_assigned`
- Deterministic bot detection based on ID `19753766791956`

### Tag Array Handling
```sql
-- Check if tag exists in array
WHERE ARRAY_CONTAINS('saas_suporte'::VARIANT, tags)

-- Flatten tags for analysis
SELECT zendesk_ticket_id, tag.value::STRING as tag
FROM ZENDESK_TICKETS_ENHANCED_V1,
LATERAL FLATTEN(input => tags) tag
```

### Performance Considerations
- Table is ~430k rows (lightweight)
- No partitioning required
- Indexed on `zendesk_ticket_id`, `clinic_id_enhanced`

---

## 10. Validation Queries

### Check clinic_id enhancement uplift
```sql
SELECT 
  clinic_id_source,
  COUNT(*) as count,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) as pct
FROM ZENDESK_TICKETS_ENHANCED_V1
GROUP BY clinic_id_source
ORDER BY count DESC;
```

### Check domain distribution
```sql
SELECT 
  ticket_domain_heuristic,
  COUNT(*) as count
FROM ZENDESK_TICKETS_ENHANCED_V1
GROUP BY ticket_domain_heuristic
ORDER BY count DESC;
```

### Check bot vs human assignment
```sql
SELECT 
  is_claudinha_assigned,
  COUNT(*) as count
FROM ZENDESK_TICKETS_ENHANCED_V1
GROUP BY is_claudinha_assigned;
```
