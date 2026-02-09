# Voice of Customer Metrics — Definitions & Methodology

> **Purpose**: Standard definitions for VoC metrics in CLIENT_VOICE domain  
> **Last Updated**: 2026-02-04

---

## Core Metrics

### 1. Average Sentiment Score

**Definition**: Mean of all sentiment scores in period/segment

**Formula**:
```
Avg Sentiment = SUM(sentimento_score) / COUNT(tickets)
```

**Scale**: 1.0 to 5.0 (decimal)

**Interpretation**:
- **4.0-5.0**: Excellent (mostly positive feedback)
- **3.5-3.9**: Good (more positive than negative)
- **3.0-3.4**: Neutral (mixed feedback)
- **2.5-2.9**: Poor (more negative than positive)
- **1.0-2.4**: Critical (mostly negative, needs urgent action)

**Caveats**:
- Sensitive to outliers (use with standard deviation)
- Baseline varies by persona (B2B higher than B2C)

---

### 2. Net Sentiment Score (NSS)

**Definition**: Adapted from NPS (Net Promoter Score), percentage-based

**Formula**:
```
NSS = (% Promoters) - (% Detractors)
```

**Classification**:
- **Promoters**: sentimento_score >= 4 (satisfied customers)
- **Passives**: sentimento_score = 3 (neutral)
- **Detractors**: sentimento_score <= 2 (unsatisfied customers)

**SQL**:
```sql
SELECT 
    COUNT(CASE WHEN sentimento_score >= 4 THEN 1 END) * 100.0 / COUNT(*) as promoter_pct,
    COUNT(CASE WHEN sentimento_score = 3 THEN 1 END) * 100.0 / COUNT(*) as passive_pct,
    COUNT(CASE WHEN sentimento_score <= 2 THEN 1 END) * 100.0 / COUNT(*) as detractor_pct,
    (COUNT(CASE WHEN sentimento_score >= 4 THEN 1 END) - COUNT(CASE WHEN sentimento_score <= 2 THEN 1 END)) * 100.0 / COUNT(*) as nss
FROM tickets;
```

**Scale**: -100 to +100

**Interpretation**:
- **+50 to +100**: Excellent (world-class)
- **+10 to +49**: Good (healthy)
- **-10 to +9**: Neutral (needs improvement)
- **-50 to -11**: Poor (critical issues)
- **-100 to -51**: Crisis (major problems)

**Benchmark**:
- B2B SaaS average: +30 to +40
- Capim B2B (2024): +15 (below average, room for improvement)

---

### 3. Sentiment Distribution

**Definition**: Breakdown of tickets by sentiment score

**Metric**: % of tickets at each score level (1, 2, 3, 4, 5)

**Expected distribution** (healthy VoC):
```
Score 5: ~10-15% (delight)
Score 4: ~30-40% (satisfaction)
Score 3: ~30-40% (neutral)
Score 2: ~10-15% (minor issues)
Score 1: ~5-10% (major issues)
```

**Red flag distributions**:
- **Bimodal** (peaks at 1 and 5, low 3): Polarized customer base
- **Left-skewed** (peak at 1-2): Crisis mode
- **Flat** (equal across all scores): LLM classification issue?

---

### 4. Category Sentiment Index

**Definition**: Average sentiment per category

**Use**: Identify pain points (categories with persistently low sentiment)

**SQL**:
```sql
SELECT 
    categoria,
    COUNT(*) as ticket_count,
    AVG(sentimento_score) as avg_sentiment,
    STDDEV(sentimento_score) as sentiment_stddev,
    COUNT(CASE WHEN sentimento_score <= 2 THEN 1 END) * 100.0 / COUNT(*) as negative_pct
FROM tickets
GROUP BY categoria
ORDER BY avg_sentiment ASC;
```

**Action thresholds**:
- If avg_sentiment < 2.5 AND ticket_count > 100 → **Priority fix**
- If negative_pct > 40% → **Investigate root cause**

---

### 5. Clinic Sentiment Rank

**Definition**: Clinics ranked by average sentiment (B2B only)

**Use**: Identify clinics with persistent support issues

**SQL**:
```sql
SELECT 
    clinic_id_enhanced,
    COUNT(*) as ticket_count,
    AVG(sentimento_score) as avg_sentiment,
    COUNT(CASE WHEN sentimento_score <= 2 THEN 1 END) as negative_tickets
FROM tickets
WHERE persona = 'B2B'
  AND created_at >= CURRENT_DATE - 90
GROUP BY clinic_id_enhanced
HAVING COUNT(*) >= 5  -- Min sample size
ORDER BY avg_sentiment ASC;
```

**Segmentation**:
- **Bottom 10%**: Needs immediate intervention
- **Bottom 10-25%**: Monitor closely
- **Middle 50%**: Baseline
- **Top 25%**: Strong relationship (learn from them)

