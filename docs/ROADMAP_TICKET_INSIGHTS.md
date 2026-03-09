# Roadmap: Ticket Insights Backfill & Enrichment

> **Status**: histórico / parcialmente superseded  
> **Last Updated**: 2026-03-09  
> **Decision**: DECISIONS_IN_PROGRESS.md § 19

## Current State Note

This roadmap preserves the original execution framing, but it is **not** the current canonical contract.

Current canonical state:
- `vox_popular.ticket_insights` is the active operational table
- the processed universe follows the 3-axis taxonomy with `product_area`, `product_area_l2`, `root_cause`, and `service_type`
- `processing_phase IS NOT NULL` is the preferred filter for the canonical processed population
- `workflow_type` and similar Stage 1/2 views should now be treated as legacy compatibility context

For the current contract, use:
- `_domain/START_HERE.md`
- `_domain/_docs/TAXONOMY_3_AXES.md`
- `_domain/_docs/reference/TICKET_INSIGHTS_SEMANTIC.md`
- `docs/reference/TICKET_INSIGHTS.md`
- `docs/AUDIT_VOX_POPULAR_2026-03-09.md`

---

## 🎯 OBJETIVO GERAL

Materializar insights dos tickets Zendesk no `vox_popular` usando uma trajetória incremental.

Leitura histórica deste roadmap:
1. ✅ fase inicial de backfill e classificação legacy
2. ✅ evolução para extração semântica e taxonomia de 3 eixos
3. ⏳ futuros enriquecimentos cross-domain e operacionalização adicional

---

## ✅ DECISÕES CONFIRMADAS

### 1. vox_popular como Single Source of Truth ✅
- `TICKET_ANALYSIS_V3` (Snowflake) é **LEGACY**
- Todas as análises vão para vox_popular (PostgreSQL RDS)
- **Rationale**: Hot/Cold architecture, agent reasoning, consolidação ontology + tickets

### 2. ZENDESK_TICKETS_ENHANCED_V1 como Fonte + Filtro Temporal ✅
- Melhor coverage de clinic_id (50.3% vs 46% em RAW)
- Flags úteis: `IS_CLAUDINHA_ASSIGNED`, `VIA_CHANNEL`, `CLINIC_ID_SOURCE`
- **Filtro**: Últimos 12 meses (tags estruturadas disponíveis)
- **Result**: 171.916 tickets com 67% Product Area coverage

### 3. Abordagem Incremental (histórico) ✅
- **Phase 1**: ✅ backfill MVP inicial
- **Phase 2**: ✅ extração semântica e expansão de colunas LLM
- **Phase 3**: ⏳ futuros enriquecimentos cross-domain e operacionalização adicional

---

## 🚧 DECISÕES PENDENTES (Não bloqueiam MVP)

### 4. Arquitetura de Agentes Especializados ⏳

**Proposta em debate**:
- `@agent-saas-specialist` (SaaS Operacional) - analisa contexto SAAS
- `@agent-pos-specialist` (Maquininha) - **NOVO, crítico** (produto estratégico)
- `@agent-bnpl-credit-specialist` (BNPL Financiamento) - analisa contexto FINTECH
- `@agent-bnpl-support-specialist` (BNPL Suporte - boleto, NF) - especialista técnico
- `@agent-onboarding-specialist` (Venda) - **talvez?** (se tivermos dados de funil)

**Questão em aberto**: 
- ❌ ~~CLIENT_VOICE pattern agent~~ → redundante, substituir por queries SQL?

**Prompt engineering** de cada agente: A DEFINIR (debate futuro)

---

## 📊 IMPLEMENTAÇÃO ATUAL (Phase 1 - MVP)

### ✅ Arquivos Criados

```
client-voice-data/
├── scripts/
│   ├── migrations/
│   │   ├── 002_create_ticket_insights_mvp.sql         ✅ Initial schema
│   │   ├── 003_fix_clinic_id_bigint.sql               ✅ BIGINT fix
│   │   └── 004_add_full_conversation.sql              ✅ Add conversation field
│   ├── apply_vox_popular_migration.py                 ✅ Migration runner
│   ├── test_dual_connection.py                        ✅ Connectivity test
│   ├── backfill_tickets_mvp.py                        ✅ Main backfill (171K tickets loaded)
│   └── classify_integrated_stage1_stage2.py           ✅ Classifier (existing)
├── ARCHITECTURE_DECISION_VOX_POPULAR.md               ✅ Architecture doc
└── ROADMAP_TICKET_INSIGHTS.md                         ✅ This file
```

### ✅ Schema inicial do MVP

**Core Fields**:
- Ticket metadata: id (BIGINT PK), created_at, status, subject, tags
- Clinic context: clinic_id (**BIGINT** - fixed!), clinic_id_source
- Assignee: assignee_name, is_claudinha_assigned
- Channel: via_channel (whatsapp, api, web, email)
- **Stage 1**: `product_area`, confidence, keywords
- **Stage 2**: `workflow_type`, confidence, keywords

**9 indexes** para performance (temporal, categorical, composite)

---

## 🚀 PRÓXIMOS PASSOS (CONCRETOS)

