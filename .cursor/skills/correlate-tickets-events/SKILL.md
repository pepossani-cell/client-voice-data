---
name: Correlate Tickets Events
description: Correlate support tickets with business events across SAAS and FINTECH domains. Use when (1) investigating if ticket spikes relate to product issues, (2) linking clinic tickets to operational or credit events, (3) detecting causal patterns (event → ticket), (4) enriching tickets with business context, (5) user asks "correlate tickets", "why ticket spike", "link support to events", or "root cause analysis". Implements cross-domain event correlation with time windows.
version: 1.0
auto_invoke: ask_first
---

# Correlate Tickets Events Skill

Correlaciona tickets de suporte com eventos de negócio nos domínios SAAS e FINTECH para análise de causa raiz.

## Quando Usar

Invoque esta skill quando:
- Investigar se picos de tickets estão relacionados a problemas no produto
- Linkar tickets de clínica a eventos operacionais ou de crédito
- Detectar padrões causais (evento → ticket)
- Enriquecer tickets com contexto de negócio
- Fazer root cause analysis de problemas recorrentes

**Invocação**: `@correlate-tickets-events` ou menção natural ("correlacionar tickets", "causa do spike")

---

## Conceitos Fundamentais

### Por Quê Correlacionar?

**Tickets não existem no vácuo**:
- Spike de tickets de "problema de login" → possível incident de autenticação
- Tickets de "crédito negado" concentrados em clínica X → possível mudança de score
- Queda de sentimento em B2B → possível problema operacional

**Objetivo**: Transformar tickets de **sintomas** em **diagnósticos**

### Domínios Correlacionáveis

| Domínio | Eventos | Join Key |
|---------|---------|----------|
| **CLIENT_VOICE** | Tickets Zendesk | ticket_id, clinic_id |
| **SAAS** | Activity, Subscriptions, Cancellations | clinic_id |
| **FINTECH** | Simulations, Approvals, Rejections | clinic_id, cpf |

### Tipos de Correlação

1. **Temporal**: Evento precedeu ticket por X dias?
2. **Entity**: Mesmo clinic_id ou patient_id?
3. **Categorical**: Ticket de categoria X correlaciona com evento Y?
4. **Volume**: Spike de tickets correlaciona com spike de rejeições?

---

## Processo de Execução

### Passo 1: Definir Hipótese de Correlação

**Perguntar ao usuário**:
```
Qual correlação você quer investigar?

A. Ticket spike → Event spike (mesma clínica)
B. Rejection spike → Sentiment drop (mesma clínica)
C. System incident → Ticket category spike (global)
D. Churn signal → Ticket sentiment drop (leading indicator)
E. Custom hypothesis (especificar)
```

---

### Passo 2: Selecionar Eventos de Negócio

**SAAS Events** (de ontologia-saas):

```sql
-- Eventos de atividade
SELECT clinic_id, event_date, event_type
FROM SAAS.CLINIC_ACTIVITY
WHERE event_type IN ('budget_created', 'appointment_scheduled', 'login')

-- Eventos de churn
SELECT clinic_id, cancelled_at, cancellation_reason
FROM SAAS.SUBSCRIPTION_CANCELLATIONS
```

**FINTECH Events** (de bnpl-funil):

```sql
-- Eventos de crédito
SELECT clinic_id, created_at, outcome_bucket
FROM C1_ENRICHED_BORROWER
WHERE outcome_bucket IN ('approved', 'rejected')

-- Taxa de rejeição por clínica
SELECT 
    clinic_id,
    DATE_TRUNC('week', created_at) AS week,
    COUNT(CASE WHEN outcome_bucket = 'rejected' THEN 1 END) * 100.0 / COUNT(*) AS rejection_rate
FROM C1_ENRICHED_BORROWER
GROUP BY 1, 2
```

---

### Passo 3: Preparar Tickets

**Base de tickets** (de client-voice-data):

```sql
SELECT 
    ticket_id,
    created_at,
    clinic_id_enhanced AS clinic_id,
    persona,
    categoria,
    subcategoria,
    sentimento_score
FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.TICKET_ANALYSIS_V3
WHERE sentimento_score IS NOT NULL
```

**Agregação por período**:

```sql
SELECT 
    clinic_id,
    DATE_TRUNC('week', created_at) AS week,
    COUNT(*) AS ticket_count,
    AVG(sentimento_score) AS avg_sentiment,
    COUNT(CASE WHEN sentimento_score <= 2 THEN 1 END) AS negative_tickets
FROM tickets
WHERE persona = 'B2B'  -- Foco em clínicas
GROUP BY 1, 2
```

---

