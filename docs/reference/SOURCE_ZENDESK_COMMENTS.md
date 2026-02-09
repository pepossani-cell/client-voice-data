# SOURCE_ZENDESK_COMMENTS

> **Domain**: CLIENT_VOICE
> **Related Reference**: [SOURCE_ZENDESK_COMMENTS_SEMANTIC.md](../../_domain/_docs/reference/SOURCE_ZENDESK_COMMENTS_SEMANTIC.md)
> **Status**: Active
> **Last Updated**: 2026-02-02

---

## 1. Schema & Grain

**Snowflake Table**: `CAPIM_DATA.SOURCE_STAGING.SOURCE_ZENDESK_COMMENTS`

**Grain**: 1 row per Comment (interaction) within a ticket.

**Primary Key**: `COMMENT_ID` (Note: `AUDIT_ID` is also unique at this level in the export).

**Business Keys**: `COMMENT_ID`

### Columns

| Column | Type | Nullable | Description |
|:---|:---|:---:|:---|
| COMMENT_ID | NUMBER | No | Unique ID for the comment |
| TICKET_ID | NUMBER | Yes | FK to ZENDESK_TICKETS |
| BODY_COMMENT | TEXT | Yes | Main text of the comment |
| TYPE | TEXT | Yes | Type of comment (e.g., 'Comment') |
| COMMENT_CREATED_AT | TIMESTAMP | Yes | When the comment was posted |

---

## 2. Overview

| Metric | Value | As Of |
|:---|:---|:---|
| Row Count | 3,885,507 | 2026-02-02 |
| Distinct Tickets | ~430k (inferred) | 2026-02-02 |
| Date Range | 2022-02-04 to 2026-02-02 | |

---

## 3. Column Profile

### Nullability

| Column | % Null | Notes |
|:---|:---:|:---|
| COMMENT_AUTHOR_ID | 30.4% | System comments may lack author |
| COMMENT_ATTACHMENTS | 98.0% | Most comments don't have files |

### Categorical Distributions

**Column: `TYPE`**

| Value | Count | % |
|:---|:---|:---|
| Comment | 3,885,507 | 100% |

**Column: `IS_COMMENT_PUBLIC`**

| Value | Count | % |
|:---|:---|:---|
| TRUE | ~3.8M | >99% |
| FALSE | ~8k | <1% |

---

## 4. Temporal Drift

Consistent volume of ~100k-120k comments per month.

| Month | Volume |
|:---|:---:|
| 2026-01 | 80,809 |
| 2025-11 | 110,257 |
| 2025-10 | 120,481 |

---

## 5. Relationships

| Target Entity | FK Column | Cardinality | Notes |
|:---|:---|:---|:---|
| ZENDESK_TICKETS | TICKET_ID | N:1 | Parent ticket |

---

## 6. Population Status

**Status**: Active

---

## Notes & Caveats

- **Attachments**: The `COMMENT_ATTACHMENTS` column is a VARIANT containing JSON data about files.
- **Search Flags**: `HAS_CX_SEARCH` and `HAS_COLLECTIONS_SEARCH` are custom flags added during ingestion for specific filtering.
