# TICKET_INSIGHTS (Agentic Doc)

> **Purpose**: Data dictionary for `ticket_insights` table (PostgreSQL)  
> **Layer**: SANDBOX (THIS_PROJECT_OWNS)  
> **Source**: PostgreSQL `vox_popular.ticket_insights`  
> **Grain**: ONE ROW = ONE ZENDESK TICKET (enriched with 3-axis taxonomy + LLM variables)  
> **Last Updated**: 2026-03-09  

---

## 1. Schema

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `zendesk_ticket_id` | `bigint` | NO | - | **PK**. Zendesk ticket ID (unique) |
| `ticket_created_at` | `timestamp` | NO | - | Ticket creation time (UTC) |
| `ticket_updated_at` | `timestamp` | YES | - | Last ticket update time (UTC) |
| `status` | `varchar` | YES | - | Ticket status (`closed`, `open`, `deleted`, etc.) |
| `subject` | `text` | YES | - | Ticket subject line |
| `tags` | `text` | YES | - | Zendesk tags (comma-separated). **CAUTION**: `droz_*` tags are routing metadata, NOT bot identifiers (see § 13) |
| `clinic_id` | `bigint` | YES | - | **FK to SAAS.CLINICS**. Capim clinic ID (35.6% fill rate) |
| `clinic_id_source` | `varchar` | YES | - | Source of clinic attribution (`zendesk_raw`, `ticket_form`, `email_hash`, etc.) |
| `assignee_name` | `varchar` | YES | - | Agent name (89.6% fill rate). `'ClaudIA - Claudinha'` = bot (100% precision) |
| **`is_claudinha_assigned`** | `boolean` | YES | `false` | **TRUE if Claudinha bot is CURRENT assignee** (snapshot, NOT history — perde 76.9% bot-touched). See § 13 |
| `via_channel` | `varchar` | YES | - | Entry channel: `whatsapp` (78.8%), `native_messaging` (14.9%), `web` (3.9%), `email` (2.3%), `api` (0.1%) |
| **`product_area`** | `varchar` | YES | - | **Canonical Eixo 1 L1**: `BNPL`, `SaaS`, `Onboarding`, `POS`, `Indeterminado` |
| `product_area_l1` | `varchar` | YES | - | Compatibility mirror used by some app flows. For processed rows, it is expected to match `product_area` |
| **`product_area_l2`** | `varchar` | YES | - | **Eixo 1 L2**: 12 subcategorias (ex: `Cobranca`, `Clinico`, `Credenciamento`, `Operacao`) |
| `product_area_confidence` | `float` | YES | - | Confidence score [0,1] for product area (legacy) |
| `product_area_keywords` | `ARRAY` | YES | - | Keywords matched for product area (legacy) |
| **`workflow_type`** | `varchar` | YES | - | **LEGACY Stage 2** (`Suporte_L2`, `Info_L1`, etc.) — replaced by `root_cause` + `service_type` |
| `workflow_confidence` | `float` | YES | - | Legacy confidence |
| `workflow_keywords` | `ARRAY` | YES | - | Legacy keywords |
| **`root_cause`** | `varchar` | YES | - | **Canonical Eixo 2 (Natureza)**: 19 valores v3.2 no universo processado. O CHECK ainda aceita alguns valores legacy por compatibilidade |
| **`sentiment`** | `int` | YES | - | LLM-extracted sentiment (1=very negative, 5=very positive) |
| **`key_themes`** | `ARRAY` | YES | - | LLM-extracted themes (max 3, vocabulário canônico 45 termos) |
| **`conversation_summary`** | `text` | YES | - | LLM-generated summary (max 200 chars) |
| **`customer_effort_score`** | `int` | YES | - | LLM-extracted CES (1-7 scale) |
| **`frustration_detected`** | `boolean` | YES | - | LLM-extracted frustration flag |
| **`churn_risk_flag`** | `varchar` | YES | - | LLM-extracted churn risk (`LOW`, `MEDIUM`, `HIGH`) |
| **`llm_confidence`** | `float` | YES | - | LLM confidence [0.0, 1.0] |
| **`service_type`** | `varchar` | YES | - | **Eixo 3 (Atendimento)**: `Bot_Escalado`, `Bot_Resolvido`, `Escalacao_Solicitada`, `Humano_Direto` |
| `atendimento_type` | `varchar` | YES | - | Compatibility mirror used by some app flows. For processed rows, it is expected to match `service_type` |
| `is_proactive` | `boolean` | YES | - | Metadata flag: Capim iniciou o contato via outreach/template outbound |
| `has_interaction` | `boolean` | YES | - | Metadata flag: houve conversa real (`FALSE` when `sem_interacao`) |
| `processing_phase` | `varchar` | YES | - | Canonical processing marker for Phase 3.x / taxonomy-ready rows |
| **`llm_model`** | `varchar` | YES | - | Model used for LLM extraction (ex: `claude-haiku-4-5`) |
| **`llm_processed_at`** | `timestamp` | YES | - | Timestamp of LLM processing. Useful for lineage, but not the preferred population filter when `processing_phase` exists |
| `loaded_at` | `timestamp` | YES | `CURRENT_TIMESTAMP` | ETL load timestamp |
| `version` | `varchar` | YES | `'v1.0_mvp'` | Data version |
| **`full_conversation`** | `text` | YES | - | **Full ticket conversation** (description + up to 5 comments, ~1.2KB avg) |

