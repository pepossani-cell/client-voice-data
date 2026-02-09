# Ficha Semântica — CLIENT_VOICE.ZENDESK_TICKETS_RAW

```yaml
---
entity: CLIENT_VOICE.ZENDESK_TICKETS_RAW
domain: CLIENT_VOICE
grain: 1 row per zendesk_ticket_id
trust_level: VERIFY
last_verified: 2026-02-09
snowflake_table: CAPIM_DATA.CAPIM_ANALYTICS.ZENDESK_TICKETS_RAW
primary_key: ZENDESK_TICKET_ID
temporal_window:
  start: "2022-02-04"
  end: "2026-02-08"
  status: ACTIVE
direct_dependencies: []
native_dependents: []
derived_dependents:
  - CLIENT_VOICE.ZENDESK_TICKETS_ENHANCED
failure_modes:
  - drift_temporal
  - null_semantics
full_reference: "docs/reference/ZENDESK_TICKETS_RAW.md"
drill_down_triggers:
  - "mudança de schema no Zendesk"
  - "atribuição de clinic_id baixa"
---
```

## Descrição

Tickets do Zendesk em formato **raw/enriquecido mínimo**, usados como base para enriquecimentos e classificação (ex.: `CLIENT_VOICE.ZENDESK_TICKETS_ENHANCED`).

## Guardrails

- **Timestamps**: Zendesk tipicamente está em UTC; normalizar para BRT quando necessário.
- **Atribuição de clínica**: `clinic_id` frequentemente está ausente no RAW; para consumo analítico, preferir a entidade enhanced.
- **Grain verificado**: 1 linha por ticket (`zendesk_ticket_id`), sem duplicatas na PK (verificação 2026-02-09).
- **Eventos/comentários**: o histórico detalhado não está aqui; comentários/eventos costumam viver em tabelas próprias.

