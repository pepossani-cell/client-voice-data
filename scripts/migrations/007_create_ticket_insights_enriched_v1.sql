-- 007_create_ticket_insights_enriched_v1.sql
-- Creates a VIEW with deterministic enrichment columns.
-- Does NOT modify ticket_insights; consumption layer for Phase 4.

BEGIN;

DROP VIEW IF EXISTS ticket_insights_enriched_v1;

CREATE VIEW ticket_insights_enriched_v1 AS
WITH base AS (
  SELECT
    ti.*,
    char_length(ti.full_conversation) AS conv_len,
    COALESCE(ti.product_area, 'Indeterminado') AS product_area_coalesced,
    LOWER(COALESCE(ti.tags, '')) AS tags_lc
  FROM ticket_insights ti
),
themes AS (
  SELECT
    b.*,
    NULLIF(
      CASE LOWER(TRIM(COALESCE(b.key_themes[1], '')))
        WHEN '' THEN ''
        WHEN 'assinatura' THEN 'plano'
        WHEN 'financiamento' THEN 'contrato'
        WHEN 'parcelamento' THEN 'parcela'
        WHEN 'negociacao' THEN 'renegociacao'
        WHEN 'quitacao' THEN 'pagamento'
        WHEN 'comprovante' THEN 'pagamento'
        WHEN 'comprovante_pagamento' THEN 'pagamento'
        WHEN 'treinamento' THEN 'onboarding'
        WHEN 'exportacao' THEN 'relatorio'
        WHEN 'maquininha' THEN 'ativacao'
        WHEN 'financeiro' THEN 'pagamento'
        ELSE LOWER(TRIM(COALESCE(b.key_themes[1], '')))
      END,
      ''
    ) AS key_theme_primary_norm,
    ARRAY(
      SELECT
        NULLIF(
          CASE LOWER(TRIM(t))
            WHEN '' THEN ''
            WHEN 'assinatura' THEN 'plano'
            WHEN 'financiamento' THEN 'contrato'
            WHEN 'parcelamento' THEN 'parcela'
            WHEN 'negociacao' THEN 'renegociacao'
            WHEN 'quitacao' THEN 'pagamento'
            WHEN 'comprovante' THEN 'pagamento'
            WHEN 'comprovante_pagamento' THEN 'pagamento'
            WHEN 'treinamento' THEN 'onboarding'
            WHEN 'exportacao' THEN 'relatorio'
            WHEN 'maquininha' THEN 'ativacao'
            WHEN 'financeiro' THEN 'pagamento'
            ELSE LOWER(TRIM(t))
          END,
          ''
        )
      FROM unnest(COALESCE(b.key_themes, ARRAY[]::text[])) AS t
    ) AS key_themes_norm
  FROM base b
)
SELECT
  t.*,
  -- Deterministic flags useful for routing/BI
  (t.tags_lc LIKE '%droz_%' OR t.tags_lc LIKE '%cloudhumans%' OR t.is_claudinha_assigned IS TRUE) AS is_bot_flow,
  (t.tags_lc LIKE '%sem_interacao%' OR t.tags_lc LIKE '%fechado_via_pesquisa_satisfacao%' OR t.tags_lc LIKE '%fora_horario_atendimento%') AS is_low_signal_flow,
  (t.tags_lc LIKE '%web_widget%' OR t.via_channel IN ('web', 'native_messaging')) AS is_widget_flow,

  -- Indeterminado bucket (deterministic)
  CASE
    WHEN t.product_area_coalesced <> 'Indeterminado' THEN 'not_indeterminado'
    WHEN t.conv_len IS NULL OR t.conv_len < 200 THEN 'junk'
    WHEN (t.tags_lc LIKE '%droz_switchboard%' OR t.tags_lc LIKE '%cloudhumans%' OR t.tags_lc LIKE '%droz_receptivo%' OR t.tags_lc LIKE '%sem_interacao%' OR t.tags_lc LIKE '%web_widget%')
      THEN 'junk'
    ELSE 'signal'
  END AS indeterminado_bucket
FROM themes t;

COMMIT;

