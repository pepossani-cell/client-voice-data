# Taxonomy Migration Guide — Legacy → v2.1

> **Purpose**: Historical guide for the original migration from Stage 1/2 to the 3-axis taxonomy  
> **Target Audience**: Data engineers, analysts, skill authors  
> **Last Updated**: 2026-03-09  
> **Status**: Historical / partially superseded by current runtime state

## Current State Note

This document preserves the original migration framing, but it is **not** the current schema contract.

Current canonical state:
- `ticket_insights` already contains `product_area`, `product_area_l2`, `root_cause`, `service_type`, `is_proactive`, `has_interaction`, `llm_processed_at`, and `processing_phase`
- `product_area_l1` and `atendimento_type` remain as compatibility mirrors for some consumers
- the processed universe follows **19 Natureza values (v3.2)**, not the earlier 15-value draft
- the preferred app-facing filter is `processing_phase IS NOT NULL`

For the current contract, use:
- `../reference/TICKET_INSIGHTS_SEMANTIC.md`
- `../../docs/reference/TICKET_INSIGHTS.md`
- `../START_HERE.md`
- `TAXONOMY_3_AXES.md`

---

## 📋 Executive Summary

**What changed**: Complete redesign of ticket classification taxonomy.

**Old model** (deprecated 2026-02-12):
```
Ticket Classification = Product_Area (Stage 1) × Workflow_Type (Stage 2)
```

**New model** (original v2.1 target, superseded by v3.2 semantics):
```
Ticket Classification = Produto (L1/L2) × Natureza (19 valores v3.2 no estado atual) × Atendimento (4 valores)
```

**Impact**:
- ✅ **Higher coverage**: Indeterminado <12% (was 32%), Unclear <18% (was 67%)
- ✅ **Better semantics**: Natureza (root causes) vs Workflow (intent)
- ✅ **Clearer orthogonality**: Produto, Natureza, Atendimento are independent dimensions
- ⚠️ **Breaking change**: Column names changed, values changed, new logic

---

## 🔄 Schema Migration

### Legacy Schema Snapshot

```sql
-- ticket_insights (current state)
CREATE TABLE ticket_insights (
    zendesk_ticket_id BIGINT PRIMARY KEY,
    
    -- Legacy classification
    product_area VARCHAR,              -- OLD: 7 valores (BNPL_Cobranca, SaaS_Operacional, etc.)
    product_area_confidence FLOAT,
    workflow_type VARCHAR,             -- OLD: 6 valores (Suporte_L2, Info_L1, etc.)
    workflow_confidence FLOAT,
    
    -- Core fields (unchanged)
    ticket_created_at TIMESTAMP,
    ticket_updated_at TIMESTAMP,
    clinic_id BIGINT,
    assignee_name VARCHAR,
    is_claudinha_assigned BOOLEAN,
    via_channel VARCHAR,
    tags TEXT,
    full_conversation TEXT,
    loaded_at TIMESTAMP
);
```

### Historical Target Schema

```sql
-- ticket_insights (target state, v2.1)
CREATE TABLE ticket_insights (
    zendesk_ticket_id BIGINT PRIMARY KEY,
    
    -- NEW: 3-axis classification
    product_area_l1 VARCHAR,           -- compatibility mirror of canonical `product_area`
    product_area_l2 VARCHAR,           -- NEW: Subcategorias (Cobranca, Clinico, etc.)
    product_confidence FLOAT,
    
    root_cause VARCHAR,                -- canonical Natureza axis (19 valores v3.2 no estado atual)
    llm_confidence FLOAT,
    
    atendimento_type VARCHAR,          -- compatibility mirror of canonical `service_type`
    
    -- LLM semantic extraction (Phase 3)
    sentiment FLOAT,                   -- NEW: 1-5 scale
    key_themes VARCHAR[],              -- NEW: Array of themes
    conversation_summary VARCHAR,      -- NEW: 150 chars summary
    
    -- Core fields (unchanged)
    ticket_created_at TIMESTAMP,
    ticket_updated_at TIMESTAMP,
    clinic_id BIGINT,
    assignee_name VARCHAR,
    is_claudinha_assigned BOOLEAN,
    via_channel VARCHAR,               -- Metadata, not taxonômico
    tags TEXT,
    full_conversation TEXT,
    loaded_at TIMESTAMP
);
```

### Migration DDL

