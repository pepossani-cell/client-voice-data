---
name: Analyze VoC Sentiment
description: Analyze Voice of Customer sentiment trends and patterns in CLIENT_VOICE domain. Use when (1) analyzing support ticket sentiment over time, (2) detecting sentiment trends (improving, declining, stable), (3) segmenting sentiment by category, clinic, or persona (B2B vs B2C), (4) correlating sentiment with business events, (5) generating NPS or CSAT reports, (6) user asks "sentiment analysis", "customer satisfaction", "support quality", "NPS trends", or "ticket sentiment". Works with LLM-enhanced Zendesk data.
version: 1.0
auto_invoke: ask_first
---

# Analyze VoC Sentiment Skill

Analisa tendências e padrões de sentimento em dados de Voice of Customer (VoC) do domínio CLIENT_VOICE, com foco em tickets Zendesk LLM-enhanced.

## Quando Usar

Invoque esta skill quando:
- Analisar sentimento de tickets de suporte ao longo do tempo
- Detectar trends (melhorando, piorando, estável)
- Segmentar sentimento por categoria, clínica, ou persona (B2B vs B2C)
- Correlacionar sentimento com eventos de negócio
- Gerar relatórios de NPS ou CSAT
- Investigar qualidade de suporte

**Invocação**: `@analyze-voc-sentiment` ou menção natural

---

## Conceitos Fundamentais

### Sentiment Score

**Definição**: Escala de 1-5 gerada por LLM

**Scale**:
- **5**: Muito positivo (elogio, gratidão)
- **4**: Positivo (satisfeito, problema resolvido)
- **3**: Neutro (informativo, sem emoção clara)
- **2**: Negativo (insatisfeito, reclamação)
- **1**: Muito negativo (raiva, ameaça de churn)

**Source**: `TICKET_ANALYSIS_V3.sentimento_score` (LLM-enhanced via n8n)

---

### Category & Subcategory

**Categories** (LLM-classified):
- **Dúvida/Pergunta**: Questions, clarifications
- **Problema/Bug**: Technical issues, bugs
- **Reclamação**: Complaints (not necessarily technical)
- **Elogio**: Praise, positive feedback
- **Solicitação**: Feature requests, improvements
- **Outro**: Uncategorized

**Subcategories**: Hierarchical (varies by category)

**Source**: `TICKET_ANALYSIS_V3.categoria`, `TICKET_ANALYSIS_V3.subcategoria`

---

### Persona

**B2B**: Clinic staff (admin, doctors, receptionists)  
**B2C**: Patients, debtors (debt collection)

**Distinction**:
- B2B: `clinic_id IS NOT NULL` (~50% of tickets)
- B2C: `clinic_id IS NULL` (~50% of tickets)

**Important**: Do NOT treat NULL clinic_id as error (see "Ghost Phenomenon" in semantic docs)

---

## Processo de Execução

### Passo 1: Definir Escopo da Análise

**Parameters to collect**:

```yaml
analysis_scope:
  period:
    start_date: YYYY-MM-DD
    end_date: YYYY-MM-DD
    granularity: daily | weekly | monthly
  
  persona:
    type: all | B2B | B2C
    
  category:
    filter: all | specific_category | multiple_categories
    
  clinic:
    filter: all | specific_clinic | clinic_segment
  
  aggregation:
    level: overall | by_category | by_clinic | by_persona | by_time
```

**Invoke `@debate`** if scope is ambiguous

---

### Passo 2: Consultar Dados de Sentimento

**Base query**:

```sql
SELECT 
    ticket_id,
    created_at,
    clinic_id,
    clinic_id_enhanced, -- Enhanced linkage (better than raw clinic_id)
    persona,
    categoria,
    subcategoria,
    sentimento_score,
    -- Additional fields for segmentation
FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.TICKET_ANALYSIS_V3
WHERE created_at BETWEEN :start_date AND :end_date
  AND sentimento_score IS NOT NULL  -- Exclude unprocessed
  AND (:persona = 'all' OR persona = :persona)
  AND (:categoria = 'all' OR categoria = :categoria)
```

