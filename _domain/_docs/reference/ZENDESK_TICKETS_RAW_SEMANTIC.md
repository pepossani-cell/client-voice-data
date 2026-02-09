# Ficha Semântica — CLIENT_VOICE.ZENDESK_TICKETS_RAW

```yaml
---
entity: CLIENT_VOICE.ZENDESK_TICKETS_RAW
domain: CLIENT_VOICE
grain: unknown
trust_level: HYPOTHESIS
last_verified: null
temporal_window:
  start: null
  end: present
  status: ACTIVE
direct_dependencies: []
native_dependents: []
derived_dependents:
  - CLIENT_VOICE.ZENDESK_TICKETS_ENHANCED
failure_modes:
  - null_semantics
  - drift_temporal
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
- **Atribuição de clínica**: `clinic_id` pode ser ausente/incompleto dependendo da origem/enriquecimento.
- **Não assumir grain**: pode haver 1 linha por ticket, mas comentários/eventos podem estar em tabelas separadas.