```sql
-- Step 1: Add new columns (preserving legacy for transition)
ALTER TABLE ticket_insights
    ADD COLUMN product_area_l1 VARCHAR,
    ADD COLUMN product_area_l2 VARCHAR,
    ADD COLUMN product_confidence FLOAT,
    ADD COLUMN root_cause VARCHAR,
    ADD COLUMN llm_confidence FLOAT,
    ADD COLUMN atendimento_type VARCHAR,
    ADD COLUMN sentiment FLOAT,
    ADD COLUMN key_themes VARCHAR[],
    ADD COLUMN conversation_summary VARCHAR;

-- Step 2: Backfill new columns (via reprocessing script)
-- See: scripts/phase3_reprocess_with_new_taxonomy.py

-- Step 3: Validate coverage
SELECT 
    COUNT(*) as total,
    COUNT(product_area_l1) as l1_filled,
    COUNT(root_cause) as nature_filled,
    COUNT(atendimento_type) as atend_filled,
    ROUND(100.0 * COUNT(product_area_l1) / COUNT(*), 1) as l1_pct,
    ROUND(100.0 * COUNT(root_cause) / COUNT(*), 1) as nature_pct,
    ROUND(100.0 * COUNT(atendimento_type) / COUNT(*), 1) as atend_pct
FROM ticket_insights;

-- Target: l1_pct >= 88%, nature_pct >= 82%, atend_pct = 100%

-- Step 4: Drop legacy columns (AFTER validation)
ALTER TABLE ticket_insights
    DROP COLUMN product_area,
    DROP COLUMN product_area_confidence,
    DROP COLUMN workflow_type,
    DROP COLUMN workflow_confidence;
```

---

## 🔀 Value Mapping

### Produto (L1) — Approximate Mapping

**⚠️ Not 1:1 mapping**: New taxonomy has different logic.

| Legacy `product_area` | New `product_area_l1` | Notes |
|:---|:---|:---|
| `BNPL_Cobranca` | `BNPL` (L2: `Cobranca`) | Direct mapping |
| `BNPL_Suporte` | `BNPL` (L2: `Servicing` or `Originacao`) | Depends on context |
| `BNPL_Financiamento` | `BNPL` (L2: `Originacao`) | Direct mapping |
| `SaaS_Operacional` | `SaaS` (L2: `Clinico` or `Conta` or `Lifecycle`) | Depends on tags |
| `SaaS_Billing` | `SaaS` (L2: `Conta`) | Direct mapping |
| `Venda` | `Onboarding` | **Renamed** (Venda → Onboarding) |
| `POS` | `POS` | Direct mapping |
| `Indeterminado` | `Indeterminado` | Direct mapping |

