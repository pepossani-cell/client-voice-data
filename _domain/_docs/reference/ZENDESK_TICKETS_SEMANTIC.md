# ZENDESK_TICKETS — Semantic Documentation

> **Domain**: CLIENT_VOICE
> **Related Reference**: [ZENDESK_TICKETS.md](../../../docs/reference/ZENDESK_TICKETS.md)
> **Last Updated**: 2026-02-03

---

## 1. Business Definition

**What is this entity?**

Zendesk at Capim is not a monolithic support channel. It serves two distinct universes with fundamentally different ontologies: B2B (SaaS Support) and B2C (Fintech Debt Collection).

**In one sentence**: The master record of customer interactions in Zendesk, serving both clinic support (B2B) and patient debt collection (B2C), requiring bifurcated routing logic to avoid context blindness.

---

## 2. Grain (Business Perspective)

**What does one row represent?**

One row represents a single support ticket with a lifecycle (Opened → Assigned → Solved → Closed). Each ticket is attributed to an agent and potentially to a clinic (B2B) or a patient/debtor (B2C).

---

## 3. Key Relationships

### Upstream (Dependencies)

| Entity | Relationship | Description |
|:---|:---|:---|
| SOURCE_ZENDESK_TICKETS | Raw source | Ingested via Hevo from Zendesk API |
| ZENDESK_USERS | Identity resolution | Links `end_user_id` and `assignee_id` to people |
| CLINICS | Affiliation (B2B only) | Links tickets to clinic entities |

### Downstream (Dependents)

| Entity | Relationship | Description |
|:---|:---|:---|
| ZENDESK_COMMENTS | Contains | Each ticket has N comments (conversation thread) |
| TICKET_ANALYSIS | Enriched | LLM-classified version with categories and sentiment |
| CLINIC_HEALTH_SCORE | Contributes to | Ticket volume/sentiment used as health proxy |

---

## 4. Common Questions This Answers

- [x] How many support tickets does a clinic open per month? (B2B)
- [x] What is the debt collection activity for a specific patient? (B2C)
- [x] Which agent is handling tickets from high-risk clinics?
- [x] What percentage of tickets are automated (bot vs human)?
- [x] What are the most common tags for fintech vs saas tickets?

**Example queries this entity powers:**
- "Top 10 clinics by ticket volume in 2025"
- "Average resolution time for B2B vs B2C tickets"
- "Debt collection tickets with high-risk tags"

---

## 5. The Bifurcated Model: Two Worlds

### Universe Classification

| Universe | Context | Target Persona | Key Identifier | Volumetry (2025) |
| :--- | :--- | :--- | :--- | :--- |
| **B2B (SaaS)** | Support, Bugs, Usage | Clinic Staff (Doctor/Secretary) | `clinic_id` | ~42% |
| **B2C (Fintech)** | Debt Collection, Negotiation | Patient (Debtor) | `cpf` / `contract_id` | ~30% |
| **Undefined** | Bot, spam, triage | Unknown | `email` | ~28% |

### Routing Logic (Multi-Attribute)

**Layer 1: Identity & Affiliation (High Confidence)**
- IF `is_claudinha_assigned` = TRUE THEN Domain = **AGENT_CLAUDINHA**
- IF `clinic_id_enhanced` IS NOT NULL AND `ticket_domain_heuristic` != 'B2C_FINANCE' THEN Domain = **SAAS (B2B)**

**Layer 2: Intent & Tags (Directional)**
- Tags like `bnpl_boleto`, `grupo_cobranca` → B2C Fintech
- Tags like `saas_suporte`, `saas__maquininha` → B2B SaaS

**Layer 3: Traceability & Flow**
- IF `via_channel` = 'whatsapp' THEN Prioritize real-time triaging
- IF `assignee_name` contains 'Bot' THEN Treat as Triage-stage

> **⚠️ Multi-Category Warning**: Agents are empowered to re-route if the User's text contradicts the Metadata. Metadata is the *Map*, the Transcript is the *X-Ray*.

---

## 6. Status Semantics

