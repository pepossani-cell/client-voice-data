# ZENDESK_TICKETS_RAW

> **Domain**: CLIENT_VOICE
> **Status**: Active (Structural Foundation)
> **Last Updated**: 2026-02-02

---

## 1. Schema & Grain

**Snowflake Table**: `CAPIM_DATA.CAPIM_ANALYTICS.ZENDESK_TICKETS_RAW`

**Grain**: 1 row per unique Zendesk Ticket.

**Primary Key**: `ZENDESK_TICKET_ID`

---

## 2. Overview

| Metric | Value | As Of |
|:---|:---|:---|
| Row Count | 430,815 | 2026-02-02 |
| Distinct Clinics | 11,427 | 2026-02-02 |
| Date Range | 2022-02-04 to 2026-02-02 | |

---

## 3. Column Profile

### Nullability Highlights

| Column | % Null | Notes |
|:---|:---:|:---|
| CLINIC_ID | 53.6% | Calculated field in dbt |
| DASH_CLINIC_ID | 100.0% | **Broken source** (hashed emails in dash_users) |
| END_USER_EXTERNAL_ID | 73.7% | Only present for specific channels |
| ORG_EXTERNAL_ID | 62.2% | Depends on manual Zendesk Org registration |

---

## 4. Temporal Drift

Stable volume with recent peak of ~15k tickets/month.

---

## 5. Relationships

| Target Entity | FK Column | Cardinality | Notes |
|:---|:---|:---:|:---|
| ZENDESK_TICKETS_ENHANCED | ZENDESK_TICKET_ID | 1:1 | Base for enhanced view |

---

## 6. Population Status

**Status**: Active

---

## Notes & Caveats

- **Redundancy**: This table is the direct output of a complex dbt model joining multiple `source_staging` tables.
- **Data Quality**: The `CLINIC_ID` in this table is the first iteration of clinic attribution and is surpassed by the logic in `ZENDESK_TICKETS_ENHANCED`.