---

## 2. Key Metrics (as of 2026-03-09)

- **Total rows**: 171,916
- **Processed (`processing_phase IS NOT NULL`)**: 140,267 (81.6%)
- **Unprocessed (`processing_phase IS NULL`)**: 31,649 (18.4%)
- **Eligible backlog** (`processing_phase IS NULL` + `full_conversation` length > 100): 30,787
- **Universe shape**: processed rows are the canonical 3-axis population; unprocessed rows still carry part of the legacy surface

---

## 3. Fill Rates

| Column | Fill Rate | Nulls |
|--------|-----------|-------|
| `clinic_id` | 35.6% | 110,767 |
| `assignee_name` | 89.6% | 17,946 |
| `product_area` | 100% | 0 |
| `product_area_l2` | 81.6% | 31,649 |
| `root_cause` | 81.8% | 31,202 |
| `service_type` | 81.6% | 31,649 |
| `is_proactive` | 81.6% | 31,649 |
| `has_interaction` | 81.6% | 31,649 |
| `processing_phase` | 81.6% | 31,649 |
| `product_area_l1` | 81.9% | 31,202 |
| `atendimento_type` | 81.9% | 31,202 |
| `full_conversation` | 100% | 0 |
| `via_channel` | 100% | 0 |

**Interpretation**:
- Canonical taxonomy coverage is driven by the processed universe
- `product_area_l1` / `atendimento_type` are compatibility mirrors, not the primary contract
- `workflow_type` remains populated as a legacy artifact and should not be used as the main semantic axis

---

## 4. Canonical Coverage Snapshot

### Product Area (processed universe)

| Category | Count | % of processed |
|----------|-------|----------------|
| BNPL | 100,921 | 71.9% |
| SaaS | 24,635 | 17.6% |
| Indeterminado | 11,332 | 8.1% |
| POS | 2,447 | 1.7% |
| Onboarding | 932 | 0.7% |

### Root Cause (processed universe, top values)

| Category | Count | % of processed |
|----------|-------|----------------|
| Cobranca_Ativa | 56,658 | 40.4% |
| Contratacao_Acompanhamento | 23,568 | 16.8% |
| Operational_Question | 11,047 | 7.9% |
| Unclear | 9,971 | 7.1% |
| Endosso_Repasse | 7,262 | 5.2% |

### Atendimento (processed universe)

| Category | Count | % of processed |
|----------|-------|----------------|
| Humano_Direto | 80,570 | 57.4% |
| Bot_Escalado | 34,081 | 24.3% |
| Bot_Resolvido | 24,061 | 17.2% |
| Escalacao_Solicitada | 1,555 | 1.1% |

### Legacy Residue (unprocessed universe)

- Legacy-only `product_area` values still exist in the unprocessed slice
- Non-canonical `root_cause` values found: `unclear` (362), `not_applicable` (77), `debt_collection` (8)
- This is why `processing_phase IS NOT NULL` is the preferred app-facing filter

### Status