**Segmentation** (apply filters from Step 1):

```sql
-- Example: B2B only
WHERE persona = 'B2B'

-- Example: Specific category
WHERE categoria = 'Problema/Bug'
```

**Output**: Ticket sentiment dataset

---

### Passo 3: Calcular Métricas de Sentimento

**Aggregate metrics**:

1. **Average Sentiment Score**:
   ```sql
   SELECT 
       AVG(sentimento_score) as avg_sentiment,
       STDDEV(sentimento_score) as sentiment_stddev
   FROM tickets;
   ```

2. **Sentiment Distribution**:
   ```sql
   SELECT 
       sentimento_score,
       COUNT(*) as ticket_count,
       COUNT(*) * 100.0 / SUM(COUNT(*)) OVER() as pct
   FROM tickets
   GROUP BY sentimento_score
   ORDER BY sentimento_score DESC;
   ```

3. **Net Sentiment Score** (NPS-like):
   ```sql
   SELECT 
       COUNT(CASE WHEN sentimento_score >= 4 THEN 1 END) as promoters,
       COUNT(CASE WHEN sentimento_score = 3 THEN 1 END) as passives,
       COUNT(CASE WHEN sentimento_score <= 2 THEN 1 END) as detractors,
       (COUNT(CASE WHEN sentimento_score >= 4 THEN 1 END) - COUNT(CASE WHEN sentimento_score <= 2 THEN 1 END)) * 100.0 / COUNT(*) as net_sentiment
   FROM tickets;
   ```

---

### Passo 4: Detectar Tendências

**Time series analysis**:

```sql
SELECT 
    DATE_TRUNC(:granularity, created_at) as period,
    COUNT(*) as ticket_volume,
    AVG(sentimento_score) as avg_sentiment,
    COUNT(CASE WHEN sentimento_score >= 4 THEN 1 END) * 100.0 / COUNT(*) as positive_pct,
    COUNT(CASE WHEN sentimento_score <= 2 THEN 1 END) * 100.0 / COUNT(*) as negative_pct
FROM tickets
GROUP BY period
ORDER BY period;
```

**Trend classification**:
- **Improving**: Sentiment increasing over time (linear regression slope > 0)
- **Declining**: Sentiment decreasing over time (slope < 0)
- **Stable**: No significant trend (|slope| < threshold)
- **Volatile**: High variance (needs investigation)

**Statistical test**: Linear regression on sentiment over time, report R² and p-value

---

### Passo 5: Análise por Segmento

**By Category**:

```sql
SELECT 
    categoria,
    COUNT(*) as ticket_count,
    AVG(sentimento_score) as avg_sentiment,
    STDDEV(sentimento_score) as sentiment_stddev
FROM tickets
GROUP BY categoria
ORDER BY ticket_count DESC;
```

**Insights**:
- Which categories have lowest sentiment? (pain points)
- Which have highest? (strengths)

**By Persona** (B2B vs B2C):

```sql
SELECT 
    persona,
    COUNT(*) as ticket_count,
    AVG(sentimento_score) as avg_sentiment
FROM tickets
GROUP BY persona;
```

**Expected**: 
- B2B: Typically higher sentiment (partnership mindset)
- B2C: Typically lower sentiment (debt collection stress)

**By Clinic** (for B2B only):

```sql
SELECT 
    clinic_id_enhanced,
    COUNT(*) as ticket_count,
    AVG(sentimento_score) as avg_sentiment
FROM tickets
WHERE persona = 'B2B'
GROUP BY clinic_id_enhanced
HAVING COUNT(*) >= 5  -- Min sample size
ORDER BY avg_sentiment ASC
LIMIT 10;  -- Bottom 10 clinics
```

**Use case**: Identify clinics with persistent support issues

