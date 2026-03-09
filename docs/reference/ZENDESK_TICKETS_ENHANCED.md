# ZENDESK_TICKETS_ENHANCED

> **Domain**: CLIENT_VOICE
> **Related Reference**: [ZENDESK_TICKETS_ENHANCED_SEMANTIC.md](../../_domain/_docs/reference/ZENDESK_TICKETS_ENHANCED_SEMANTIC.md)
> **Status**: Active (Workaround)
> **Last Updated**: 2026-02-13 (v6 - added full_conversation)

---

## 1. Schema & Grain

**Snowflake View**: `CAPIM_DATA_DEV.POSSANI_SANDBOX.ZENDESK_TICKETS_ENHANCED_V1` (Production workaround)

**Grain**: 1 row per unique Zendesk Ticket.

**Primary Key**: `ZENDESK_TICKET_ID`

**Business Keys**: `ZENDESK_TICKET_ID`

### Key Highlights (Differences from RAW)
This view extends `ZENDESK_TICKETS_RAW` by joining with `RESTRICTED.USERS_SENSITIVE_INFORMATION` to bypass the hashed email limitation in `source_dash_users`.

| Column | Type | Nullable | Description |
|:---|:---|:---:|:---|
| ZENDESK_TICKET_ID | NUMBER | Yes | Unique identifier from Zendesk |
| TICKET_CREATED_AT | TIMESTAMP | Yes | When the ticket was created |
| VIA_CHANNEL | TEXT | Yes | Origin channel (whatsapp, api, web, email) |
| IS_MESSAGING | BOOLEAN | Yes | TRUE if interaction is via Messaging API |
| ASSIGNEE_ID | NUMBER | Yes | ID of the agent assigned to the ticket |
| ASSIGNEE_NAME | TEXT | Yes | Name of the agent (Resolves to 'ClaudIA - Claudinha' for Bots) |
| ASSIGNEE_EMAIL | TEXT | Yes | Email of the agent |
| IS_CLAUDINHA_ASSIGNED | BOOLEAN | No | Deterministic flag based on ID `19753766791956` |
| CLINIC_ID_ENHANCED | NUMBER | Yes | Consolidated Clinic ID (Best available) |
| CLINIC_ID_SOURCE | TEXT | No | Source of the ID: 'org', 'restricted', 'none' |
| TICKET_DOMAIN_HEURISTIC | TEXT | No | Final Class: 'B2C_FINANCE', 'B2B_SUPPORT', 'B2B_POS', 'AGENT_CLAUDINHA', 'ROUTER_NEEDED' |
| FULL_CONVERSATION | TEXT | Yes | Aggregated conversation: DESCRIPTION + first 5 COMMENTS (max 7K chars) |

---

## 2. Overview

| Metric | Value | As Of |
|:---|:---|:---|
| Row Count | 436,320 | 2026-02-13 |
| Distinct Tickets | 436,320 | 2026-02-13 |
| Distinct Clinics (enhanced) | 11,948 | 2026-02-13 |
| Fill Rate (clinic_id) | 46.8% | 2026-02-13 |
| Date Range | 2022-02-04 to 2026-02-13 | |

---

## 3. Column Profile

### Nullability (Clinic IDs)

| Column | % Null | Notes |
|:---|:---:|:---|
| CLINIC_ID_ENHANCED | 53.2% | Fill rate ~46.8% (v5 — corrected IDs) |

### Categorical Distributions

**Column: `CLINIC_ID_SOURCE`** (v5, 2026-02-13)

| Value | Count | % | Description |
|:---|:---|:---|:---|
| none | 232,117 | 53.2% | No clinic attribution possible |
| org | 165,729 | 38.0% | From org EXTERNAL_ID (Capim clinic_id) |
| requests | 36,891 | 8.5% | From dbt enrichment (end_user_external_id etc.) |
| restricted | 1,583 | 0.4% | From PII table (email match, last resort) |

**CRITICAL FIX (v5, 2026-02-13)**: Prior versions used Zendesk `organization_id` (~10^13) as clinic_id — completely wrong. Now uses `SOURCE_ZENDESK_ORGANIZATIONS.EXTERNAL_ID` (correct Capim clinic_id, range 1–49K). Cross-validated: 202,620 matches with `ZENDESK_TICKETS_RAW.CLINIC_ID`, 0 mismatches.

**Column: `STATUS`**

| Value | Count | % |
|:---|:---|:---|
| closed | 396,938 | 92.1% |
| solved | 32,231 | 7.5% |
| deleted | 913 | 0.2% |
| open | 487 | 0.1% |

---

## 4. Temporal Drift

The volume shows growth from ~9k tickets/month in early 2024 to ~15k in mid-2025, then stabilizing.

| Month | Volume | Notes |
|:---|:---:|:---|
| 2026-02 | ~5K+ | Month in progress |
| 2026-01 | 12,075 | |
| 2025-12 | 10,113 | |
| 2025-11 | 13,792 | |
| 2025-10 | 14,462 | |

---

## 5. Relationships

| Target Entity | FK Column | Cardinality | Notes |
|:---|:---|:---:|:---|
| CLINICS (via SAAS) | clinic_id_enhanced | N:1 | Linked to Clinic Master (~46.8% fill) |
| SOURCE_ZENDESK_ORGANIZATIONS | organization_id | N:1 | Org external_id = clinic_id |
| ZENDESK_TICKETS_RAW | zendesk_ticket_id | 1:1 | dbt-enriched version |
| ZENDESK_COMMENTS | zendesk_ticket_id | 1:N | ~9 comments per ticket |

---

## 6. Population Status

**Status**: Active

**Evidence**:
- Last record from 2026-02-02.
- Continuous daily growth observed in drift analysis.

---

## Notes & Caveats

- **Workaround Status**: This view is a temporary fix for the hashed email issue in `source_dash_users`.
- **Traceability Upgrade (2026-02-03)**: Added `VIA_CHANNEL`, `IS_MESSAGING`, `ASSIGNEE_NAME`, `ASSIGNEE_EMAIL`, and `IS_CLAUDINHA_ASSIGNED` (ID: 19753766791956).
- **Semantic Routing**: Adopted `B2C_FINANCE`, `B2B_SUPPORT`, `B2B_POS` taxonomy based on empirical investigation.
- **CRITICAL BUG FIX v5 (2026-02-13)**: `clinic_id_enhanced` was returning Zendesk `organization_id` (internal ID ~10^13) instead of Capim `clinic_id` (1–49K). Fixed by joining with `SOURCE_ZENDESK_ORGANIZATIONS.EXTERNAL_ID`. Also added `ZENDESK_TICKETS_RAW.CLINIC_ID` (dbt enrichment) as fallback source.
- **FULL_CONVERSATION v6 (2026-02-13)**: Added aggregated conversation field that mirrors the PostgreSQL `vox_popular.ticket_insights` logic. Includes DESCRIPTION + first 5 COMMENTS (truncated to 7K chars). This enables LLM semantic analysis directly in Snowflake without needing PostgreSQL access.

## Changelog

| Version | Date | Changes |
|:---|:---|:---|
| v6 | 2026-02-13 | Added `full_conversation` field (DESCRIPTION + first 5 COMMENTS, max 7K chars) |
| v5 | 2026-02-13 | **CRITICAL**: Fixed clinic_id_enhanced (was org_id), added dbt fallback, 3-source enrichment |
| v4 | 2026-02-10 | Script updated (never deployed) to use org_external_id |
| v3 | 2026-02-03 | Added assignee details, bot identification, semantic routing |
| v1 | 2026-02-02 | Initial view with org + restricted enrichment |