| Status Value | Business Meaning | Notes |
|:---|:---|:---|
| open | Ticket is active and awaiting agent response | |
| pending | Ticket is awaiting user input | |
| solved | Agent has provided a resolution | Can be reopened |
| closed | Ticket is archived (cannot be reopened) | |
| deleted | Ticket was manually discarded | Rare |

---

## 7. Tag Taxonomy (Business Heuristics)

### Fintech / B2C Signals
- **Core**: `grupo_cobranca`, `agente_cobranca`, `droz_ativo` (Active Collection)
- **Intent**: `cob_renegociação_fácil`, `cob_envio_de_boleto`, `cob_promessa_de_pagamento`
- **Risk**: `maior_180` (Days past due), `loss`, `faixa_1_30`

### SaaS / B2B Signals
- **Core**: `saas_suporte`, `saas_duvida`
- **Intent**: `saas_pagamento` (subscription), `saas_agenda`, `saas_login`
- **Hardware**: `saas__maquininha` (POS Support)

### Technical / Bot Signals
- `droz_switchboard`: The routing bot. Present in 90%+ of tickets. Ignore if other tags exist.
- `cloudhumans`: AI Agent layer. High volume, usually Triage.

---

## 8. Identification Strategy

### For B2B (SaaS) Tickets
- **Trust**: `clinic_id_enhanced` from ZENDESK_TICKETS_ENHANCED_V1
- **Fallback**: If NULL, check `requester_email` against `SAAS.USERS`
- **Success Rate**: 92% of B2B tickets have `clinic_id`

### For B2C (Fintech) Tickets
- **Current State**: `clinic_id` is usually NULL (expected!)
- **Strategy**: DO NOT look for Clinics. Look for **CPF** or **Contract IDs** in the transcript or subject line
- **Success Rate**: Near-zero `clinic_id` match (0.08%) — **This is not a bug!**

#### B2C Linkage (The "Golden Path")
1. Resolve User Email: `end_user_id` → `ZENDESK_USERS.user_email`
2. Match Platform User: `user_email` → `RESTRICTED.INCREMENTAL_SENSITIVE_DATA_API.email`
3. Find Debt Context: `user_id` → `CREDIT_SIMULATIONS.financial_responsible_id`

> **⚠️ Warning**: Do NOT use `PATIENTS` table for debt collection. The payer is the `financial_responsible_id` (User), not always the clinical patient.

---

## 9. Limitations & Caveats

### The "Ghost" Phenomenon
- **B2B Tickets**: Excellent identification (92% match rate with `clinic_id`)
- **B2C Tickets**: Near-zero identification with `clinic_id` (0.08%) — **This is expected**
- Do NOT treat B2C tickets without `clinic_id` as data quality errors. They belong to a different ontology (Patient/Debtor Ontology).

### Tag Lag
- Tags like `saas__maquininha` may appear on a ticket BEFORE the database reflects `has_capim_pos = TRUE`
- Trust the ticket context over dimensional attributes for real-time support

### Email Sharing (B2B)
- Clinics often share emails (e.g., `contato@clinica.com` used by 3 users)
- This makes `requester_email` a weak identifier for specific *persons* in B2B, but strong for the *Clinic*

---

## 10. PII & Sensitivity

| Column | Sensitivity | Notes |
|:---|:---|:---|
| subject | MEDIUM | May contain patient names or CPF |
| description | MEDIUM | May contain clinical or financial details |
| requester_email | HIGH | Personal contact information |
| tags | LOW | Operational metadata only |

---

## 11. Source & Confirmation

**Source System**: Zendesk + Enhanced via Snowflake (RESTRICTED schema)

**Primary View**: `CAPIM_DATA_DEV.POSSANI_SANDBOX.ZENDESK_TICKETS_ENHANCED_V1`

**Confirmation Level**:
- [x] Confirmed by business owner (CX Team)
- [x] Observed in data
- [x] Inferred (Bifurcation logic, routing heuristics)

**Business Owner**: CX Team / Data Engineering

**Last Validated**: 2026-02-03 (Traceability Upgrade: Added `VIA_CHANNEL`, `IS_MESSAGING`, `ASSIGNEE_NAME`, `IS_CLAUDINHA_ASSIGNED`)
