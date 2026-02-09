# Category Taxonomy — LLM Classification

> **Purpose**: Complete category/subcategory tree for support ticket classification  
> **Domain**: CLIENT_VOICE  
> **Source**: LLM-enhanced classification via n8n  
> **Last Updated**: 2026-02-04

---

## Category Hierarchy

### 1. Dúvida/Pergunta

**Definition**: Questions, clarifications, how-to requests

**Typical sentiment**: 3.0-3.5 (neutral to slightly positive)

**Subcategories**:
- **Como usar**: Feature usage questions
- **Informação**: General information requests
- **Configuração**: Setup or settings questions
- **Processo**: Business process clarifications
- **Outro**: Uncategorized questions

**Example tickets**:
- "Como faço para exportar relatórios?"
- "Qual o prazo para aprovação de crédito?"
- "Como adicionar novo usuário no sistema?"

---

### 2. Problema/Bug

**Definition**: Technical issues, bugs, errors, system not working as expected

**Typical sentiment**: 2.0-2.8 (negative to neutral)

**Subcategories**:
- **Sistema lento**: Performance issues
- **Erro/Falha**: Errors, crashes, failures
- **Não funciona**: Feature not working
- **Integração**: Integration issues (API, third-party)
- **Outro**: Uncategorized technical problems

**Example tickets**:
- "Sistema está muito lento hoje"
- "Erro ao tentar finalizar orçamento"
- "Integração com PagSeguro parou de funcionar"

**Correlation**: Often correlates with product releases or infrastructure issues

---

### 3. Reclamação

**Definition**: Complaints (not necessarily technical), dissatisfaction, frustration

**Typical sentiment**: 1.5-2.3 (very negative to negative)

**Subcategories**:
- **Atendimento**: Support quality complaints
- **Processo**: Business process complaints
- **Política**: Policy or rule complaints
- **Cobrança**: Billing or payment complaints (overlap with B2C)
- **Outro**: Uncategorized complaints

**Example tickets**:
- "Já abri 3 tickets sobre o mesmo problema e ninguém resolve"
- "Política de cancelamento é muito rígida"
- "Cobrança duplicada no cartão"

**Action**: High-priority for resolution (churn risk)

---

### 4. Elogio

**Definition**: Praise, positive feedback, gratitude

**Typical sentiment**: 4.5-5.0 (very positive)

**Subcategories**:
- **Atendimento**: Praise for support quality
- **Funcionalidade**: Feature praise
- **Resultados**: Business outcome praise
- **Outro**: General praise

**Example tickets**:
- "Atendimento excelente, resolveu meu problema rapidamente"
- "Adorei a nova funcionalidade de relatórios"
- "Sistema ajudou a aumentar nossa eficiência em 30%"

