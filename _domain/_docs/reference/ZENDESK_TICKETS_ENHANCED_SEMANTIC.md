# ZENDESK_TICKETS_ENHANCED — Semantic Documentation

> **Domain**: CLIENT_VOICE
> **Related Reference**: [ZENDESK_TICKETS_ENHANCED.md](../../../docs/reference/ZENDESK_TICKETS_ENHANCED.md)
> **Last Updated**: 2026-02-02

---

## 1. Business Definition

**What is this entity?**
This entity represents the "enhanced" view of customer support interactions between Capim and its clinics (and sometimes their patients). It consolidates technical ticket data with improved clinic attribution.

**In one sentence**: The master record for support tickets, enriched with the best possible clinic identification for reporting.

---

## 2. Grain (Business Perspective)

**What does one row represent?**

One row represents a single support ticket. This ticket has a lifecycle (Opened → Assigned → Solved → Closed) and is attributed to an agent and a clinic.

---

## 3. Key Relationships

### Upstream (Dependencies)

| Entity | Relationship | Description |
|:---|:---|:---|
| SOURCE_ZENDESK_TICKETS | Enriches | The raw raw data from Zendesk |
| USERS_SENSITIVE_INFORMATION | Matches email | Used to bypass email hashing for clinic identification |
| CLINICS | Belongs to | Each ticket is (ideally) linked to a clinic |

### Downstream (Dependents)

| Entity | Relationship | Description |
|:---|:---|:---|
| CHAT_CLASSIFICATION | Input for | Ticket content is used to categorize the reason for contact |
| CLINIC_HEALTH_SCORE | Contributes to | Ticket volume and resolution time are used as proxy for clinic health |

---

## 4. Common Questions This Answers

- [x] How many tickets does a specific clinic open per month?
- [x] What is the average resolution time (SLA) per clinic group?
- [x] Which agents are handling tickets from the most "risky" clinics?
- [x] What percentage of tickets are coming from automated templates (Droz)?

**Example queries this entity powers:**
- "Top 10 clinics by ticket volume in 2025."
- "Resolution time distribution for 'Support Clinic' vs 'Support Client'."

---

## 5. Status Semantics

| Status Value | Business Meaning | Notes |
|:---|:---|:---|
| open | Ticket is active and awaiting response | |
| pending | Ticket is awaiting user input | |
| solved | Agent has provided a resolution | |
| closed | Ticket is archived (cannot be reopened) | |
| deleted | Ticket was manually discarded | |

---

## 6. Scale & Units

| Field | Unit | Notes |
|:---|:---|:---|
| BUSINESS_... | Minutes | Time measures accounting for business hours |
| CALENDAR_... | Minutes | Real-world elapsed time |

---

## 7. Limitations & Caveats

### What this entity CANNOT answer:

- **Raw message content**: For the text of the messages, you must join with `SOURCE_ZENDESK_COMMENTS`.
- **100% accurate clinic mapping**: About 50% of tickets still cannot be matched to a clinic due to missing metadata in Zendesk.

### Known Data Quality Issues:

- **Hashed Emails**: The standard `ZENDESK_TICKETS_RAW` and `ZENDESK_TICKETS` tables are broken for email-based joining because `source_dash_users` is anonymized. Use THIS table (`ENHANCED`) instead.
- **Organization IDs**: Manual registration in Zendesk organizations is the primary source of `clinic_id` but is prone to agent error.

---

## 8. PII & Sensitivity

| Column | Sensitivity | Notes |
|:---|:---|:---|
| END_USER_EXTERNAL_ID | MEDIUM | Contains user email (unhashed in this view) |
| DESCRIPTION | MEDIUM | May contain snippets of patient or clinic data |

---

## 9. Source & Confirmation

**Source System**: Zendesk + Snowflake (RESTRICTED schema)

**Confirmation Level**:
- [ ] Confirmed by business owner
- [x] Observed in data
- [x] Inferred (Hierarchical clinic attribution logic)

**Business Owner**: CX Team / Data Engineering