### **✅ COMPLETE: Phase 1 MVP** - Executed 2026-02-10

#### ✅ Passo 1: Criar tabela no vox_popular

```bash
# Migrations aplicadas:
python scripts/apply_vox_popular_migration.py --migration 002_create_ticket_insights_mvp.sql
python scripts/apply_vox_popular_migration.py --migration 003_fix_clinic_id_bigint.sql
python scripts/apply_vox_popular_migration.py --migration 004_add_full_conversation.sql
```

**Resultado**: 20 colunas, 13 índices (incluindo GIN para full-text search)

---

#### ✅ Passo 2: Testar conectividade dual

```bash
python scripts/test_dual_connection.py
```

**Resultado**:
```
[OK] Snowflake: 81,380 tickets (últimos 12 meses)
[OK] PostgreSQL: ticket_insights table ready
[OK] Classifier: loaded (Stage 1+2)
```

---

#### ✅ Passo 3: Teste de backfill (1K tickets)

```bash
python scripts/backfill_tickets_mvp.py --test --max-batches 1
```

**Resultado**:
- 1,000 tickets em 14.7s
- Product Area: 69.1% classified
- Workflow Type: 30.4% classified

---

#### ✅ Passo 4: Backfill completo - EXECUTADO

```bash
python scripts/backfill_tickets_mvp.py
```

**Resultado**:
- **171,916 tickets** processados
- **Runtime**: 6.4 minutos (385s)
- **Performance**: 446 tickets/segundo
- **Period**: 2025-02-09 to 2026-02-10 (últimos 12 meses)

---

#### ✅ Passo 5: Validação final do MVP histórico

**Métricas alcançadas**:
```sql
Total tickets: 171,916
Product Area coverage: 67.4%
Workflow Type coverage: 32.6% -- métrica legacy
Clinic ID coverage: 35.6%

-- Coverage
SELECT 
    ROUND(COUNT(CASE WHEN product_area != 'Indeterminado' THEN 1 END)::NUMERIC / COUNT(*) * 100, 1) as product_coverage,
    ROUND(COUNT(CASE WHEN workflow_type != 'Indeterminado' THEN 1 END)::NUMERIC / COUNT(*) * 100, 1) as workflow_coverage
FROM ticket_insights;
-- Esperado: Product ~68%, Workflow ~36% no MVP legacy

-- Distribuição (validar contra CLASSIFIER_FINAL_REPORT)
SELECT product_area, COUNT(*), ROUND(COUNT(*)::NUMERIC / 430815 * 100, 1) as pct
FROM ticket_insights
GROUP BY product_area
ORDER BY COUNT(*) DESC;
```

---

### **Depois: LLM semantic extraction** (histórico)

**Não fazer agora**. Esperar Phase 1 MVP completo.

1. Alterar schema (adicionar colunas LLM)
2. Criar script `enrich_with_llm.py`
3. Processar 430K tickets em batch (OpenAI/Anthropic API)
4. Custo estimado: $100-300 (dependendo do modelo)

---

### **Depois: Agent enrichment** (histórico)

**Não fazer agora**. Esperar Phase 2 completo.

**ANTES de implementar, debater**:
1. ✅ Lista final de agentes especializados (SAAS, POS, FINTECH, BNPL Support, Venda?)
2. ⏳ Prompt engineering de cada agente (context, queries, output)
3. ⏳ Critérios de seleção (quais tickets enriquecer? 150K de 430K?)
4. ⏳ Schema de `ticket_insights_enriched` (JSONB? Colunas estruturadas?)

---

## 📋 CHECKLIST MVP (Phase 1) - ✅ COMPLETE

- [x] 1. Aplicar migrations (002, 003, 004)
- [x] 2. Testar conectividade dual (Snowflake + PostgreSQL)
- [x] 3. Backfill teste (1K tickets)
- [x] 4. Validar teste (distribuição correta)
- [x] 5. Backfill completo (171.916 tickets dos últimos 12 meses)
- [x] 6. Validação final (67.4% Product coverage, 32.6% Workflow)
- [x] 7. Documentar decisões (DECISIONS_IN_PROGRESS.md § 19)

---

## 🎓 LESSONS LEARNED (Phase 1)

### ✅ What Worked
1. **Recent tickets strategy**: 67% classification vs 2% em antigos
2. **BIGINT for clinic_id**: Fixed overflow elegantly
3. **Python aggregation**: Bypassed Snowflake CTE issues
4. **Batch processing**: 446 tickets/s stable performance

### ⚠️ Issues & Workarounds
1. **Comments SQL error**: Agregação falhou, mas backfill continuou
   - Impact: `full_conversation` tem menos contexto que esperado
2. **Low clinic coverage (35.6%)**: Tickets recentes sem org_id
3. **Unicode terminal**: Removed emojis for Windows compatibility

---

## 🎯 Historical Next Step

**Goal**: Extract root_cause, sentiment, themes from `full_conversation`

**Status at the time**: ready to start

**Estimated Effort**: 
- Schema migration: 15 min
- LLM pipeline: 2-3 hours
- Processing: 4-6 hours (100 tickets/batch)
- Cost: ~$50-100 (Claude Sonnet 4)

---