### Passo 4: Aplicar Time Windows de Correlação

**Correlação Event → Ticket** (evento precedeu ticket):

```sql
WITH events AS (
    SELECT clinic_id, event_date, event_type
    FROM saas_events
),
tickets_agg AS (
    SELECT clinic_id, week, ticket_count, avg_sentiment
    FROM ticket_aggregates
)

SELECT 
    e.clinic_id,
    e.event_date,
    e.event_type,
    t.week AS ticket_week,
    t.ticket_count,
    t.avg_sentiment,
    DATEDIFF('day', e.event_date, t.week) AS days_after_event
FROM events e
JOIN tickets_agg t
    ON e.clinic_id = t.clinic_id
   AND t.week BETWEEN e.event_date AND DATEADD('day', 14, e.event_date)
```

**Time windows recomendados**:
- Incident → Tickets: 0-3 dias
- Rejection → Complaint: 0-7 dias
- Churn signal → Sentiment drop: 0-30 dias

---

### Passo 5: Calcular Métricas de Correlação

**Correlation coefficient** (Pearson):

```python
from scipy.stats import pearsonr

# Exemplo: rejeições vs tickets negativos
corr, p_value = pearsonr(df['rejection_rate'], df['negative_ticket_rate'])

if p_value < 0.05 and abs(corr) > 0.3:
    print(f"Correlação significativa: r={corr:.3f}, p={p_value:.4f}")
```

**Lift analysis** (evento aumenta probabilidade de ticket?):

```sql
-- Taxa de ticket APÓS evento vs taxa baseline
WITH clinics_with_event AS (
    SELECT DISTINCT clinic_id FROM events WHERE event_type = 'rejection'
),
ticket_rates AS (
    SELECT 
        CASE WHEN cwe.clinic_id IS NOT NULL THEN 'with_event' ELSE 'baseline' END AS group_type,
        AVG(ticket_rate) AS avg_ticket_rate
    FROM clinic_ticket_rates ctr
    LEFT JOIN clinics_with_event cwe ON ctr.clinic_id = cwe.clinic_id
    GROUP BY 1
)
SELECT 
    with_event.avg_ticket_rate / baseline.avg_ticket_rate AS lift
FROM ticket_rates with_event, ticket_rates baseline
WHERE with_event.group_type = 'with_event' AND baseline.group_type = 'baseline';
```

**Lift > 1.5** → Evento aumenta significativamente probabilidade de ticket

---

### Passo 6: Visualizar Correlação

**Chart 1: Event Study** (ticket volume antes/depois de evento):

```
     Tickets
       |    /\
       |   /  \
       |  /    \
       | /      \___
       |/
       +-----|-----|-----
          -7d  Event  +7d
```

**Chart 2: Scatter Plot** (rejeição vs sentimento):

```
Sentiment
    |  o  o
    |    o   o
    |  o    o
    |o   o
    |_________ Rejection Rate
```

**Chart 3: Heatmap** (categoria de ticket vs evento):

```
              | Rejection | Cancellation | Incident |
| Bug         |    0.8    |     0.2      |   0.9    |
| Reclamação  |    0.6    |     0.7      |   0.3    |
| Dúvida      |    0.1    |     0.3      |   0.2    |
```

---

### Passo 7: Gerar Relatório de Correlação

```markdown
# Correlation Report: Tickets × Business Events

**Period**: 2024-10-01 to 2024-12-31  
**Hypothesis**: Credit rejections drive support ticket volume

---

## Key Findings

### 1. Rejection Rate vs Negative Tickets

- **Correlation**: r = 0.45 (p < 0.01)
- **Interpretation**: Moderate positive correlation
- **Lift**: Clinics with high rejection (>30%) have 2.1x more negative tickets

### 2. Event Study: Post-Rejection Ticket Spike

- **Baseline**: 2.3 tickets/week/clinic
- **Post-rejection (0-7 days)**: 4.8 tickets/week/clinic
- **Lift**: 2.1x

### 3. Category Breakdown

| Category | Lift Post-Rejection |
|----------|---------------------|
| Reclamação | 3.2x |
| Dúvida | 1.8x |
| Problema/Bug | 1.1x |

---

## Recommended Actions

1. **Proactive outreach**: Contact clinics after rejection spike
2. **FAQ update**: Add credit rejection FAQs to reduce ticket volume
3. **Monitoring**: Create alert for rejection spike → ticket spike pattern

---

## Caveats

- Correlation ≠ Causation (outros fatores podem estar envolvidos)
- Sample size: 1,234 clinics with both events and tickets
- Time window: 7 days post-event (may miss delayed effects)
```

---

## Recursos Incluídos

### References

