# Correlation Patterns — Tickets × Business Events

> **Purpose**: Padrões conhecidos de correlação ticket ↔ evento  
> **Domain**: CLIENT_VOICE + cross-domain  
> **Based on**: Análise histórica (2024-2025)

---

## Padrões Confirmados

### Pattern 1: Rejection Spike → Complaint Spike

**Correlação**: r ≈ 0.4-0.5 (moderada positiva)

**Mecanismo**:
- Clínica tem paciente rejeitado
- Clínica ou paciente abre ticket de reclamação
- Time window: 0-7 dias

**Lift típico**: 2.0-2.5x

**Categoria de ticket**: Reclamação > Dúvida

---

### Pattern 2: System Incident → Bug Tickets

**Correlação**: Forte no curto prazo

**Mecanismo**:
- Incident de sistema (auth, payment, etc)
- Usuários reportam problema
- Time window: 0-3 dias (pico em day 1)

**Lift típico**: 3-5x no dia do incident

**Categoria de ticket**: Problema/Bug

**Detecção**: Spike anômalo em categoria específica

---

### Pattern 3: Subscription Cancellation → Sentiment Drop

**Correlação**: Leading indicator (tickets precedem cancellation)

**Mecanismo**:
- Clínica insatisfeita abre tickets
- Sentimento cai progressivamente
- Eventualmente cancela assinatura

**Time window**: Tickets 30-60 dias ANTES de cancellation

**Uso**: Early warning system para churn

---

### Pattern 4: Onboarding Issues → Dúvida Spike

**Correlação**: Forte para clínicas novas

**Mecanismo**:
- Clínica recém-onboarded
- Muitas dúvidas de uso
- Pico de tickets nas primeiras 4 semanas

**Categoria de ticket**: Dúvida > Solicitação

**Baseline**: Clínicas novas têm 3x mais tickets que estabelecidas

---

## Thresholds de Significância

### Correlation Coefficient (r)

| r Value | Interpretation | Action |
|---------|----------------|--------|
| |r| < 0.1 | Negligible | Ignore |
| 0.1 ≤ |r| < 0.3 | Weak | Investigate further |
| 0.3 ≤ |r| < 0.5 | Moderate | Likely real pattern |
| |r| ≥ 0.5 | Strong | Definite pattern |

### P-Value

- **p < 0.05**: Statistically significant
- **p < 0.01**: Highly significant
- **p ≥ 0.05**: Not significant (may be noise)

### Lift

| Lift | Interpretation |
|------|----------------|
| < 1.2 | No practical effect |
| 1.2 - 1.5 | Small effect |
| 1.5 - 2.0 | Moderate effect |
| > 2.0 | Large effect |

---

## Confounders a Controlar

### 1. Clinic Size

**Problema**: Clínicas maiores têm mais eventos E mais tickets

**Solução**: Normalizar por volume (tickets per budget, não tickets absolutos)

### 2. Sazonalidade

**Problema**: Janeiro tem menos atividade (férias)

**Solução**: Comparar com mesmo período do ano anterior, ou usar controle sazonal

### 3. Persona Mix

**Problema**: Clínicas com mais B2C têm sentimento diferente

**Solução**: Analisar B2B e B2C separadamente

### 4. Category Concentration

**Problema**: Uma clínica com 100 tickets de "bug" distorce média

**Solução**: Usar mediana ou winsorize outliers

---

## Exemplos de Análises Anteriores

### Análise Q4 2024: Rejeição × Tickets

**Período**: 2024-10-01 a 2024-12-31

**Resultado**:
- Correlação: r = 0.42 (p < 0.001)
- Lift: 2.3x para clínicas com rejection_rate > 30%
- Categoria mais afetada: Reclamação (lift 3.1x)

**Ação tomada**: FAQ de rejeição adicionado ao Zendesk

---

### Análise Nov 2024: Incident Auth

**Data do incident**: 2024-11-15

**Resultado**:
- Spike de 400% em tickets "Problema/Bug" no day 1
- Decay para baseline em 4 dias
- Sentimento médio caiu de 3.2 para 2.1 no período

**Ação tomada**: Post-mortem e comunicação proativa

---

## Query Templates

### Template 1: Correlation por Clínica

```sql
WITH clinic_metrics AS (
    SELECT 
        clinic_id,
        rejection_rate,
        negative_ticket_rate
    FROM combined_view
    WHERE clinic_id IS NOT NULL
)
SELECT 
    CORR(rejection_rate, negative_ticket_rate) AS correlation,
    COUNT(*) AS n_clinics
FROM clinic_metrics;
```

### Template 2: Event Study

```sql
WITH event_window AS (
    SELECT 
        clinic_id,
        DATEDIFF('day', event_date, ticket_date) AS days_after,
        COUNT(*) AS tickets
    FROM events_tickets_joined
    WHERE days_after BETWEEN -7 AND 14
    GROUP BY 1, 2
)
SELECT 
    days_after,
    AVG(tickets) AS avg_tickets
FROM event_window
GROUP BY 1
ORDER BY 1;
```

---

## Referências

- **Statistical methods**: Pearson correlation, lift analysis
- **Data sources**: TICKET_ANALYSIS_V3, C1_ENRICHED_BORROWER, CLINIC_ACTIVITY
- **Visualization**: docs/VISUALIZATION_STANDARDS.md