**Use**: Learn from positive feedback (what's working well?)

---

### 5. Solicitação

**Definition**: Feature requests, improvements, suggestions

**Typical sentiment**: 3.2-3.8 (neutral to slightly positive)

**Subcategories**:
- **Nova funcionalidade**: New feature requests
- **Melhoria**: Improvement suggestions for existing features
- **Integração**: Integration requests (new partners, APIs)
- **Relatório**: Reporting or analytics requests
- **Outro**: Uncategorized requests

**Example tickets**:
- "Gostaria de poder exportar dados em Excel"
- "Seria útil ter integração com WhatsApp"
- "Sugestão: adicionar gráfico de evolução mensal"

**Use**: Product roadmap input (prioritize by volume and sentiment)

---

### 6. Outro

**Definition**: Tickets that don't fit other categories

**Typical sentiment**: 3.0 (neutral)

**Subcategories**: None (catch-all)

**Volume**: Should be < 5% of total tickets

**Red flag**: If > 10% → LLM classification needs tuning

---

## Category Sentiment Baselines

| Categoria | Expected Avg Sentiment | Red Flag Threshold |
|-----------|----------------------|-------------------|
| Dúvida/Pergunta | 3.2-3.5 | < 3.0 |
| Problema/Bug | 2.3-2.8 | < 2.0 |
| Reclamação | 1.8-2.3 | < 1.5 |
| Elogio | 4.5-5.0 | < 4.0 |
| Solicitação | 3.2-3.8 | < 3.0 |
| Outro | 3.0 | < 2.5 |

**Deviation from baseline** → investigate (data issue? category drift? real sentiment change?)

---

## LLM Classification Quality

### Classification Confidence (if available)

**Metric**: LLM-provided confidence score (0.0 to 1.0)

**Thresholds**:
- **High confidence**: > 0.8 (trust classification)
- **Medium confidence**: 0.5-0.8 (acceptable, but monitor)
- **Low confidence**: < 0.5 (manual review recommended)

**Action**: If low-confidence tickets > 10% → retrain LLM or adjust prompt

---

### Known Misclassifications

**Pattern 1: "Dúvida" vs "Problema"**

**Issue**: Customer asks "Por que X não funciona?" → classified as "Dúvida", should be "Problema"

**Heuristic**: If question contains "não funciona", "erro", "falha" → reclassify to "Problema"

---

**Pattern 2: "Solicitação" vs "Reclamação"**

**Issue**: "Gostaria de ter funcionalidade X, pois o atual é péssimo" → ambiguous

**Rule**: If sentiment < 2.5 → treat as "Reclamação", else "Solicitação"

---

**Pattern 3: B2C Debt Collection**

**Issue**: Debt collection tickets often misclassified

**Rule**: If persona = 'B2C' and keywords ['dívida', 'cobrança', 'pagamento'] → special handling

---

## Mapping to Standard Frameworks

### NPS (Net Promoter Score)

**Mapping**:
- NPS Question: "How likely are you to recommend us?" (0-10 scale)
- Sentiment Score: "How satisfied are you?" (1-5 scale)

**Conversion** (approximate):
```
NPS Score ≈ (Sentiment - 3) * 2.5 + 5

Example:
Sentiment 5.0 → NPS ≈ 10 (Promoter)
Sentiment 4.0 → NPS ≈ 7.5 (Promoter)
Sentiment 3.0 → NPS ≈ 5 (Passive)
Sentiment 2.0 → NPS ≈ 2.5 (Detractor)
Sentiment 1.0 → NPS ≈ 0 (Detractor)
```

**Caveat**: Sentiment ≠ NPS (different questions), use with caution

---

### CSAT (Customer Satisfaction Score)

**Mapping**:
- CSAT Question: "How satisfied are you?" (1-5 stars)
- Sentiment Score: 1-5 scale

**Direct mapping**: Sentiment score IS CSAT (same scale)

**CSAT Metric**:
```
CSAT = (Count of scores 4-5) / (Total responses) * 100
```

**SQL**:
```sql
SELECT 
    COUNT(CASE WHEN sentimento_score >= 4 THEN 1 END) * 100.0 / COUNT(*) as csat
FROM tickets;
```

---

## Time-Based Analysis

### Rolling Averages

**Use**: Smooth out daily volatility

**Calculation**: 7-day or 30-day rolling average

**SQL**:
```sql
SELECT 
    created_at::DATE as date,
    AVG(sentimento_score) OVER (
        ORDER BY created_at::DATE 
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) as sentiment_7d_rolling,
    AVG(sentimento_score) OVER (
        ORDER BY created_at::DATE 
        ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
    ) as sentiment_30d_rolling
FROM tickets
ORDER BY date;
```

**Visualization**: Line chart with rolling averages overlaid on daily sentiment

---

### Seasonal Patterns

**Known patterns** (if any):
- January: Peak support volume (New Year, new clinics onboarding)
- July: Mid-year reviews, budget planning
- December: End-of-year rush, holiday slowdown

**Detection**:
```sql
SELECT 
    EXTRACT(MONTH FROM created_at) as month,
    AVG(sentimento_score) as avg_sentiment
FROM tickets
GROUP BY month
ORDER BY month;
```

**Action**: If seasonal pattern detected, adjust for seasonality in trend analysis

---

## Caveats

**LLM Limitations**:
- Sentiment score is subjective (LLM interpretation, not customer self-reported)
- May misinterpret sarcasm or cultural nuances
- Consistency depends on prompt stability

**Data Quality**:
- ~1-2% of tickets may have NULL sentiment (processing failed)
- LLM model may change over time (monitor for drift)

**Reporting**:
- Always state "LLM-generated sentiment, not customer self-reported"
- Include confidence intervals for small samples
- Document LLM model version (if known)

---

**Reference**: Based on `TICKET_ANALYSIS_V3` schema and production observations (2023-2025)
