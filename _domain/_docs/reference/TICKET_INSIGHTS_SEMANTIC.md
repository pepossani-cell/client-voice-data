# TICKET_INSIGHTS — Semantic Documentation

> **Purpose**: Business context and semantic understanding of `ticket_insights`  
> **Domain**: CLIENT_VOICE  
> **Layer**: SANDBOX (THIS_PROJECT_OWNS)  
> **Last Updated**: 2026-03-09 (audit-aligned)

---

## 1. Purpose & Business Context

`ticket_insights` is the **consolidated, enriched operational table** for Voice of Customer (VoC) analytics. It brings together:

1. **Raw Zendesk tickets** (from Data Engineering's `SOURCE_STAGING`)
2. **Clinic attribution** (from multiple enrichment sources)
3. **Stage 1+2 classification** (product area & workflow type, keyword-based)
4. **Full conversation context** (description + comments) for LLM semantic extraction (Phase 3)

**This table enables**:
- **VoC dashboards** (`client-voice/`) for support health monitoring
- **Root cause analysis** via full conversation content
- **Cross-domain correlation** (linking support tickets to SAAS/FINTECH events)
- **LLM semantic extraction** (Phase 3: sentiment, themes, customer intent)

**Ownership**: This project (`client-voice-data`) owns the ETL, schema, and enrichment logic.

---

## 2. Grain

**ONE ROW = ONE ZENDESK TICKET**

- Primary Key: `zendesk_ticket_id` (bigint, unique)
- Time anchor: `ticket_created_at` (UTC)
- Update tracking: `ticket_updated_at`, `loaded_at`

**Invariants**:
- Every ticket appears exactly once
- `zendesk_ticket_id` is immutable
- Upsert strategy: `ON CONFLICT (zendesk_ticket_id) DO UPDATE` (latest wins)

---

## 3. Key Columns — Semantic Meaning

### 3.1. Identity & Temporal

| Column | Meaning |
|--------|---------|
| `zendesk_ticket_id` | Zendesk's internal ticket ID (PK, immutable) |
| `ticket_created_at` | **When customer first raised the issue** (UTC) |
| `ticket_updated_at` | Last activity on ticket (any update, comment, status change) |
| `loaded_at` | ETL timestamp (when we last synced this row) |

### 3.2. Attribution & Context

| Column | Meaning |
|--------|---------|
| **`clinic_id`** | **Capim clinic ID** (links to SAAS domain) — ONLY for B2B tickets (35.6% fill rate) |
| `clinic_id_source` | How we attributed clinic: `zendesk_raw` (46% reliable), `ticket_form`, `email_hash`, `none` |
| `assignee_name` | Support agent who handled ticket (89.6% filled) |
| **`is_claudinha_assigned`** | **TRUE if bot (Claudinha) is CURRENT assignee** — snapshot, NOT history. Perde 76.9% dos bot-touched (see § 3.2.1) |
| `via_channel` | Entry point: `whatsapp` (78.8%), `native_messaging`, `web`, `email`, `api` |
| `status` | Zendesk status: `closed` (99.1%), `deleted`, `open`, `new`, `hold`, `pending`, `solved` |
| `tags` | Zendesk tags (comma-separated) — **KEY**: `cloudhumans` (31.8%) e `transbordo_botweb` (2.1%) são sinais de bot (see § 3.2.1) |

**B2B vs B2C distinction**:
- **B2B tickets**: Clinics contacting Capim support (have `clinic_id`)
- **B2C tickets**: Patients contacting Capim support (NO `clinic_id`)
- **Implication**: When `clinic_id IS NULL`, interpret as "patient ticket" (not clinic-related)

#### 3.2.1. Bot (Claudinha) Identification ⚠️ CRITICAL (Updated 2026-02-13)

**Use 4 camadas de evidência para identificar bot involvement.**

`is_claudinha_assigned` sozinho **perde 76.9% dos tickets bot-touched** porque é um snapshot (assignee final), não histórico. Quando ClaudIA escala, o assignee muda para humano.

**4 Camadas de evidência (por ordem de prioridade)**:

| Camada | Sinal | Significado | Volume | Confiança |
|--------|-------|-------------|--------|-----------|
| 1 | Tag `cloudhumans` | Ticket passou pela plataforma CloudHumans/ClaudIA via WhatsApp | 54,684 (31.8%) | **Alta** |
| 2 | Tag `transbordo_botweb` | Escalação formal do bot no native messaging | 3,620 (2.1%) | **Alta** |
| 3 | `is_claudinha_assigned = TRUE` | Bot é assignee ATUAL (snapshot) | 28,729 (16.7%) | **Alta (precisão), baixa (recall)** |
| 4 | Bot self-ID no texto | "sou a claudia", "sou a assistente virtual" | ~300 (0.2%) | Alta mas rara |

**Descoberta empírica (2026-02-13)**:
- `cloudhumans` e `transbordo_botweb` são **mutuamente exclusivas** (0 overlap)
- `cloudhumans` = WhatsApp bot (99.8% via WhatsApp)
- `transbordo_botweb` = Native messaging bot (99.7% via native_messaging, desde Dez/2025)
- `droz_*` tags (93.5% dos tickets) são **infraestrutura de roteamento**, NÃO sinais de bot

**Distribuição global de sinais de bot (N=171,916)**:

| Grupo | Count | % |
|-------|-------|---|
| Sem evidência de bot | 104,034 | 60.5% |
| CloudHumans (claudinha=FALSE, humano assumiu) | 37,109 | 21.6% |
| CloudHumans (claudinha=TRUE, bot resolveu) | 17,575 | 10.2% |
| Claudinha assigned (sem tag) | 9,578 | 5.6% |
| Transbordo (claudinha=FALSE, escalado) | 2,044 | 1.2% |
| Transbordo (claudinha=TRUE, resolvido N1) | 1,576 | 0.9% |

**Correct usage**:
```sql
-- ✅ CORRECT: Identify ALL bot-touched tickets (39.5% do total)
SELECT * FROM ticket_insights 
WHERE is_claudinha_assigned = TRUE
   OR tags ILIKE '%cloudhumans%'
   OR tags ILIKE '%transbordo_botweb%';

-- ✅ Bot resolveu (sem escalação humana)
SELECT * FROM ticket_insights 
WHERE is_claudinha_assigned = TRUE
   AND tags NOT ILIKE '%transbordo_botweb%';

-- ✅ Bot tocou mas humano assumiu (escalação)
SELECT * FROM ticket_insights 
WHERE tags ILIKE '%cloudhumans%'
   AND is_claudinha_assigned = FALSE;

-- ❌ WRONG: ONLY is_claudinha (perde 76.9% dos bot-touched)
SELECT * FROM ticket_insights WHERE is_claudinha_assigned = TRUE;

-- ❌ WRONG: droz_switchboard (93.5% dos tickets, não seletivo)
SELECT * FROM ticket_insights WHERE tags LIKE '%droz_switchboard%';
```

**Tags `droz_*` — routing metadata, NÃO bot identifier**:
- `droz_switchboard`: 93.5% de TODOS os tickets (bot + humano) — infraestrutura Droz
- `droz_receptivo`: ~29-45% dos tickets — inbound (crescendo)
- `droz_ativo`: ⚠️ **~3% e caindo** (era 30.6% em Ago/2025 → 3.0% em Fev/2026). **Tag morrendo — NÃO usar como sinal de proatividade.** Usar lista curada de templates outbound (ver `TAXONOMY_3_AXES.md` § Metadata Complementar).
- `droz_conversation_*` / `droz_talk_*`: IDs de sessão (metadata)

**Quality metrics (bot vs human, last 3 months)**:

| Metric | Claudinha (bot) | Humano | Δ (pp) |
|--------|-----------------|--------|--------|
| **Tickets** | 6,591 (27.3%) | 17,557 (72.7%) | - |
| **avg_conf** | 0.688 | 0.805 | -11.7 |
| **low_conf_rate** | 30.71% | 8.15% | +22.56 |
| **unclear_rate** | 39.49% | 11.68% | +27.81 |
| **junk_rate** | 40.37% | 17.83% | +22.54 |
| **avg_sentiment** | 2.936 | 2.816 | +0.12 |

**Key finding**: Bot tickets have **significantly lower quality** (40% junk rate, 30% low confidence, 39% unclear) compared to human-handled tickets.

**Source**: `_scratch/investigate_droz_tags.py`, `_scratch/investigate_transbordo_cloudhumans.py`, `scripts/analyze_claudinha_performance.py`

### 3.3. Classification (3-Axis Taxonomy)

> **Schema status**: `product_area`, `product_area_l2`, `root_cause`, `service_type`, `via_channel`, `is_proactive`, `has_interaction`, `llm_processed_at` e `processing_phase` já existem na base.  
> `workflow_type` permanece como coluna legacy. `product_area_l1` e `atendimento_type` existem como colunas de compatibilidade sincronizadas com os campos canônicos no universo processado.  
> **See**: `TAXONOMY_3_AXES.md` for full specification.

**Classification model**: **Produto × Natureza × Atendimento** (3 orthogonal axes)

---

#### Eixo 1: PRODUTO (product_area / product_area_l2)

**Semantic**: Which **product/area** does this ticket relate to?

**L1 (5 valores principais)**:

| Value | Meaning | Volume % |
|-------|---------|:--------:|
| `BNPL` | Crédito parcelado, cobrança, endosso | 28.3% |
| `SaaS` | Plataforma clínica, agenda, orçamento | 40.1% |
| `Onboarding` | Venda, credenciamento, ativação | 10.2% |
| `POS` | Maquininha Capininha (hardware) | 8.7% |
| `Indeterminado` | Não foi possível determinar | 12.7% |

**L2 (subcategorias)**:

- **BNPL**: `Cobranca`, `Servicing`, `Originacao`, `Contratacao`
- **SaaS**: `Clinico`, `Conta`, `Lifecycle`
- **Onboarding**: `Credenciamento`, `Ativacao`
- **POS**: `Entrega`, `Operacao`, `Configuracao`

**Canonical columns**: `product_area` (L1) + `product_area_l2` (L2)  
**Compatibility mirror**: `product_area_l1`  
**Classification method**: Deterministic (tags) → LLM context (Prompt Compiler 5-layer)  
**Confidence**: `product_confidence` [0.0, 1.0] — target: <12% Indeterminado

---

#### Eixo 2: NATUREZA (root_cause)

**Semantic**: What is the **nature** of the problem/inquiry?

**19 valores v3.2** (grouped logically):

| Categoria | Valores | Descrição |
|-----------|---------|-----------|
| **Funil BNPL** (5) | Simulacao_Credito, Contratacao_Acompanhamento, Contratacao_Suporte_Paciente, Endosso_Repasse, Cobranca_Ativa | C1 → C2 follow-up → C2 fricção → C2S → Post-C2S |
| **Processos** (3) | Credenciamento, Migracao, Process_Generico | Workflows operacionais |
| **Assinatura SaaS** (2) | Subscription_Pagamento, Subscription_Cancelamento | Billing SaaS e churn |
| **Financeiro/Transacional** (3) | Financial_Inquiry, Forma_Pagamento, Negativacao | Consultas e cobranças |
| **Suporte/Técnico** (3) | Operational_Question, Technical_Issue, Acesso | Dúvidas, bugs, login |
| **Cross-cutting** (3) | Carne_Capim, Alteracao_Cadastral, Unclear | Específicos + catch-all |

**Mudanças v3.1→v3.2 (2026-02-13)**:
- `Contratacao` split em 2 Naturezas: `Contratacao_Acompanhamento` (follow-up genérico) + `Contratacao_Suporte_Paciente` (fricção telefone/docs/assinatura)
- `venda_dificuldade_na_assinatura` absorvido por `Technical_Issue`
- Tags `venda_*` movidas de Onboarding para BNPL (correção semântica: venda de financiamento, não SaaS)
- Funil BNPL expandido: 4 → 5 etapas
- `Financial_Issue` absorvido por `Endosso_Repasse` (0.03%)
- Novos: `Acesso`, `Carne_Capim`, `Alteracao_Cadastral`
- Tags `n2_*` adicionadas como sinais Tier 1 (25 tags, 7/7 meses estáveis)
- `saas_login` rebaixado de HIGH → MEDIUM confidence (trust 53.3%)

**Classification method**: Deterministic signals (Tier 1, expandido com `n2_*`) → LLM semantic extraction (Tier 2)  
**Confidence**: `llm_confidence` [0.0, 1.0] — target: <15% Unclear  
**Full specification**: `TAXONOMY_3_AXES.md` v3.2

---

#### Eixo 3: ATENDIMENTO (service_type)

**Semantic**: How was the ticket **handled**? (bot vs human)

| Value | Meaning | Volume % (estimado) |
|-------|---------|:--------:|
| `Bot_Escalado` | Bot tocou o ticket, humano assumiu | ~25-30% |
| `Bot_Resolvido` | Bot resolveu sem intervenção humana | ~15-17% |
| `Escalacao_Solicitada` | Cliente pediu humano explicitamente | ~3-5% |
| `Humano_Direto` | Sem evidência de envolvimento do bot | ~55-60% |

**Classification method**: 4 camadas de evidência → pipeline determinístico (7 passos)
**Data sources**: tags (`cloudhumans`, `transbordo_botweb`), `is_claudinha_assigned`, conversation text (escalation/self-ID patterns)

**⚠️ CRITICAL**: `is_claudinha_assigned` sozinho perde 76.9% dos bot-touched. Usar em conjunto com `cloudhumans` e `transbordo_botweb` (see § 3.2.1). Full logic: `TAXONOMY_3_AXES.md`

---

#### Metadata Complementar

**`via_channel`** (canal físico, NOT taxonômico):

| Value | Volume % | Meaning |
|-------|:--------:|---------|
| `whatsapp` | 78.8% | WhatsApp Business |
| `native_messaging` | 14.9% | Widget de chat nativo (web) |
| `web` | 3.9% | Formulário web |
| `email` | 2.3% | Email support |
| `api` | 0.1% | Integrações via API |

**Nota**: NÃO existe `phone`, `voice` ou `mobile` na base. 100% digital.

---

**`is_proactive`** (boolean — direção do contato, NEW v3.1):

| Value | Meaning | Volume % |
|-------|---------|:--------:|
| `TRUE` | Capim iniciou o contato (outbound template curado) | ~30% |
| `FALSE` | Cliente iniciou o contato (inbound/reativo) | ~70% |

**Derivation**: Lista curada de templates outbound (auditoria 78K tickets). Duas espécies: **outbound humano** (identificados por alta correlação com `droz_ativo` durante auditoria) e **sistema automatizado** (100% `grupo_cobranca`). Templates de resposta (>60% receptivo) são excluídos. A flag final usa **apenas a whitelist de templates**, não `droz_ativo` (tag morrendo — NÃO usada em runtime).

**⚠️ Impacto**: Tickets proativos NÃO são "voz do cliente" orgânica. Filtrar de análises de sentiment/NPS. Incluir em análises de efetividade de outreach.

**Full specification**: `TAXONOMY_3_AXES.md` § Metadata Complementar.

---

**`has_interaction`** (boolean — houve conversa real?, NEW v3.1):

| Value | Meaning | Volume % |
|-------|---------|:--------:|
| `TRUE` | Conversa real aconteceu | ~87% |
| `FALSE` | Tag `sem_interacao` — ticket sem conversa real | ~13% |

**⚠️ Impacto**: Tickets sem interação têm classificação LLM de baixa confiança (69% sentiment neutro=3). Filtrar de análises de sentiment. Útil para medir taxa de resposta de outreach (`is_proactive AND NOT has_interaction`).

---

**Uso combinado**: Análises complementares, não eixos taxonômicos principais.

**Exemplos de uso**:
```sql
-- Voz do cliente orgânica (filtra proativo + sem_interacao)
SELECT * FROM ticket_insights
WHERE is_proactive = FALSE AND has_interaction = TRUE;

-- Taxa de resposta de outreach proativo
SELECT 
  COUNT(*) as total_outreach,
  COUNT(CASE WHEN has_interaction THEN 1 END) as respondido,
  ROUND(100.0 * COUNT(CASE WHEN has_interaction THEN 1 END) / COUNT(*), 1) as taxa_resposta
FROM ticket_insights
WHERE is_proactive = TRUE;

-- Sentiment orgânico (exclui ruído)
SELECT AVG(sentiment) as avg_sentiment
FROM ticket_insights
WHERE is_proactive = FALSE 
  AND has_interaction = TRUE
  AND sentiment IS NOT NULL;
```

### 3.4. Full Conversation

**`full_conversation`** (text, 100% filled, avg 1.2KB):

**Semantic**: Complete ticket conversation history for semantic extraction.

**Format**:
```
=== TICKET DESCRIPTION ===
[customer's original message]

--- Comment 1 by [author_id] ---
[agent or customer response, truncated to 500 chars]

--- Comment 2 by [author_id] ---
[next response]
...
```

**Construction logic**:
- Ticket description (full text)
- Up to **5 comments** (ordered by `created_at`)
- Each comment truncated to **500 chars** (to limit payload)

**Quality**:
- 99.5% of tickets have comments (only 0.5% have `[No comments]`)
- Avg length: 1,240 chars (sufficient for LLM context)
- Max length: 2,874 chars

**Phase 3 usage**: LLM extracts (7 variáveis, decisão 20.7a):
- `root_cause` (19 valores canônicos v3.2 — see Eixo 2)
- `sentiment` (1-5 scale)
- `key_themes` (array, max 3, vocabulário canônico 45 termos)
- `conversation_summary` (max 200 chars)
- `customer_effort_score` (1-7 scale)
- `frustration_detected` (boolean)
- `churn_risk_flag` (LOW/MEDIUM/HIGH)
- `llm_confidence` (0.0-1.0)

**Rejected**: `customer_intent` (redundante com root_cause), `urgency_level` (post-hoc, não extraível).

---

## 4. Relationships

### 4.1. SAAS Domain (Clinics)

**Join key**: `clinic_id` (bigint)

```sql
-- Link tickets to clinic metadata
SELECT 
    t.zendesk_ticket_id,
    t.ticket_created_at,
    t.product_area,
    t.root_cause,
    c.clinic_name,
    c.is_active,
    c.subscription_tier
FROM ticket_insights t
JOIN CAPIM_DATA.DASH_PRODUCTION.CLINICS c 
    ON t.clinic_id = c.clinic_id
WHERE t.clinic_id IS NOT NULL;
```

**Semantic**:
- Enables **clinic health diagnostics** (ticket volume + types as health signal)
- Supports **churn analysis** (spike in `Cobranca_Ativa` / BNPL `root_cause` values before churn?)
- **Limitation**: Only 35.6% of tickets have `clinic_id` (B2B only)

### 4.2. FINTECH Domain (Credit Events) — Planned

**No direct FK**, use fuzzy join:

```sql
-- Correlate debt collection tickets with credit events
SELECT 
    t.zendesk_ticket_id,
    t.ticket_created_at,
    t.root_cause,
    cs.simulation_id,
    cs.rejection_reason
FROM ticket_insights t
JOIN CAPIM_DATA.DASH_PRODUCTION.CREDIT_SIMULATIONS cs
    ON t.clinic_id = cs.clinic_id
    AND cs.created_at BETWEEN t.ticket_created_at - INTERVAL '7 days' 
                           AND t.ticket_created_at + INTERVAL '1 day'
WHERE t.root_cause IN ('Cobranca_Ativa', 'Simulacao_Credito', 'Contratacao_Acompanhamento', 'Contratacao_Suporte_Paciente', 'Endosso_Repasse');
```

**Semantic**: Did a credit rejection trigger a support ticket?

### 4.3. Multi-Domain Join (Clinic Health Check)

**Use case**: `@clinic-health-check <clinic_id>` skill

```sql
-- Combine support health with operational health
SELECT 
    t.clinic_id,
    COUNT(*) as ticket_count,
    COUNT(CASE WHEN t.root_cause IN ('Cobranca_Ativa', 'Simulacao_Credito', 'Contratacao_Acompanhamento', 'Contratacao_Suporte_Paciente', 'Endosso_Repasse') THEN 1 END) as bnpl_tickets,
    AVG(b.budget_value) as avg_budget_value,
    COUNT(a.appointment_id) as appointment_count
FROM ticket_insights t
LEFT JOIN SAAS.BUDGETS b ON t.clinic_id = b.clinic_id 
    AND b.created_at >= CURRENT_DATE - 90
LEFT JOIN SAAS.APPOINTMENTS a ON t.clinic_id = a.clinic_id 
    AND a.created_at >= CURRENT_DATE - 90
WHERE t.clinic_id = <CLINIC_ID>
    AND t.ticket_created_at >= CURRENT_DATE - 90
GROUP BY t.clinic_id;
```

**Semantic**: Support health as leading indicator for operational/financial health

---

## 5. Usage Patterns

### 5.1. When to Use This Entity

✅ **Use `ticket_insights` when**:
- Analyzing **support health metrics** (volume, product area mix, workflow types)
- Building **VoC dashboards** (temporal trends, top clinics, channel distribution)
- **Correlating support with business events** (SAAS/FINTECH)
- **Preparing LLM extraction** (Phase 3: semantic analysis of `full_conversation`)
- **Root cause analysis** (drill down into specific ticket conversations)

❌ **Don't use `ticket_insights` when**:
- Need **real-time ticket status** (use Snowflake `SOURCE_ZENDESK_TICKETS` instead)
- Need **all comments** (we only fetch first 5, truncated to 500 chars each)
- Need **Zendesk metadata** (custom fields, attachments, etc.) → use raw Snowflake
- Analyzing **pre-Feb 2025 tickets** (only 12 months backfilled)

### 5.2. Common Analysis Patterns

#### Pattern 1: Clinic Health Diagnostic

**Question**: "Is clinic X having support issues?"

**Query logic**:
1. Count tickets for clinic in last 90 days
2. Segment by `root_cause` (especially `Cobranca_Ativa` as red flag) and `product_area`
3. Check if spike vs historical average
4. Cross-reference with SAAS/FINTECH metrics

#### Pattern 2: Product Area Trends

**Question**: "Are cobrança tickets increasing?"

**Query logic**:
1. Aggregate by month + `root_cause` (v3: `Cobranca_Ativa`, `Simulacao_Credito`, etc.)
2. Calculate month-over-month change
3. Flag significant increases (>20%)

#### Pattern 3: Root Cause Investigation

**Question**: "Why are we getting so many [X] tickets?"

**Query logic**:
1. Filter by `product_area` / `root_cause` / `service_type` (v3 taxonomy axes)
2. Sample `full_conversation` (random 50 tickets)
3. Manual review OR Phase 3 LLM extraction
4. Group by `root_cause` (19 valores v3.2)

#### Pattern 4: Channel Effectiveness

**Question**: "Do WhatsApp tickets resolve faster?"

**Query logic**:
1. Calculate `resolution_time = ticket_updated_at - ticket_created_at`
2. Segment by `via_channel`
3. Compare median resolution times

---

## 6. Known Issues & Caveats

### 6.1. Clinic Attribution Gap (35.6% fill rate)

**Issue**: `clinic_id` is NULL for 64.4% of tickets.

**Why**:
- **B2C tickets** (patients) don't have clinic context
- Zendesk ticket forms don't always capture clinic ID
- Email hashing attribution has limited coverage

**Workaround**:
- Use `clinic_id_source` to assess attribution quality
- For B2C analysis, accept `clinic_id IS NULL` as valid state
- Future: Improve attribution via LLM entity extraction (Phase 3+)

### 6.2. Legacy Stage 2 Classification (DEPRECATED)

**Status**: `workflow_type` (Stage 2) é **LEGACY** — substituída pela taxonomia 3 eixos (Produto × Natureza × Atendimento).

**Old issue**: 67.4% "Indeterminado" no Stage 2 keyword-based.

**New approach (2026-02-12+)**: 
- **Eixo 1 (Produto)**: Determinístico por tags/themes. Target: <12% Indeterminado.
- **Eixo 2 (Natureza)**: Deterministic Tier 1 (n2_* tags expandidas) + LLM Tier 2 → `root_cause` (19 valores v3.2). Target: <15% Unclear.
- **Eixo 3 (Atendimento)**: Determinístico por tags (`cloudhumans`, `transbordo_botweb`) + `is_claudinha_assigned` + texto.

**See**: `TAXONOMY_3_AXES.md` para lógica completa.

### 6.3. Comment Truncation

**Issue**: Comments truncated to 500 chars each, only first 5 fetched.

**Why**: Balance between completeness and payload size (LLM token limits)

**Workaround**:
- For deep investigations, query Snowflake `SOURCE_ZENDESK_COMMENTS` directly
- 99.5% of tickets have comments → truncation is minor issue

### 6.4. Historical Data Limitation

**Issue**: Only 12 months backfilled (Feb 2025 - Feb 2026).

**Why**: Backfill runtime constraint (~3 hours for 172K tickets).

**Workaround**:
- For older tickets, query Snowflake directly
- Future: Incremental backfill for historical periods if needed

---

## 7. Quality Checks

**Validation queries** (run periodically):

### Check 1: PK uniqueness

```sql
SELECT COUNT(*), COUNT(DISTINCT zendesk_ticket_id)
FROM ticket_insights;
-- Should be equal
```

### Check 2: Temporal sanity

```sql
SELECT 
    MIN(ticket_created_at) as oldest,
    MAX(ticket_created_at) as newest,
    MAX(loaded_at) as last_load
FROM ticket_insights;
-- oldest >= 2025-02-09
-- newest <= CURRENT_DATE
-- last_load ~ recent
```

### Check 3: Full conversation quality

```sql
SELECT 
    COUNT(*) as total,
    COUNT(CASE WHEN full_conversation LIKE '%--- Comment%' THEN 1 END) as with_comments,
    AVG(LENGTH(full_conversation))::int as avg_length
FROM ticket_insights;
-- with_comments >= 99%
-- avg_length >= 1000 chars
```

### Check 4: Classification coverage

```sql
-- v3 taxonomy coverage (root_cause, service_type)
SELECT 
    COUNT(CASE WHEN root_cause = 'Unclear' OR root_cause IS NULL THEN 1 END)::float / COUNT(*) as natureza_gap,
    COUNT(CASE WHEN service_type IS NULL THEN 1 END)::float / COUNT(*) as atendimento_gap,
    -- Legacy columns (backwards compat)
    COUNT(CASE WHEN product_area = 'Indeterminado' THEN 1 END)::float / COUNT(*) as legacy_stage1_gap
FROM ticket_insights;
-- natureza_gap target: < 15%
-- atendimento_gap target: < 5%
-- legacy_stage1_gap < 35% (acceptable, legacy)
```

---

## 8. Failure Modes

**See**: `LESSONS_LEARNED.md` in `capim-meta-ontology/_memory/`

**Critical bugs fixed**:
1. **Bug**: `full_conversation` truncated due to incorrect Snowflake column names
   - **Symptom**: Avg length ~100 chars (should be ~1200)
   - **Fix**: Corrected column references in `backfill_tickets_mvp.py`
   - **Date**: 2026-02-09

2. **Bug**: `ON CONFLICT DO UPDATE` missing `full_conversation` field
   - **Symptom**: Re-runs didn't update `full_conversation`
   - **Fix**: Added field to UPDATE clause
   - **Date**: 2026-02-09

**Monitoring**:
- Run `scripts/validate_comments_loaded.py` after backfills
- Check avg `full_conversation` length (should be ~1200 chars)
- Verify 99%+ comment coverage

---

## 9. Phase 3 Status (LLM Semantic Extraction)

### Columns already created in PostgreSQL:

| Column | Type | Status | Description |
|--------|------|--------|-------------|
| `root_cause` | varchar | ✅ Active | 19 valores canônicos v3.2 no universo processado; CHECK ainda aceita alguns valores legacy |
| `sentiment` | int | ✅ Active | 1-5 scale |
| `key_themes` | ARRAY | ✅ Active | Max 3, vocabulário canônico 45 termos |
| `conversation_summary` | text | ✅ Active | Max 200 chars |
| `customer_effort_score` | int | ✅ Active | 1-7 scale |
| `frustration_detected` | boolean | ✅ Active | Flag de frustração |
| `churn_risk_flag` | varchar | ✅ Active | LOW/MEDIUM/HIGH |
| `llm_confidence` | float | ✅ Active | 0.0-1.0 |
| `product_area` | varchar | ✅ Active | Eixo Produto L1 canônico |
| `product_area_l2` | varchar | ✅ Active | Subcategoria L2 (12 valores) |
| `service_type` | varchar | ✅ Active | Eixo Atendimento (4 valores) |
| `product_area_l1` | varchar | ✅ Compatibility | Espelho de compatibilidade de `product_area` no universo processado |
| `atendimento_type` | varchar | ✅ Compatibility | Espelho de compatibilidade de `service_type` no universo processado |
| `via_channel` | varchar | ✅ Active | Canal físico de entrada (metadata, não eixo taxonômico) |
| `is_proactive` | boolean | ✅ Active | Flag: Capim iniciou contato (template outbound curado, ~30%) |
| `has_interaction` | boolean | ✅ Active | Flag: conversa real (NOT sem_interacao, ~87%) |
| `processing_phase` | varchar | ✅ Active | Marcador canônico da população processada / Phase 3.x |
| `llm_model` | varchar | ✅ Active | Modelo usado para extração |
| `llm_processed_at` | timestamp | ✅ Active | Timestamp de processamento LLM; útil para lineage, mas não é o filtro canônico preferencial quando `processing_phase` existe |

**ETL**: `scripts/reprocess_tickets_full_taxonomy.py` (LLM + deterministic rules)

**Cost estimate (batch API)**: ~$132-156 para 171K tickets (3-tier: Opus 4.6 / Sonnet 4.5 / Haiku 4.5, com 50% batch discount)

### Phase 4: Real-time Sync

**Goal**: Keep `ticket_insights` near-real-time (daily sync).

**Approach**:
- Incremental load (only new/updated tickets since last `loaded_at`)
- Run via cron or GitHub Actions
- Sync latency: < 24 hours

### Phase 5: Improved Clinic Attribution

**Goal**: Increase `clinic_id` fill rate from 35.6% to 60%+.

**Approach**:
- LLM entity extraction from `full_conversation`
- Cross-reference with SAAS clinic names/emails
- Fuzzy matching on clinic metadata

---

## 10. Meta-Ontology Registration

**Status**: NOT YET REGISTERED in `capim-meta-ontology`

**Reason**: Cross-domain joins (CLIENT_VOICE ↔ SAAS/FINTECH) not yet production-critical.

**When to register**:
- When Phase 3 implements correlation workflows
- When `@clinic-health-check` skill uses `ticket_insights` as core component
- When FINTECH/SAAS teams depend on `ticket_insights` for their analyses

**Registration plan**:
```yaml
# capim-meta-ontology/_federation/CROSS_DOMAIN_GLUE.yaml
- name: "Support Tickets to Clinics"
  left_domain: CLIENT_VOICE
  left_entity: ticket_insights
  right_domain: SAAS
  right_entity: CLINICS
  join_on: clinic_id
  match_type: EXACT
  coverage: 35.6%
  caveats: "Only B2B tickets have clinic_id"
```

---

**See also**: `TICKET_INSIGHTS.md` (data dictionary) for schema details and queries.