**Recommendation**: **Reprocess all tickets** with new classifier (don't rely on mapping).

---

### Natureza — NO Direct Mapping

**Legacy `workflow_type` values** (Stage 2):
- `Suporte_L2`, `Info_L1`, `Transbordo`, `Reclamacao_L1/L2`, `Solicitacao_L1/L2`, `Indeterminado` (67.4%)

**Current canonical `root_cause` values** (19 semantic categories in v3.2 processed universe):
- `Simulacao_Credito`, `Contratacao_Acompanhamento`, `Contratacao_Suporte_Paciente`, `Endosso_Repasse`, `Cobranca_Ativa`
- `Credenciamento`, `Migracao`, `Process_Generico`
- `Subscription_Pagamento`, `Subscription_Cancelamento`
- `Financial_Inquiry`, `Forma_Pagamento`, `Negativacao`
- `Operational_Question`, `Technical_Issue`, `Acesso`
- `Carne_Capim`, `Alteracao_Cadastral`, `Unclear`

**⚠️ CRITICAL**: **NO 1:1 mapping exists**. Legacy workflow_type (intent-based) ≠ new root_cause (semantic).

**Example**:
- Legacy: `workflow_type = 'Suporte_L2'`
- New: `root_cause = 'Technical_Issue'` (if bug) OR `'Operational_Question'` (if usage doubt) OR `'Migracao'` (if migration issue)

**Recommendation**: **LLM reprocessing required** for all tickets.

---

### Atendimento — NEW Dimension

**Legacy approach**: Used `is_claudinha_assigned` directly in queries.

**Current approach**: dedicated handling axis with 4 values (`service_type` canonically, `atendimento_type` as compatibility mirror):
- `Bot_Resolvido` (bot resolved without escalation)
- `Bot_Escalado` (bot started, escalated to human)
- `Escalacao_Solicitada` (customer explicitly requested human)
- `Humano_Direto` (direct to human, no bot involvement)

**Mapping logic**:

```sql
-- Simplified mapping (actual logic more complex, see TAXONOMY_3_AXES.md § Eixo 3)
CASE
    WHEN is_claudinha_assigned = TRUE 
     AND tags NOT LIKE '%transbordo%' 
     AND full_conversation NOT LIKE '%vou te transferir%'
        THEN 'Bot_Resolvido'
    
    WHEN is_claudinha_assigned = TRUE 
     AND (tags LIKE '%transbordo%' OR full_conversation LIKE '%vou te transferir%')
        THEN 'Bot_Escalado'
    
    WHEN full_conversation LIKE '%quero falar com atendente%'
        THEN 'Escalacao_Solicitada'
    
    ELSE 'Humano_Direto'
END as atendimento_type
```

**Recommendation**: Use deterministic classifier + text signals (not just `is_claudinha_assigned`).

---

## 📊 Query Migration Examples

### Example 1: Product Area Distribution

**Legacy query**:
```sql
SELECT 
    product_area,
    COUNT(*) as cnt,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 1) as pct
FROM ticket_insights
WHERE ticket_created_at >= CURRENT_DATE - 90
GROUP BY 1
ORDER BY 2 DESC;
```

**New query** (v2.1):
```sql
SELECT 
    product_area,
    product_area_l2,
    COUNT(*) as cnt,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 1) as pct
FROM ticket_insights
WHERE ticket_created_at >= CURRENT_DATE - 90
GROUP BY 1, 2
ORDER BY 3 DESC;
```

---

### Example 2: Workflow Type → Root Cause

**Legacy query**:
```sql
SELECT 
    workflow_type,
    AVG(product_area_confidence) as avg_conf
FROM ticket_insights
GROUP BY 1;
```

**New query** (v2.1):
```sql
SELECT 
    root_cause,
    AVG(llm_confidence) as avg_conf,
    AVG(sentiment) as avg_sent
FROM ticket_insights
GROUP BY 1
ORDER BY 2 DESC;
```

---

### Example 3: Bot vs Human

**Legacy query**:
```sql
SELECT 
    CASE 
        WHEN is_claudinha_assigned THEN 'Bot'
        ELSE 'Human'
    END as handler,
    COUNT(*)
FROM ticket_insights
GROUP BY 1;
```

**New query** (v2.1):
```sql
SELECT 
    service_type,
    COUNT(*) as cnt,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 1) as pct
FROM ticket_insights
GROUP BY 1
ORDER BY 2 DESC;
```

**Insight**: New query distinguishes 4 types of handling (not just bot vs human).

---

### Example 4: Cross-Dimensional Analysis

**New capability** (not possible with legacy):

```sql
-- "Show me credenciamento tickets that the bot escalated"
SELECT 
    COUNT(*) as cnt,
    AVG(sentiment) as avg_sent
FROM ticket_insights
WHERE root_cause = 'Credenciamento'
  AND service_type = 'Bot_Escalado'
  AND ticket_created_at >= CURRENT_DATE - 90;
```

**Interpretation**: How well does the bot handle onboarding issues?

---

## 🛠️ Skills Migration

### Skill: `@analyze-voc-sentiment`

**Changes needed**:

1. **Update queries**: Replace `workflow_type` with `root_cause`
2. **Add segmentation**: Use `product_area` + `product_area_l2` for drill-downs
3. **Use service_type**: Instead of `is_claudinha_assigned` directly

**Example diff**:

```diff
# OLD (legacy)
- SELECT workflow_type, AVG(sentiment_score) FROM tickets GROUP BY 1

# NEW (v2.1)
+ SELECT root_cause, AVG(sentiment) FROM tickets GROUP BY 1
```

---

### Skill: `@correlate-tickets-events`

**Changes needed**:

1. **Segment by root_cause**: Instead of workflow_type
2. **Use product_area** for cross-domain correlation
3. **Add service_type** as potential correlation signal

**Example**:

```sql
-- Correlate BNPL tickets with credit rejections
SELECT 
    t.root_cause,
    COUNT(*) as ticket_count,
    COUNT(cs.simulation_id) as rejection_count
FROM ticket_insights t
LEFT JOIN credit_simulations cs
    ON t.clinic_id = cs.clinic_id
    AND cs.created_at BETWEEN t.ticket_created_at - INTERVAL '7 days' 
                           AND t.ticket_created_at + INTERVAL '1 day'
    AND cs.rejection_reason IS NOT NULL
WHERE t.product_area = 'BNPL'
  AND t.ticket_created_at >= CURRENT_DATE - 90
GROUP BY 1
ORDER BY 2 DESC;
```

---

## 📝 Dashboards / Reports Migration

### Streamlit App (client-voice)

**Components to update**:

1. **Filters**:
   - Replace `workflow_type` dropdown → `root_cause` (19 valores v3.2)
   - Use `product_area` + `product_area_l2` as primary product filters
   - Add `service_type` filter (4 valores)
   - Add `via_channel` filter (metadata, optional)

2. **Charts**:
   - Distribution by `product_area` (pie chart)
   - Drill-down by `product_area_l2` (bar chart)
   - Trend by `root_cause` (time series)
   - Bot vs Human efficiency (`service_type` × `sentiment`)

3. **Metrics**:
   - Coverage: % tickets com `product_area != 'Indeterminado'` no universo processado
   - Clarity: % tickets with `root_cause != 'Unclear'` (target: >82%)
   - Bot efficiency: `Bot_Resolvido / (Bot_Resolvido + Bot_Escalado)` (target: >50%)

---

## ⚠️ Breaking Changes Checklist

**Before deploying**:

- [ ] **Backup current table**: `CREATE TABLE ticket_insights_backup AS SELECT * FROM ticket_insights`
- [ ] **Add new columns** (DDL above)
- [ ] **Reprocess tickets** with new taxonomy (Phase 3 script)
- [ ] **Validate coverage** (target: 88% L1, 82% Nature, 100% Atendimento)
- [ ] **Update skills** (@analyze-voc-sentiment, @correlate-tickets-events)
- [ ] **Update dashboards** (Streamlit app filters + charts)
- [ ] **Update documentation** (README, semantic docs)
- [ ] **Drop legacy columns** (AFTER validation)

---

## 🚀 Rollout Plan

### Phase 1: Schema + Reprocessing (Sprint 1-2)

1. Add new columns to `ticket_insights` (non-breaking)
2. Run Phase 3 reprocessing (24.6K tickets, 3 months)
3. Validate coverage + quality
4. Backfill historical (430K tickets)

### Phase 2: Skills + Dashboards (Sprint 3)

5. Update `@analyze-voc-sentiment` skill
6. Update `@correlate-tickets-events` skill
7. Update Streamlit app (filters, charts, metrics)
8. User acceptance testing

### Phase 3: Deprecation (Sprint 4)

9. Mark legacy columns as deprecated (add comment in DDL)
10. Monitor usage (log queries using legacy columns)
11. Communicate sunset date (30 days notice)
12. Drop legacy columns

---

## 📚 References

- **New Taxonomy Spec**: `TAXONOMY_3_AXES.md` (v2.1, 2026-02-12)
- **Decisions Log**: `capim-meta-ontology/_memory/DECISIONS_IN_PROGRESS.md` (19.11-19.18)
- **Empirical Validation Scripts**: `scripts/analysis/taxonomy_redesign_2026_02/`
- **Legacy Taxonomy** (archived): `_docs/archive/PRODUCT_TAXONOMY_DEPRECATED_2026_02_12.md`
- **Legacy Category** (deprecated): `.cursor/skills/analyze-voc-sentiment/references/CATEGORY_TAXONOMY.md`

---

## ❓ FAQ

### Q: Can I use the legacy columns during transition?

**A**: Yes, new columns will coexist with legacy columns until migration is complete. Queries using legacy columns will continue to work, but will be marked as deprecated.

### Q: How long will the transition take?

**A**: Estimated 3-4 sprints:
- Sprint 1-2: Schema + reprocessing
- Sprint 3: Skills + dashboards
- Sprint 4: Deprecation + cleanup

### Q: Will old queries break?

**A**: Not immediately. Legacy columns will be preserved during transition. However, after Sprint 4 (deprecation), queries using legacy columns will fail.

### Q: What if coverage is low after reprocessing?

**A**: Target coverage: 88% L1, 82% Nature. If below target:
1. Investigate `Indeterminado` / `Unclear` tickets (sample 50)
2. Refine deterministic rules (Stage 1)
3. Adjust LLM prompt (Prompt Compiler L3/L4)
4. Reprocess failed subset

### Q: Can I opt out of the migration?

**A**: No. Legacy taxonomy is deprecated and will be removed after transition period. All downstream consumers must migrate.

---

## 📞 Support

**Questions?** Contact: Data team or `@client-voice-data` skill

**Issues?** File in: `capim-meta-ontology/_memory/DECISIONS_IN_PROGRESS.md` (decision tracking)