**`references/CORRELATION_PATTERNS.md`**:
- Padrões conhecidos de correlação ticket ↔ evento
- Thresholds de significância estatística
- Exemplos de análises anteriores

**`references/CROSS_DOMAIN_JOIN.md`**:
- Como fazer joins cross-domain (clinic_id as glue)
- Handling de clinic_id NULL (B2C tickets)
- Edge cases de linkage

---

## Integração com Outras Skills

**Composes**:
- `@analyze-voc-sentiment` (Tier 3) - Fornece dados de sentimento
- `@analyze-conversion-funnel` (Tier 3, FINTECH) - Fornece dados de rejeição

**Uses**:
- `@debate` (Tier 1) - Para decidir hipótese de correlação
- `@clinic-health-check` (Tier 2) - Usa correlação como sinal de saúde

---

## Anti-Patterns

❌ **Não faça**:
- Assumir causalidade sem validar (correlation ≠ causation)
- Ignorar confounders (sazonalidade, tamanho de clínica)
- Usar time windows muito largos (noise domina signal)
- Esquecer de verificar significância estatística

✅ **Faça**:
- Testar múltiplas hipóteses e comparar
- Controlar para confounders conhecidos
- Usar time windows baseados em lógica de negócio
- Reportar p-values e confidence intervals

---

## Exemplos

### Exemplo 1: Spike de Tickets Após Rejection

**Hipótese**: Clínicas com alta rejeição geram mais tickets negativos

**Query**:
```sql
WITH clinic_rejections AS (
    SELECT 
        clinic_id,
        DATE_TRUNC('week', created_at) AS week,
        COUNT(CASE WHEN outcome_bucket = 'rejected' THEN 1 END) AS rejections
    FROM C1_ENRICHED_BORROWER
    WHERE created_at >= '2024-10-01'
    GROUP BY 1, 2
),
clinic_tickets AS (
    SELECT 
        clinic_id,
        DATE_TRUNC('week', created_at) AS week,
        COUNT(CASE WHEN sentimento_score <= 2 THEN 1 END) AS negative_tickets
    FROM TICKET_ANALYSIS_V3
    WHERE persona = 'B2B' AND created_at >= '2024-10-01'
    GROUP BY 1, 2
)
SELECT 
    r.clinic_id,
    r.week,
    r.rejections,
    COALESCE(t.negative_tickets, 0) AS negative_tickets
FROM clinic_rejections r
LEFT JOIN clinic_tickets t
    ON r.clinic_id = t.clinic_id
   AND r.week = t.week
ORDER BY r.rejections DESC
LIMIT 100;
```

**Output**: Top 100 clínicas por rejeições + tickets negativos

---

### Exemplo 2: Incident → Ticket Category Spike

**Hipótese**: Incidents de sistema causam spike em tickets de "Problema/Bug"

**Query**:
```sql
WITH incident_dates AS (
    -- Datas de incidents conhecidos (manual ou de sistema de monitoring)
    SELECT DATE '2024-11-15' AS incident_date, 'Auth system' AS incident_type
    UNION ALL
    SELECT DATE '2024-12-01', 'Payment processing'
),
ticket_daily AS (
    SELECT 
        DATE_TRUNC('day', created_at) AS day,
        categoria,
        COUNT(*) AS tickets
    FROM TICKET_ANALYSIS_V3
    GROUP BY 1, 2
)
SELECT 
    i.incident_date,
    i.incident_type,
    t.day,
    DATEDIFF('day', i.incident_date, t.day) AS days_after,
    t.categoria,
    t.tickets
FROM incident_dates i
JOIN ticket_daily t
    ON t.day BETWEEN i.incident_date AND DATEADD('day', 7, i.incident_date)
WHERE t.categoria = 'Problema/Bug'
ORDER BY i.incident_date, t.day;
```

**Esperado**: Spike de tickets "Problema/Bug" nos dias 0-3 após incident

---

## Notas Técnicas

- **Snowflake-first**: Fazer joins e agregações no Snowflake
- **Clinic_id as glue**: Principal join key entre domínios
- **B2C exclusion**: Tickets B2C (clinic_id NULL) não podem ser correlacionados
- **Statistical power**: Mínimo ~30 clinics por grupo para significância

---

## Referências

- **Tickets**: `CAPIM_DATA_DEV.POSSANI_SANDBOX.TICKET_ANALYSIS_V3`
- **FINTECH**: `C1_ENRICHED_BORROWER` (via bnpl-funil)
- **SAAS**: `CLINIC_ACTIVITY` (via ontologia-saas)
- **Skill**: `@analyze-voc-sentiment` (dados de sentimento)