---

### Passo 6: Correlacionar com Eventos

**Cross-domain correlation** (optional, advanced):

**Invoke `@correlate-tickets-events`** (Tier 3 skill, planned) for:
- Correlate sentiment drops with SAAS events (churn signals, activity drops)
- Correlate sentiment drops with FINTECH events (rejection spikes)

**Manual correlation** (if skill not available):

```sql
-- Example: Sentiment vs Clinic Activity
WITH ticket_sentiment AS (
    SELECT 
        clinic_id_enhanced,
        DATE_TRUNC('month', created_at) as month,
        AVG(sentimento_score) as avg_sentiment
    FROM tickets
    WHERE persona = 'B2B'
    GROUP BY clinic_id_enhanced, month
),
clinic_activity AS (
    SELECT 
        clinic_id,
        mes_ativo,
        appointment_count
    FROM SAAS.CLINIC_ACTIVITY_MONTHLY  -- Example SAAS table
)
SELECT 
    t.clinic_id_enhanced,
    t.month,
    t.avg_sentiment,
    c.appointment_count,
    CORR(t.avg_sentiment, c.appointment_count) OVER (PARTITION BY t.clinic_id_enhanced) as correlation
FROM ticket_sentiment t
JOIN clinic_activity c 
    ON t.clinic_id_enhanced = c.clinic_id 
   AND t.month = c.mes_ativo;
```

---

### Passo 7: Gerar Visualizações

**Chart 1: Sentiment Time Series** (line chart):
- X-axis: Period (daily/weekly/monthly)
- Y-axis: Average sentiment score
- Dual Y-axis: Ticket volume (bar chart overlay)
- Annotations: Key events (product launches, incidents)

**Chart 2: Sentiment Distribution** (stacked bar chart):
- X-axis: Period or Segment
- Y-axis: % of tickets
- Stacks: Score 1, 2, 3, 4, 5 (color-coded: red→yellow→green)

**Chart 3: Category Heatmap**:
- Rows: Categories
- Columns: Time periods
- Color: Average sentiment (heatmap)
- Size: Ticket volume (bubble size or annotation)

**Chart 4: Clinic Sentiment Ranking** (horizontal bar chart):
- X-axis: Average sentiment
- Y-axis: Clinics (top 10 best, bottom 10 worst)
- Annotations: Ticket count per clinic

**Reference**: `capim-meta-ontology/docs/VISUALIZATION_STANDARDS.md`

---

### Passo 8: Gerar Relatório

**Report structure**:

```markdown
# Voice of Customer Sentiment Analysis — <Period>

**Period**: YYYY-MM-DD to YYYY-MM-DD  
**Persona**: All | B2B | B2C  
**Generated**: <Timestamp>

---

## Executive Summary

- **Total Tickets**: N
- **Average Sentiment**: X.X / 5.0
- **Net Sentiment**: +X.X% (promoters - detractors)
- **Trend**: Improving | Declining | Stable (R²=X.XX, p<0.05)

---

## Sentiment Distribution

| Score | Count | % | Label |
|-------|-------|---|-------|
| 5 | N | X.X% | Muito Positivo |
| 4 | N | X.X% | Positivo |
| 3 | N | X.X% | Neutro |
| 2 | N | X.X% | Negativo |
| 1 | N | X.X% | Muito Negativo |

---

## Sentiment by Category

| Categoria | Tickets | Avg Sentiment | Top Issues |
|-----------|---------|---------------|------------|
| Problema/Bug | N | X.X | [Subcategories] |
| Reclamação | N | X.X | [Subcategories] |
| Dúvida | N | X.X | [Subcategories] |

**Insights**: [Categories with lowest sentiment = pain points]

---

## Sentiment by Persona

| Persona | Tickets | Avg Sentiment | Trend |
|---------|---------|---------------|-------|
| B2B | N | X.X | Improving |
| B2C | N | X.X | Stable |

---

## Visualizations

[Embed charts from Step 7]

---

## Key Findings

1. **[Finding 1]**: [Insight with data support]
2. **[Finding 2]**: [Insight with data support]
3. **[Finding 3]**: [Insight with data support]

---

## Recommendations

- [Action 1 to improve sentiment]
- [Action 2]

---

## Caveats

- **LLM classification**: Sentiment scores are LLM-generated, not human-validated
- **B2C bias**: Debt collection tickets skew negative (expected)
- **Sample size**: [Any segments with low sample size]

---

## Appendix

**Queries**: [Link to reproducible queries]  
**Data source**: `TICKET_ANALYSIS_V3`  
**LLM model**: [If known]
```

