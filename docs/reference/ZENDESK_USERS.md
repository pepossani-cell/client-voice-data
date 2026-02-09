# ZENDESK_USERS

> **Domain**: CLIENT_VOICE
> **Related Reference**: [ZENDESK_USERS_SEMANTIC.md](../../_domain/_docs/reference/ZENDESK_USERS_SEMANTIC.md)
> **Status**: Active (Auxiliary / Identity Resolution)
> **Last Updated**: 2026-02-03

---

## 1. Schema & Grain

**Snowflake Table**: `CAPIM_DATA.SOURCE_STAGING.SOURCE_ZENDESK_USERS`

**Grain**: 1 row per unique Zendesk User (identity)

**Primary Key**: `user_id` (aliased as `id` in some queries)

**Business Keys**: `user_email`, `user_id`

### Key Columns

| Column | Type | Nullable | Description |
|:---|:---|:---:|:---|
| id (user_id) | NUMBER | No | Unique identifier from Zendesk |
| email (user_email) | TEXT | Yes | Email address (critical linkage key) |
| name (user_name) | TEXT | Yes | Display name (often unstructured) |
| role (user_role) | TEXT | No | Discriminator: 'end-user', 'agent', 'admin' |
| organization_id | NUMBER | Yes | FK to Zendesk Organizations (~Clinics) |
| phone | TEXT | Yes | Phone number (secondary linkage key) |
| created_at | TIMESTAMP | Yes | When the user was created in Zendesk |
| updated_at | TIMESTAMP | Yes | Last update timestamp |
| active | BOOLEAN | Yes | Whether the user is active |
| verified | BOOLEAN | Yes | Whether the email is verified |
| locale | TEXT | Yes | User locale (e.g., 'pt-br', 'en-us') |

---

## 2. Overview

| Metric | Value | As Of |
|:---|:---|:---|
| Row Count | ~150,000 | 2026-02-02 (estimate) |
| Distinct Users | ~150,000 | |
| Distinct Emails | ~140,000 | Some emails shared |
| Distinct Organizations | ~12,000 | |

---

## 3. Column Profile

### Nullability

| Column | % Null | Notes |
|:---|:---:|:---|
| email (user_email) | ~10% | Some users have phone only (WhatsApp) |
| organization_id | ~60% | Expected: B2C users not in orgs |
| phone | ~70% | Often missing for web/email tickets |
| name (user_name) | ~2% | High fill rate |

### Categorical Distributions

**Column: `role` (user_role)**

| Value | Count | % |
|:---|:---|:---|
| end-user | ~145,000 | ~96% |
| agent | ~3,500 | ~2.3% |
| admin | ~1,500 | ~1.0% |

**Column: `active`**

| Value | Count | % |
|:---|:---|:---|
| TRUE | ~135,000 | ~90% |
| FALSE | ~15,000 | ~10% |

---

## 4. Temporal Drift

User growth is steady with spikes during:
- 2023-03: Initial rollout (~20k users)
- 2024-06: WhatsApp integration (~40k new users)
- 2025-10: Debt collection automation (~30k new users)

---

## 5. Relationships

| Target Entity | FK Column | Cardinality | Notes |
|:---|:---|:---:|:---|
| ZENDESK_TICKETS | user_id (as end_user_id) | 1:N | User can create many tickets |
| ZENDESK_TICKETS | user_id (as assignee_id) | 1:N | Agent can be assigned to many tickets |
| ZENDESK_COMMENTS | user_id (as author_id) | 1:N | User can author many comments |
| PLATFORM USERS | email | N:1 | Links to platform user_id via email match |

---

## 6. Population Status

**Status**: Active

**Evidence**:
- Last record from 2026-02-02
- Continuous daily growth via Hevo ingestion
- Real-time sync from Zendesk API

---

## 7. Identity Resolution Queries

### Find requester details for a ticket
```sql
SELECT 
  t.zendesk_ticket_id,
  u.email as requester_email,
  u.name as requester_name,
  u.role as requester_role
FROM ZENDESK_TICKETS_ENHANCED_V1 t
JOIN SOURCE_ZENDESK_USERS u 
  ON t.end_user_id = u.id;
```

### Find agent details for a ticket
```sql
SELECT 
  t.zendesk_ticket_id,
  u.email as agent_email,
  u.name as agent_name,
  u.role as agent_role
FROM ZENDESK_TICKETS_ENHANCED_V1 t
JOIN SOURCE_ZENDESK_USERS u 
  ON t.assignee_id = u.id
WHERE u.role IN ('agent', 'admin');
```

### Link Zendesk user to platform user (B2C)
```sql
SELECT 
  zu.id as zendesk_user_id,
  zu.email as zendesk_email,
  pu.id as platform_user_id,
  pu.cpf
FROM SOURCE_ZENDESK_USERS zu
JOIN CAPIM_DATA.RESTRICTED.INCREMENTAL_SENSITIVE_DATA_API pu
  ON LOWER(TRIM(zu.email)) = LOWER(TRIM(pu.email))
WHERE zu.role = 'end-user';
```

---

## 8. Query Optimization Tips

### Email Matching (Case-Insensitive)
```sql
-- Always normalize emails for joining
WHERE LOWER(TRIM(user_email)) = LOWER(TRIM('example@clinic.com'))
```

### Filter by Role
```sql
-- End-users only (customers)
WHERE user_role = 'end-user'

-- Agents only (support staff)
WHERE user_role IN ('agent', 'admin')
```

### Active Users Only
```sql
-- Exclude deactivated accounts
WHERE active = TRUE
```

---

## 9. Notes & Caveats

### Email Normalization Required
- Always use `LOWER(TRIM(email))` when joining
- Some emails have leading/trailing spaces
- Case sensitivity can cause failed matches

### Shared Emails (B2B)
- Multiple clinic staff may share `contato@clinica.com`
- Use `organization_id` to group, not individual `user_id`
- Consider as "clinic inbox" rather than individual person

### Phone vs Email Priority
- For WhatsApp tickets, `phone` is more reliable than `email`
- Phone format is inconsistent (normalize before matching)

### Bot Identities
- ClaudIA (Claudinha) bot: `user_id = 19753766791956`
- Other bots may exist, filter by `name` pattern: `'%Bot%'`, `'%Automation%'`

---

## 10. Validation Queries

### Check role distribution
```sql
SELECT 
  role,
  COUNT(*) as count,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) as pct
FROM SOURCE_ZENDESK_USERS
GROUP BY role
ORDER BY count DESC;
```

### Check email fill rate
```sql
SELECT 
  CASE 
    WHEN email IS NULL THEN 'NULL'
    WHEN email = '' THEN 'EMPTY'
    ELSE 'FILLED'
  END as email_status,
  COUNT(*) as count
FROM SOURCE_ZENDESK_USERS
GROUP BY email_status;
```

### Check organization affiliation rate
```sql
SELECT 
  CASE 
    WHEN organization_id IS NULL THEN 'No Org (B2C)'
    ELSE 'Has Org (B2B)'
  END as org_status,
  COUNT(*) as count
FROM SOURCE_ZENDESK_USERS
GROUP BY org_status;
```

### Identify bot accounts
```sql
SELECT 
  id,
  name,
  email,
  role
FROM SOURCE_ZENDESK_USERS
WHERE name ILIKE '%bot%' 
   OR name ILIKE '%automation%'
   OR name ILIKE '%claudia%';
```
