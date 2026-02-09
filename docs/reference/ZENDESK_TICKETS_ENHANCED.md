# ZENDESK_TICKETS_ENHANCED

> **Domain**: CLIENT_VOICE
> **Related Reference**: [ZENDESK_TICKETS_ENHANCED_SEMANTIC.md](../../_domain/_docs/reference/ZENDESK_TICKETS_ENHANCED_SEMANTIC.md)
> **Status**: Active (Workaround)
> **Last Updated**: 2026-02-02

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

---

## 2. Overview

| Metric | Value | As Of |
|:---|:---|:---|
| Row Count | 430,815 | 2026-02-02 |
| Distinct Tickets | 430,815 | 2026-02-02 |
| Distinct Clinics | 12,084 | 2026-02-02 |
| Date Range | 2022-02-04 to 2026-02-02 | |

---

## 3. Column Profile

### Nullability (Clinic IDs)

| Column | % Null | Notes |
|:---|:---:|:---|
| CLINIC_ID (Original) | 53.6% | Fill rate ~46.4% |
| CLINIC_ID_ENHANCED | 49.7% | **Improved Fill rate ~50.3%** (+3.9pp) |
| CLINIC_ID_FROM_RESTRICTED | 86.7% | New source discovered via PII table |

### Categorical Distributions

**Column: `CLINIC_ID_SOURCE`**

| Value | Count | % |
|:---|:---|:---|
| none | 213,951 | 49.7% |
| org | 162,858 | 37.8% |
| requests | 36,891 | 8.6% |
| restricted | 17,115 | 4.0% |

**Column: `STATUS`**

| Value | Count | % |
|:---|:---|:---|
| closed | 396,938 | 92.1% |
| solved | 32,231 | 7.5% |
| deleted | 913 | 0.2% |
| open | 487 | 0.1% |

---

## 4. Temporal Drift

The volume shows a steady growth from ~9k tickets/month in early 2024 to ~15k in mid-2025.

| Month | Volume |
|:---|:---:|
| 2026-01 | 12,075 |
| 2025-12 | 10,113 |
| 2025-11 | 13,792 |
| 2025-10 | 14,462 |

---

## 5. Relationships

| Target Entity | FK Column | Cardinality | Notes |
|:---|:---|:---:|:---|
| CLINICS | clinic_id_enhanced | N:1 | Linked to Clinic Master |
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