| Status | Count | % |
|--------|-------|---|
| closed | 170,289 | 99.1% |
| deleted | 1,444 | 0.8% |
| open | 72 | 0.0% |
| new | 54 | 0.0% |
| hold | 40 | 0.0% |
| pending | 11 | 0.0% |
| solved | 6 | 0.0% |

### Via Channel

| Channel | Count | % |
|---------|-------|---|
| whatsapp | 135,427 | 78.8% |
| native_messaging | 25,676 | 14.9% |
| web | 6,704 | 3.9% |
| email | 3,978 | 2.3% |
| api | 131 | 0.1% |

---

## 5. Full Conversation Quality

| Metric | Value |
|--------|-------|
| Min length | 72 chars |
| Max length | 2,874 chars |
| **Avg length** | **1,240 chars** |
| Median length | 1,274 chars |
| **With comments** | **171,001 (99.5%)** |

**Format**: 
```
=== TICKET DESCRIPTION ===
[ticket description text]

--- Comment 1 by [author_id] ---
[comment text (truncated to 500 chars)]

--- Comment 2 by [author_id] ---
[comment text]
...
```

---

## 6. Indexes

| Index | Type | Columns |
|-------|------|---------|
| `ticket_insights_pkey` | btree | `zendesk_ticket_id` (PK) |
| `idx_clinic_id` | btree | `clinic_id` |
| `idx_created_clinic` | btree | `ticket_created_at DESC, clinic_id` |
| `idx_created_product` | btree | `ticket_created_at DESC, product_area` |
| `idx_product_workflow` | btree | `product_area, workflow_type` |
| `idx_ticket_created_at` | btree | `ticket_created_at DESC` |
| `idx_ticket_updated_at` | btree | `ticket_updated_at DESC` |
| `idx_status` | btree | `status` |
| `idx_via_channel` | btree | `via_channel` |
| `idx_is_claudinha` | btree | `is_claudinha_assigned` |
| `idx_product_area` | btree | `product_area` |
| `idx_workflow_type` | btree | `workflow_type` |
| `idx_full_conversation_gin` | gin | `to_tsvector(full_conversation)` (full-text search) |

---

## 7. Common Queries

### Get tickets for a clinic (last 90 days, canonical population)

```sql
SELECT 
    zendesk_ticket_id,
    ticket_created_at,
    subject,
    product_area,
    product_area_l2,
    root_cause,
    service_type,
    status,
    via_channel
FROM ticket_insights
WHERE clinic_id = <CLINIC_ID>
    AND processing_phase IS NOT NULL
    AND ticket_created_at >= CURRENT_DATE - INTERVAL '90 days'
ORDER BY ticket_created_at DESC;
```

### Top clinics by ticket volume

```sql
SELECT 
    clinic_id,
    COUNT(*) as total_tickets,
    COUNT(CASE WHEN root_cause = 'Cobranca_Ativa' THEN 1 END) as cobranca_tickets,
    COUNT(CASE WHEN product_area = 'SaaS' THEN 1 END) as saas_tickets
FROM ticket_insights
WHERE clinic_id IS NOT NULL
    AND processing_phase IS NOT NULL
    AND ticket_created_at >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY clinic_id
ORDER BY total_tickets DESC
LIMIT 20;
```

### Full-text search in conversations

```sql
SELECT 
    zendesk_ticket_id,
    ticket_created_at,
    subject,
    product_area,
    root_cause,
    ts_headline('portuguese', full_conversation, to_tsquery('portuguese', '<SEARCH_TERM>')) as snippet
FROM ticket_insights
WHERE processing_phase IS NOT NULL
  AND to_tsvector('portuguese', full_conversation) @@ to_tsquery('portuguese', '<SEARCH_TERM>')
ORDER BY ticket_created_at DESC
LIMIT 50;
```

### Temporal trends (monthly aggregation)

```sql
SELECT 
    DATE_TRUNC('month', ticket_created_at) as month,
    COUNT(*) as total_tickets,
    COUNT(CASE WHEN root_cause = 'Cobranca_Ativa' THEN 1 END) as cobranca,
    COUNT(CASE WHEN product_area = 'SaaS' THEN 1 END) as saas,
    ROUND(AVG(LENGTH(full_conversation))::numeric, 0) as avg_conv_length
FROM ticket_insights
WHERE processing_phase IS NOT NULL
  AND ticket_created_at >= CURRENT_DATE - INTERVAL '12 months'
GROUP BY month
ORDER BY month DESC;
```