---

## Statistical Tests

### Trend Detection (Linear Regression)

**Test**: Is sentiment improving/declining over time?

**Method**: Linear regression (sentiment ~ time)

**Python**:
```python
from scipy.stats import linregress

# df has 'date' and 'avg_sentiment' columns
slope, intercept, r_value, p_value, std_err = linregress(
    df['date'].astype('int64') / 10**9,  # Convert to numeric
    df['avg_sentiment']
)

if p_value < 0.05:
    if slope > 0:
        trend = "Improving"
    else:
        trend = "Declining"
else:
    trend = "Stable (no significant trend)"

print(f"Trend: {trend}, R²={r_value**2:.3f}, p={p_value:.4f}")
```

**Report**: Always include R², p-value, and slope

---

### Segment Comparison (Chi-Square Test)

**Test**: Are sentiment distributions different across segments?

**Method**: Chi-square test of independence

**Example**: Compare B2B vs B2C sentiment distribution

**Python**:
```python
from scipy.stats import chi2_contingency

# Contingency table: [segment, sentiment_score] counts
contingency_table = pd.crosstab(df['persona'], df['sentimento_score'])

chi2, p_value, dof, expected = chi2_contingency(contingency_table)

if p_value < 0.05:
    print("Statistically significant difference (p < 0.05)")
else:
    print("No significant difference (p >= 0.05)")
```

**Report**: p-value and interpretation

---

### Correlation with External Events

**Test**: Is sentiment correlated with business metrics?

**Method**: Pearson correlation

**Example**: Sentiment vs Clinic Activity

**Python**:
```python
from scipy.stats import pearsonr

# df has 'avg_sentiment' and 'appointment_count' columns
corr, p_value = pearsonr(df['avg_sentiment'], df['appointment_count'])

print(f"Correlation: {corr:.3f}, p={p_value:.4f}")
```

**Interpretation**:
- corr > 0.3 and p < 0.05: Positive correlation (more activity → better sentiment)
- corr < -0.3 and p < 0.05: Negative correlation (more activity → worse sentiment, overload?)

---

## Benchmarks

### Industry Benchmarks (SaaS Support)

| Metric | Industry Average | Top Quartile | Bottom Quartile |
|--------|-----------------|--------------|----------------|
| B2B Avg Sentiment | 3.5-3.8 | 4.0+ | < 3.2 |
| B2C Avg Sentiment | 3.0-3.3 | 3.5+ | < 2.8 |
| Net Sentiment | +20 to +30 | +40+ | < +10 |
| Negative % | 20-25% | < 15% | > 30% |

**Source**: SaaS industry reports (2024-2025)

---

### Capim Baselines (2024)

| Persona | Avg Sentiment | NSS | Positive % | Negative % |
|---------|--------------|-----|------------|------------|
| **B2B** | 3.4 | +15 | 48% | 22% |
| **B2C** | 2.8 | -8 | 35% | 38% |
| **Overall** | 3.1 | +4 | 42% | 30% |

**Gap vs Industry**:
- B2B: Below average (3.4 vs 3.6 industry)
- B2C: Near average (2.8 vs 3.0 industry)

---

## Confidence Intervals

**When to report CIs**:
- Comparing segments with different sample sizes
- Claiming "statistically different" without test
- Small samples (n < 30)

**Calculation** (95% CI for mean sentiment):
```python
from scipy import stats

mean = df['sentimento_score'].mean()
sem = stats.sem(df['sentimento_score'])  # Standard error of mean
ci = stats.t.interval(0.95, len(df)-1, loc=mean, scale=sem)

print(f"Mean: {mean:.2f}, 95% CI: [{ci[0]:.2f}, {ci[1]:.2f}]")
```

**Example**: 
- B2B: 3.4 (95% CI: [3.35, 3.45])
- B2C: 2.8 (95% CI: [2.75, 2.85])
- **Non-overlapping CIs** → statistically different

---

## Caveats & Limitations

**LLM-Generated Scores**:
- Not human-validated (may have classification errors)
- Consistency depends on LLM model and prompt
- Model drift over time possible (if LLM model changes)

**Sample Size**:
- Small samples (n < 30) have high variance
- Use confidence intervals for small segments
- Avoid over-interpreting single-ticket sentiments

**Persona Baseline Difference**:
- B2B and B2C have different baselines (DO NOT compare directly)
- Always segment by persona first

**Temporal Lag**:
- Sentiment reflects PAST interactions (lagging indicator)
- Not predictive of future sentiment (leading indicators needed)

---

## References

- **NPS Methodology**: https://www.netpromoter.com/know/
- **LLM Classification**: n8n workflow (ID: eQEByyVKRHtD4uBa)
- **Entity Semantic Doc**: `_domain/_docs/reference/ZENDESK_TICKETS_ENHANCED_SEMANTIC.md`