---

## Recursos Incluídos

### Scripts

**`scripts/analyze_sentiment.py`** (planned):
```python
# Usage:
# python scripts/analyze_sentiment.py --start 2024-01-01 --end 2024-12-31 --persona B2B

# Functions:
# - query_sentiment_data(start, end, filters) -> DataFrame
# - calculate_sentiment_metrics(df) -> dict
# - detect_sentiment_trend(df) -> TrendResult
# - segment_by_category(df) -> DataFrame
# - segment_by_clinic(df) -> DataFrame
# - generate_visualizations(df, output_dir) -> None
# - export_report(metrics, charts, output_path) -> None
```

### References

**`references/VOC_METRICS.md`**:
- NPS calculation methodology
- CSAT vs sentiment score mapping
- Industry benchmarks
- Statistical significance tests

**`references/CATEGORY_TAXONOMY.md`**:
- Complete category/subcategory tree
- LLM classification logic
- Category definitions and examples
- Known misclassifications

**`references/SENTIMENT_PATTERNS.md`**:
- Typical sentiment by category (baselines)
- Seasonal patterns (if any)
- Correlation with business events
- Red flags and thresholds

---

## Integração com Outras Skills

**Composes**:
- `@debate` (Tier 1) - For ambiguous analysis scope or methodology
- `@correlate-tickets-events` (Tier 3, planned) - For cross-domain correlation

**Uses**:
- `@investigate-entity` (Tier 2) - To profile TICKET_ANALYSIS_V3 or related tables
- `@clinic-health-check` (Tier 2) - Sentiment is one dimension of clinic health

**Feeds**:
- CLIENT_VOICE app (Streamlit dashboard) - Sentiment charts and metrics

---

## Anti-Patterns

❌ **Don't**:
- Treat NULL `clinic_id` as data error (B2C tickets expected to have NULL)
- Compare B2B and B2C sentiment directly (different contexts)
- Ignore sample size (small samples have high variance)
- Use sentiment as sole health indicator (combine with volume, category, resolution time)
- Skip statistical tests when claiming "trend" (eyeballing is not enough)

✅ **Do**:
- Segment by persona FIRST (B2B vs B2C have different baselines)
- Report confidence intervals for aggregates
- Validate trends with statistical tests (linear regression, p-value)
- Document caveats (LLM-generated, not human-validated)
- Use Snowflake for aggregations (not Python)

---

## Exemplos

### Exemplo 1: Tendência Geral de Sentimento

**Scope**: All tickets, monthly aggregation, 2024

**Query**:
```sql
SELECT 
    DATE_TRUNC('month', created_at) as month,
    COUNT(*) as ticket_count,
    AVG(sentimento_score) as avg_sentiment,
    STDDEV(sentimento_score) as sentiment_stddev,
    COUNT(CASE WHEN sentimento_score >= 4 THEN 1 END) * 100.0 / COUNT(*) as positive_pct,
    COUNT(CASE WHEN sentimento_score <= 2 THEN 1 END) * 100.0 / COUNT(*) as negative_pct
FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.TICKET_ANALYSIS_V3
WHERE created_at BETWEEN '2024-01-01' AND '2024-12-31'
  AND sentimento_score IS NOT NULL
GROUP BY month
ORDER BY month;
```

