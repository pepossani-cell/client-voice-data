# ZENDESK_TICKETS — Semantic Documentation

> **Domain**: CLIENT_VOICE
> **Related Reference**: [ZENDESK_TICKETS.md](../../../docs/reference/ZENDESK_TICKETS.md)
> **Last Updated**: 2026-02-13 (tag reliability audit + proactive/interaction metadata)

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

## 7. Tag Taxonomy & Reliability

> **⚠️ UPDATED 2026-02-13**: Seção reescrita com base em auditoria empírica de 78.018 tickets (6 meses).
> **Full taxonomy**: `TAXONOMY_3_AXES.md` (v3.1) — classificação 3 eixos (Produto × Natureza × Atendimento).
> **Full audit**: `TAXONOMY_3_AXES.md` § Auditoria de Confiabilidade das Tags.

### Tag Coverage & Quality (N=78.018)

- **99.9%** dos tickets têm tags (apenas 79 sem tags)
- **Média**: 7.3 tags/ticket, mediana 8, máximo 14
- **101.589 tags únicas** (muitas one-off ou per-ticket)
- **Contradições**: <0.1% entre tags semânticas (muito limpo)

### Tier 1 Tags — Alta Confiança (Determinísticas)

| Tag | Trust Score | Estabilidade | Mapeia para |
|:---|:---:|:---:|:---|
| `grupo_cobranca` | **97.9%** | 7/7 meses | Natureza: `Cobranca_Ativa` |
| `loss` | **92.0%** | 7/7 meses | Natureza: `Subscription_Cancelamento` |
| `venda_si_suporte` | **93.8%** | 7/7 meses | Natureza: `Contratacao` (Produto: 94% `Onboarding`) |
| `bug_*` | **81.2%** | 7/7 meses | Natureza: `Technical_Issue` |
| `cloudhumans` | — | 7/7 meses | Atendimento: bot involvement (WhatsApp) |
| `transbordo_botweb` | — | 5/7 meses (novo Dez/2025) | Atendimento: bot escalation (native) |
| Todos `n2_*` (top 25) | — | **7/7 meses** | Natureza + Produto (mapeamento 1:1) |

### N2_* Tags — Routing de Escalação (Altamente Informativas)

| Tag | Volume (6mo) | Mapeia para (Natureza) |
|:---|---:|:---|
| `n2_saas_pagamento` | 2.322 | `Subscription_Pagamento` |
| `n2_endosso` | 1.890 | `Endosso_Repasse` |
| `n2_bnpl_duvidas_e_suporte` | 1.779 | `Operational_Question` (BNPL) |
| `n2_venda_si_telefone` | 1.257 | `Contratacao` |
| `n2_bnpl_boleto` | 1.041 | `Cobranca_Ativa` |
| `n2_bnpl_duvidas_em_credenciamento` | 1.012 | `Credenciamento` |
| `n2_bnpl_endosso` | 806 | `Endosso_Repasse` |
| `n2_saas_migracao_base` | 729 | `Migracao` |
| `n2_bug_agenda` | 681 | `Technical_Issue` |
| `n2_saas_login` | 638 | `Acesso` (MEDIUM conf.) |
| `n2_saas_churn` | 623 | `Subscription_Cancelamento` |
| `n2_bnpl_cobranca` | 533 | `Cobranca_Ativa` |
| `n2_saas_treinamento` | 521 | `Operational_Question` |
| `n2_cancelamento` | 515 | `Subscription_Cancelamento` |
| `n2_saas_alteracao_dados` | 462 | `Alteracao_Cadastral` |
| `n2_saas_financeiro_menoscarne` | 263 | `Forma_Pagamento` |
| `n2_saas_financeiro_carne` | 196 | `Carne_Capim` |

### Tags Problemáticas — ⚠️ Caveats

| Tag | Issue | Recomendação |
|:---|:---|:---|
| `saas_login` | Trust **53.3%** para `access_issue` (47% são tech/info) | Tier 1 **MEDIUM** (LLM refine) |
| `droz_ativo` | **30.6%→3.0%** em 6 meses — tag morrendo | ❌ NÃO usar como sinal |
| `lancamento_concluido` | **18.1%→4.6%** — semântica instável | ⚠️ Sinal aditivo apenas |
| `template_*` genérico | **16.6% são templates de resposta** (não outbound) | ❌ NÃO usar como proxy de proatividade |
| `droz_switchboard` | **93.5%** dos tickets (infraestrutura) | ❌ Não seletivo |

### Proactive vs Reactive (Metadata Derivada)

**~30% dos tickets são proativos** (Capim iniciou contato). Derivado de lista curada de templates outbound.

**3 espécies de templates**:
1. **Outbound Humano** (~8.500/6mo): `template_contrato_validado`, `template_documents_approved_v4`, etc. (>80% `droz_ativo`)
2. **Sistema Automatizado** (~15.000/6mo): `template_cob_*`, DDA, negativação (100% `grupo_cobranca`)
3. **Templates de Resposta** (~5.500/6mo): `template_cxsolicitandocontato`, `template_saas_inadimplentes_v1`, etc. (>60% `droz_receptivo`) — **NÃO são proativos**

**Full specification**: `TAXONOMY_3_AXES.md` § Metadata Complementar.

### Bot / Technical Signals
- `droz_switchboard`: Routing infrastructure. Present in 93.5% of tickets. **Ignore** — not a bot signal.
- `cloudhumans`: WhatsApp bot layer (31.8%, growing). **High confidence** bot involvement signal.
- `transbordo_botweb`: Native messaging bot escalation (2.1%→22.7%, born Dec/2025). **High confidence** bot signal.
- `droz_ativo` / `droz_receptivo`: Direction tags, but `droz_ativo` is dying. Use `template_*` whitelist instead.

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