---

## 8. ETL Pipeline

**Script**: `scripts/backfill_tickets_mvp.py`

**Source**:
- `CAPIM_DATA.SOURCE_STAGING.SOURCE_ZENDESK_TICKETS` (raw Zendesk)
- `CAPIM_DATA.CAPIM_ANALYTICS.ZENDESK_TICKETS_RAW` (enriched with `clinic_id`)
- `CAPIM_DATA.SOURCE_STAGING.SOURCE_ZENDESK_COMMENTS` (comments)

**Transformation**:
1. Fetch tickets from Snowflake (last 365 days)
2. Enrich with clinic attribution (`clinic_id` from multiple sources)
3. Classify Stage 1 (product area) using keyword matching
4. Classify Stage 2 (workflow type) using keyword matching
5. Fetch up to 5 comments per ticket from Snowflake
6. Aggregate comments into `full_conversation` field
7. Upsert to PostgreSQL `vox_popular.ticket_insights`

**Frequency**: On-demand (backfill)

**Sync strategy**: `ON CONFLICT (zendesk_ticket_id) DO UPDATE`

---

## 9. Upstream Dependencies

| Source | Type | Description |
|--------|------|-------------|
| `CAPIM_DATA.SOURCE_STAGING.SOURCE_ZENDESK_TICKETS` | Snowflake | Raw Zendesk tickets |
| `CAPIM_DATA.CAPIM_ANALYTICS.ZENDESK_TICKETS_RAW` | Snowflake | Enriched tickets (with `clinic_id`) |
| `CAPIM_DATA.SOURCE_STAGING.SOURCE_ZENDESK_COMMENTS` | Snowflake | Zendesk comments |

---

## 10. Downstream Dependencies

| Consumer | Type | Usage |
|----------|------|-------|
| `client-voice-app` | Streamlit UI | Dashboards, filters, ticket details |
| Phase 3 / 3.2 scripts | Python scripts | Semantic extraction and taxonomy reprocessing |

---

## 11. Known Issues & Limitations

**See**: `TICKET_INSIGHTS_SEMANTIC.md` § "Known Issues"

**Quick list**:
- `clinic_id` only 35.6% filled (B2C tickets lack clinic attribution)
- `workflow_type` is still present but should be treated as legacy
- ~18.4% of the table is still outside the canonical processed universe (`processing_phase IS NULL`)
- Comments truncated to 500 chars each (to limit payload)
- Only last 5 comments fetched (deep conversations may be incomplete)

---

## 12. Related Entities

| Entity | Relationship | Join Key |
|--------|-------------|----------|
| `SAAS.CLINICS` | MANY tickets → ONE clinic | `clinic_id` |
| `FINTECH.CREDIT_SIMULATIONS` | (planned) Correlation via `clinic_id` + time window | - |
| `SAAS.BUDGETS` | (planned) Correlation via `clinic_id` + time window | - |

---

## 13. Bot Identification — Tags & Signals (Updated 2026-02-13)

### 13.1. Bot Involvement: 4 Camadas de Evidência

`is_claudinha_assigned` sozinho **perde 76.9% dos tickets bot-touched** (é snapshot do assignee final).

**Use as 4 camadas juntas:**

| Camada | Sinal | Cobertura | Confiança | Canal |
|--------|-------|-----------|-----------|-------|
| 1 | Tag `cloudhumans` | 54,684 (31.8%) | Alta | WhatsApp (99.8%) |
| 2 | Tag `transbordo_botweb` | 3,620 (2.1%) | Alta | Native messaging (99.7%) |
| 3 | `is_claudinha_assigned = TRUE` | 28,729 (16.7%) | Alta (precisão), baixa (recall) | Qualquer |
| 4 | Bot self-ID no texto | ~300 (0.2%) | Alta mas rara | Qualquer |

**`cloudhumans`** e **`transbordo_botweb`** são **mutuamente exclusivas** (0 overlap) e representam 2 pipelines de bot:
- `cloudhumans` = plataforma CloudHumans via WhatsApp (desde fev/2025)
- `transbordo_botweb` = escalação formal do bot web (desde dez/2025, crescendo)

