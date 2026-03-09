# ZENDESK_TICKETS_ENHANCED — Semantic Documentation

> **Domain**: CLIENT_VOICE
> **Related Reference**: [ZENDESK_TICKETS_ENHANCED.md](../../../docs/reference/ZENDESK_TICKETS_ENHANCED.md)
> **Last Updated**: 2026-02-13 (v7 — tag reliability audit, proactive/interaction metadata)

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
| SOURCE_ZENDESK_TICKETS | Enriches | The raw data from Zendesk |
| SOURCE_ZENDESK_ORGANIZATIONS | Joins on organization_id | `EXTERNAL_ID` = Capim clinic_id (primary source, 38%) |
| ZENDESK_TICKETS_RAW (dbt) | Fallback clinic_id | dbt-enriched clinic_id via end_user_external_id etc. (8.5%) |
| USERS_SENSITIVE_INFORMATION | Matches email | Used to bypass email hashing for clinic identification (0.4%) |
| SOURCE_ZENDESK_USERS | Agent/requester info | Names and emails for assignees and requesters |

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
- [x] What is the full conversation history of a ticket? (NEW v6)
- [x] Can I run LLM analysis on ticket content directly in Snowflake? (NEW v6)

**Example queries this entity powers:**
- "Top 10 clinics by ticket volume in 2025."
- "Resolution time distribution for 'Support Clinic' vs 'Support Client'."
- "Show me the full conversation for ticket 12345." (NEW v6)
- "Extract sentiment from recent ticket conversations using LLM." (NEW v6)

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

## 7. Tag-Derived Metadata (for downstream enrichment)

> **Source**: `TAXONOMY_3_AXES.md` v3.1 | **Auditoria**: N=78.018, 6 meses

This view's `TAGS` field enables derivation of two critical metadata flags for downstream processing in `ticket_insights`:

### 7.1. `is_proactive` — Ticket Direction

**~30% of tickets** are proactive outbound (Capim initiated contact, not the customer). These are NOT organic "voice of customer".

**Derivation**: Match against a **curated whitelist** of outbound templates (see `TAXONOMY_3_AXES.md` § Metadata Complementar):
- **Outbound Human** (~8.500 tickets/6mo): `template_contrato_validado`, `template_documents_approved_v4`, `template_cxprimeiramensagem`, etc. (>80% `droz_ativo`)
- **System Automated** (~15.000 tickets/6mo): `template_cob_*`, `template_*_dda`, `template_negativacao*`, etc. (100% `grupo_cobranca`)

**⚠️ Falsos-positivos evitados**: `template_cxsolicitandocontato` (66% receptivo), `template_saas_inadimplentes_v1` (96% receptivo) são templates de **resposta**, não outbound.

**⚠️ Sinal descartado**: `droz_ativo` (30.6%→3.0% em 6 meses — tag morrendo).

### 7.2. `has_interaction` — Real Conversation?

**~13% of tickets** have tag `sem_interacao` — ticket opened but no real conversation happened.

**Derivation**: `has_interaction = NOT (tags ILIKE '%sem_interacao%')`

**Impact**: LLM classification has low confidence for these tickets (69% neutral sentiment=3). Filter from sentiment analyses.

### 7.3. Tag Reliability Summary

| Tag Group | Trust | Stability (7/7 months) | Contradictions | Use as |
|:---|:---:|:---:|:---:|:---|
| `grupo_cobranca` | 97.9% | ✅ Stable | 0.01% | Tier 1 HIGH |
| `venda_si_suporte` | 93.8% | ✅ Stable | 0.01% | Tier 1 HIGH (Natureza: Contratacao; Produto: 94% Onboarding) |
| `loss` | 92.0% | ✅ Stable | 0.06% | Tier 1 HIGH |
| `bug_*` | 81.2% | ✅ Stable | — | Tier 1 HIGH |
| All `n2_*` | N/A | ✅ Stable (top 25) | 0.03% | Tier 1 HIGH |
| `saas_login` | **53.3%** | ✅ Stable | — | Tier 1 **MEDIUM** |
| `droz_ativo` | N/A | ❌ **Dying** (30→3%) | — | ❌ Do NOT use |

**Full audit**: `TAXONOMY_3_AXES.md` § Auditoria de Confiabilidade das Tags.

---

## 8. Limitations & Caveats

### What this entity CANNOT answer:

- **All comments**: The `full_conversation` field includes only the DESCRIPTION + first 5 COMMENTS (max 7K chars). For complete conversation history or more than 5 comments, you must join with `SOURCE_ZENDESK_COMMENTS`.
- **100% accurate clinic mapping**: About 53% of tickets still cannot be matched to a clinic due to missing metadata in Zendesk.

### Known Data Quality Issues:

- **Hashed Emails**: The standard `ZENDESK_TICKETS_RAW` and `ZENDESK_TICKETS` tables are broken for email-based joining because `source_dash_users` is anonymized. Use THIS table (`ENHANCED`) instead.
- **Organization IDs**: `organization_id` is the Zendesk INTERNAL ID (huge numbers ~10^13). The **correct** Capim `clinic_id` comes from `SOURCE_ZENDESK_ORGANIZATIONS.EXTERNAL_ID`. NEVER use `organization_id` directly as clinic_id.

### clinic_id_enhanced Resolution (v5, 2026-02-13):

| Priority | Source | Column | Coverage | Notes |
|:---:|:---|:---|:---:|:---|
| 1 | SOURCE_ZENDESK_ORGANIZATIONS | `EXTERNAL_ID` | 38.0% | Org's external_id = Capim clinic_id |
| 2 | ZENDESK_TICKETS_RAW (dbt) | `CLINIC_ID` | 8.5% | dbt enrichment via end_user_external_id etc. |
| 3 | USERS_SENSITIVE_INFORMATION | `CLINIC_ID` | 0.4% | PII table email match (last resort) |
| - | None | - | 53.2% | No clinic attribution possible |

**CRITICAL BUG FIX (2026-02-13)**: Prior to v5, the view used `organization_id` directly as `clinic_id_enhanced`, returning Zendesk internal IDs (~10^13) instead of Capim clinic_ids (1–49K). This was corrected by joining with `SOURCE_ZENDESK_ORGANIZATIONS` and using `EXTERNAL_ID`.

---

## 9. PII & Sensitivity

| Column | Sensitivity | Notes |
|:---|:---|:---|
| END_USER_EXTERNAL_ID | MEDIUM | Contains user email (unhashed in this view) |
| DESCRIPTION | MEDIUM | May contain snippets of patient or clinic data |

---

## 10. Source & Confirmation

**Source System**: Zendesk + Snowflake (RESTRICTED schema)

**Confirmation Level**:
- [ ] Confirmed by business owner
- [x] Observed in data
- [x] Inferred (Hierarchical clinic attribution logic)

**Business Owner**: CX Team / Data Engineering