**Output**:
| Month | Tickets | Avg Sentiment | Positive % | Negative % |
|-------|---------|--------------|------------|------------|
| 2024-01 | 3,245 | 3.2 | 42% | 28% |
| 2024-02 | 2,891 | 3.4 | 45% | 25% |
| ... | ... | ... | ... | ... |

**Trend**: Improving (slope=+0.02/month, p<0.01)

---

### Exemplo 2: Sentimento por Categoria

**Scope**: Q4 2024, all personas

**Query**:
```sql
SELECT 
    categoria,
    COUNT(*) as ticket_count,
    AVG(sentimento_score) as avg_sentiment,
    STDDEV(sentimento_score) as sentiment_stddev
FROM TICKET_ANALYSIS_V3
WHERE created_at BETWEEN '2024-10-01' AND '2024-12-31'
GROUP BY categoria
ORDER BY avg_sentiment ASC;  -- Worst categories first
```

**Output**:
| Categoria | Tickets | Avg Sentiment | Interpretation |
|-----------|---------|--------------|----------------|
| Reclamação | 1,234 | 1.8 | 🔴 Pain point |
| Problema/Bug | 2,345 | 2.3 | 🟡 Needs attention |
| Dúvida | 4,567 | 3.1 | 🟢 Neutral |
| Elogio | 234 | 4.8 | 🟢 Strength |

**Insight**: "Reclamação" has consistently low sentiment → prioritize resolution

---

### Exemplo 3: Sentimento por Clínica (B2B)

**Scope**: B2B tickets only, clinics with 5+ tickets

**Query**:
```sql
SELECT 
    clinic_id_enhanced,
    COUNT(*) as ticket_count,
    AVG(sentimento_score) as avg_sentiment,
    COUNT(CASE WHEN sentimento_score <= 2 THEN 1 END) as negative_tickets
FROM TICKET_ANALYSIS_V3
WHERE persona = 'B2B'
  AND created_at >= CURRENT_DATE - 90  -- Last 90 days
GROUP BY clinic_id_enhanced
HAVING COUNT(*) >= 5
ORDER BY avg_sentiment ASC
LIMIT 10;  -- Bottom 10 clinics
```

**Output**: Clinics with persistent low sentiment → candidates for intervention

---

## Benchmarks e Metas

### Benchmarks Internos (Capim)

| Persona | Avg Sentiment | Positive % | Negative % |
|---------|--------------|------------|------------|
| **B2B** (2024) | 3.4 | 48% | 22% |
| **B2C** (2024) | 2.8 | 35% | 38% |

**Note**: B2C lower due to debt collection context (expected)

---

### Metas (2026)

| Metric | 2025 Baseline | 2026 Target | Stretch |
|--------|--------------|-------------|---------|
| B2B Avg Sentiment | 3.4 | 3.6 | 3.8 |
| B2C Avg Sentiment | 2.8 | 3.0 | 3.2 |
| Net Sentiment | +15% | +20% | +25% |
| Negative % (B2B) | 22% | < 18% | < 15% |

---

## Notas Técnicas

- **Data source**: `TICKET_ANALYSIS_V3` (LLM-enhanced via n8n)
- **Update frequency**: Daily (n8n pipeline runs nightly)
- **LLM model**: [Document if known, currently unknown per analysis]
- **Snowflake-first**: All aggregations in Snowflake, Python for viz only
- **Performance**: ~2-5s para queries mensais, ~10-15s para granularidade diária

---

## Referências

- **Entity docs**: `_domain/_docs/reference/ZENDESK_TICKETS_ENHANCED_SEMANTIC.md`
- **ETL**: `scripts/sync_zendesk_enhanced_view.py`
- **Visualization**: `capim-meta-ontology/docs/VISUALIZATION_STANDARDS.md`
- **App integration**: `client-voice/` (Streamlit dashboard consumes these metrics)