### 13.2. Tags `droz_*` — Routing Metadata (NÃO bot identifier)

| Tag Pattern | % de TODOS tickets | Significado | Bot identifier? |
|-------------|:------------------:|-------------|:---:|
| `droz_switchboard` | 93.5% | Infraestrutura Droz (roteamento) | ❌ |
| `droz_receptivo` | ~29% | Inbound ticket | ❌ |
| `droz_ativo` | ~8% | Proactive outreach | ❌ |
| `droz_conversation_*` | - | IDs de sessão (metadata) | ❌ |

### 13.3. Correct Bot Identification

```sql
-- ✅ ALL bot-touched tickets (39.5% do total)
SELECT * FROM ticket_insights 
WHERE is_claudinha_assigned = TRUE
   OR tags ILIKE '%cloudhumans%'
   OR tags ILIKE '%transbordo_botweb%';

-- ✅ Bot resolveu (sem escalação humana)
SELECT * FROM ticket_insights 
WHERE (is_claudinha_assigned = TRUE 
       OR tags ILIKE '%cloudhumans%')
  AND NOT (tags ILIKE '%cloudhumans%' AND is_claudinha_assigned = FALSE)
  AND tags NOT ILIKE '%transbordo_botweb%';

-- ✅ Bot tocou, humano assumiu (escalação)
SELECT * FROM ticket_insights 
WHERE (tags ILIKE '%cloudhumans%' AND is_claudinha_assigned = FALSE)
   OR (tags ILIKE '%transbordo_botweb%' AND is_claudinha_assigned = FALSE);

-- ✅ Human-only (sem evidência de bot)
SELECT * FROM ticket_insights 
WHERE is_claudinha_assigned = FALSE
  AND (tags NOT ILIKE '%cloudhumans%' OR tags IS NULL)
  AND (tags NOT ILIKE '%transbordo_botweb%' OR tags IS NULL);

-- ❌ WRONG: ONLY is_claudinha (perde 76.9% dos bot-touched)
SELECT * FROM ticket_insights WHERE is_claudinha_assigned = TRUE;

-- ❌ WRONG: droz_switchboard (93.5% dos tickets, não seletivo)
SELECT * FROM ticket_insights WHERE tags LIKE '%droz_switchboard%';
```

### 13.4. Distribuição de Sinais de Bot (N=171,916)

| Grupo | Count | % |
|-------|------:|--:|
| Sem evidência de bot | 104,034 | 60.5% |
| CloudHumans (claudinha=FALSE) | 37,109 | 21.6% |
| CloudHumans (claudinha=TRUE) | 17,575 | 10.2% |
| Claudinha assigned (sem tag) | 9,578 | 5.6% |
| Transbordo (claudinha=FALSE) | 2,044 | 1.2% |
| Transbordo (claudinha=TRUE) | 1,576 | 0.9% |

### 13.5. Bot Quality Metrics

| Metric | Claudinha (bot) | Humano | Δ (pp) |
|--------|-----------------|--------|--------|
| **n** | 6,591 (27.3%) | 17,557 (72.7%) | - |
| **avg_conf** | 0.688 | 0.805 | -11.7 |
| **junk_rate** | 40.37% | 17.83% | +22.54 |
| **unclear_rate** | 39.49% | 11.68% | +27.81 |

**Nota**: Métricas baseadas em `is_claudinha_assigned` (snapshot). Tickets onde bot tocou mas humano assumiu (`cloudhumans + claudinha=FALSE`) podem ter qualidade diferente.

### 13.6. Related Scripts

| Script | Purpose |
|--------|---------|
| `_scratch/investigate_droz_tags.py` | Droz tags como proxy de bot (2026-02-13) |
| `_scratch/investigate_transbordo_cloudhumans.py` | Discovery cloudhumans vs transbordo (2026-02-13) |
| `scripts/analyze_claudinha_performance.py` | Bot vs human quality metrics |
| `scripts/reprocess_tickets_full_taxonomy.py` | Classification pipeline (3-axis + LLM) |

---

**See also**: `TICKET_INSIGHTS_SEMANTIC.md` for business context and semantic details.
