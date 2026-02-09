# ZENDESK_USERS — Semantic Documentation

> **Domain**: CLIENT_VOICE
> **Related Reference**: [ZENDESK_USERS.md](../../../docs/reference/ZENDESK_USERS.md)
> **Last Updated**: 2026-02-03

---

## 1. Business Definition

**What is this entity?**

The master registry of all identities (Customers and Agents) known to Zendesk. This entity is the **"Rosetta Stone"** for identity resolution in Client Voice, bridging the gap between an anonymous Ticket ID and a specific person (Patient, Doctor, Staff, or Agent).

**In one sentence**: The identity registry that resolves who is the requester (end-user) and who is the responder (agent) for every support interaction.

---

## 2. Grain (Business Perspective)

**What does one row represent?**

One row represents a unique person or shared identity registered in Zendesk. This can be:
- An end-user (clinic staff, patient, debtor)
- An agent (support staff)
- An admin (system user)
- A bot identity (e.g., ClaudIA)

---

## 3. Key Relationships

### Upstream (Dependencies)

| Entity | Relationship | Description |
|:---|:---|:---|
| Raw Zendesk API | Source | Ingested via Hevo from Zendesk |
| USERS_SENSITIVE_INFORMATION | PII match | Links Zendesk email to platform user_id |

### Downstream (Dependents)

| Entity | Relationship | Description |
|:---|:---|:---|
| ZENDESK_TICKETS | Resolves identity | `end_user_id` and `assignee_id` FK to this table |
| ZENDESK_COMMENTS | Resolves identity | `author_id` FK to this table |
| PLATFORM USERS | Cross-domain link | Email matching for financial/clinical context |

---

## 4. Common Questions This Answers

- [x] Who is the person behind this ticket? (Name, email, role)
- [x] Is this requester an agent or an end-user?
- [x] Which clinic organization is this user affiliated with?
- [x] How many tickets has this user created?
- [x] What is the agent assignment pattern for a specific user?

**Example queries this entity powers:**
- "Find all tickets from user X"
- "Identify the agent who handled most debt collection cases"
- "Link Zendesk requester to platform financial_responsible_id"

---

## 5. Role Semantics (The Discriminator)

| Role Value | Business Meaning | Notes |
|:---|:---|:---|
| end-user | Customer, clinic staff, patient, debtor | The person requesting help |
| agent | Support agent (human) | The person providing support |
| admin | System administrator | Backend access only |

**Critical Rule**: 
- `end_user_id` on a ticket ALWAYS points to role = 'end-user'
- `assignee_id` on a ticket ALWAYS points to role = 'agent' or 'admin'

**Validation**: 2026-02-03 analysis showed 100% of B2C tickets had `end_user_id` pointing to `user_role = 'end-user'`.

---

## 6. Identity Resolution Patterns

### The "Requester" Pattern
**Use case**: Find "Who sent this ticket?"

1. Start with `ZENDESK_TICKETS.end_user_id`
2. Join to `ZENDESK_USERS.user_id`
3. Get `user_email`, `user_name`, `user_role`

### The "Agent" Pattern
**Use case**: Find "Who answered this ticket?"

1. Start with `ZENDESK_TICKETS.assignee_id`
2. Join to `ZENDESK_USERS.user_id` WHERE `user_role` IN ('agent', 'admin')
3. Get `assignee_name`, `assignee_email`

### The "Cross-Domain" Pattern (B2C Linkage)
**Use case**: Link Zendesk requester to platform user (for debt context)

1. Get `user_email` from `ZENDESK_USERS`
2. Match `user_email` ↔ `CAPIM_DATA.RESTRICTED.INCREMENTAL_SENSITIVE_DATA_API.email`
3. Resolve `user_id` (platform ID)
4. Join to `CREDIT_SIMULATIONS.financial_responsible_id` for debt context

---

## 7. Organization Affiliation

**Business Meaning**: In Zendesk, "Organizations" roughly map to Clinics (B2B).

- `organization_id` in this table links to Zendesk's internal organization registry
- For B2B tickets, this is the primary way to identify clinic affiliation
- For B2C tickets, `organization_id` is usually NULL (patients are not in organizations)

**Usage**:
- If `organization_id IS NOT NULL` → Likely B2B (clinic-related)
- If `organization_id IS NULL` → Likely B2C (patient/debtor)

---

## 8. Limitations & Caveats

### Email Sharing (B2B)
- In B2B (SaaS), multiple clinic staff members may share `contato@clinica.com`
- In this case, the `user_id` represents the *Role/Clinic*, not a specific individual
- Use `user_name` for person identification, but treat as unreliable (often "Clínica X")

### Email Hashing (Legacy Issue)
- In some legacy analytics tables (`source_dash_users`), emails are hashed (SHA256)
- Use `SOURCE_STAGING.SOURCE_ZENDESK_USERS` or `RESTRICTED` tables for identity matching
- This is why `ZENDESK_TICKETS_ENHANCED_V1` exists (workaround for hashed emails)

### Phone Numbers
- `phone` is often present when `email` is missing (especially for WhatsApp tickets)
- Phone numbers are secondary linkage keys
- Not standardized (may have different formats: +55, 55, no prefix, etc.)

---

## 9. PII & Sensitivity

| Column | Sensitivity | Notes |
|:---|:---|:---|
| user_email | **HIGH** | Personal contact information, PII |
| user_name | MEDIUM | May contain real names |
| phone | **HIGH** | Personal contact information, PII |
| organization_id | LOW | Operational metadata only |
| user_role | LOW | Operational metadata only |

---

## 10. Source & Confirmation

**Source System**: Zendesk API (via Hevo)

**Canonical Source**: `CAPIM_DATA.SOURCE_STAGING.SOURCE_ZENDESK_USERS`

**Confirmation Level**:
- [x] Confirmed by business owner (CX Team)
- [x] Observed in data
- [x] Inferred (Identity resolution patterns, role semantics)

**Business Owner**: CX Team / Data Engineering

**Last Validated**: 2026-02-03 (Role validation: 100% of B2C tickets had correct end-user role)
