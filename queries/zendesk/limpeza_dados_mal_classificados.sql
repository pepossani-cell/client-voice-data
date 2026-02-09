-- =============================================================================
-- QUERIES PARA LIMPEZA DE DADOS MAL CLASSIFICADOS
-- Baseado no workflow V3 (eQEByyVKRHtD4uBa)
-- Prompt Versão 3.0 Estratégica - Classificador de Tickets VoC
-- =============================================================================
-- 
-- ⚠️ IMPORTANTE: Execute as queries de ANÁLISE primeiro para revisar os dados
-- antes de executar as queries de LIMPEZA (DELETE).
--
-- ⚠️ NOTA: O workflow atualizado usa `ticket_analysis_v3` e `processing_control_v3` (com _v3).
-- As queries abaixo usam os nomes corretos conforme o workflow.
--
-- =============================================================================
-- VALORES VÁLIDOS CONFORME O PROMPT V3.0 ESTRATÉGICA
-- =============================================================================
--
-- PERSONAS válidas:
--   - Clínica
--   - Paciente
--   - Indefinido
--
-- TIPO DE CONTATO válidos:
--   - Dúvida
--   - Reclamação
--   - Solicitação
--   - Sugestão
--   - Elogio
--
-- CATEGORIAS (ÚNICAS - não dependem de persona):
--   1. BNPL Financiamento
--   2. BNPL Cobrança
--   3. SaaS
--   4. Maquininha
--   5. Carnê Capim
--   6. Cancelamento
--   7. Contato comercial
--   8. Mensagem incoerente
--   9. Inteligência artificial
--
-- =============================================================================
-- 1. QUERY DE ANÁLISE: Resumo de problemas encontrados
-- =============================================================================
-- Execute esta query primeiro para ver quantos registros serão afetados

SELECT 
    'Persona inválida ou NULL' AS problema,
    COUNT(*) AS quantidade,
    LISTAGG(DISTINCT persona, ', ') WITHIN GROUP (ORDER BY persona) AS valores_encontrados
FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.ticket_analysis_v3
WHERE persona IS NULL
   OR persona = ''
   OR persona NOT IN ('Clínica', 'Paciente', 'Indefinido')
   OR persona LIKE '%/%'
   OR persona LIKE '%,%'

UNION ALL

SELECT 
    'Tipo de Contato inválido ou NULL' AS problema,
    COUNT(*) AS quantidade,
    LISTAGG(DISTINCT tipo_contato, ', ') WITHIN GROUP (ORDER BY tipo_contato) AS valores_encontrados
FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.ticket_analysis_v3
WHERE tipo_contato IS NULL
   OR tipo_contato = ''
   OR tipo_contato NOT IN ('Dúvida', 'Reclamação', 'Solicitação', 'Sugestão', 'Elogio')
   OR tipo_contato LIKE '%/%'
   OR tipo_contato LIKE '%,%'

UNION ALL

SELECT 
    'Categoria inválida ou NULL' AS problema,
    COUNT(*) AS quantidade,
    LISTAGG(DISTINCT categoria, ', ') WITHIN GROUP (ORDER BY categoria) AS valores_encontrados
FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.ticket_analysis_v3
WHERE categoria IS NULL
   OR categoria = ''
   OR categoria NOT IN (
       'BNPL Financiamento', 'BNPL Cobrança', 'SaaS', 'Maquininha',
       'Carnê Capim', 'Cancelamento', 'Contato comercial',
       'Mensagem incoerente', 'Inteligência artificial'
   )
   OR categoria LIKE '%/%'
   OR categoria LIKE '%,%'

UNION ALL

SELECT 
    'Persona com múltiplos valores' AS problema,
    COUNT(*) AS quantidade,
    LISTAGG(DISTINCT persona, ', ') WITHIN GROUP (ORDER BY persona) AS valores_encontrados
FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.ticket_analysis_v3
WHERE persona LIKE '%/%'
   OR persona LIKE '%,%'
   OR persona LIKE '% e %'
   OR persona LIKE '% / %'

UNION ALL

SELECT 
    'Tipo de Contato com múltiplos valores' AS problema,
    COUNT(*) AS quantidade,
    LISTAGG(DISTINCT tipo_contato, ', ') WITHIN GROUP (ORDER BY tipo_contato) AS valores_encontrados
FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.ticket_analysis_v3
WHERE tipo_contato LIKE '%/%'
   OR tipo_contato LIKE '%,%'
   OR tipo_contato LIKE '% e %'
   OR tipo_contato LIKE '% / %'

UNION ALL

SELECT 
    'Categoria com múltiplos valores' AS problema,
    COUNT(*) AS quantidade,
    LISTAGG(DISTINCT categoria, ', ') WITHIN GROUP (ORDER BY categoria) AS valores_encontrados
FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.ticket_analysis_v3
WHERE categoria LIKE '%/%'
   OR categoria LIKE '%,%'
   OR categoria LIKE '% e %'
   OR categoria LIKE '% / %';

-- =============================================================================
-- 2. QUERY DETALHADA: Listar todos os tickets mal classificados
-- =============================================================================
-- Use esta query para revisar os tickets antes de deletar

SELECT 
    id AS ticket_id,
    persona,
    tipo_contato,
    categoria,
    subcategoria,
    sentimento_score,
    conversation_date,
    created_at,
    workflow_version,
    CASE 
        WHEN persona IS NULL OR persona = '' THEN 'Persona NULL/vazia'
        WHEN persona NOT IN ('Clínica', 'Paciente', 'Indefinido') THEN 'Persona inválida: ' || persona
        WHEN persona LIKE '%/%' OR persona LIKE '%,%' THEN 'Persona múltipla: ' || persona
        WHEN tipo_contato IS NULL OR tipo_contato = '' THEN 'Tipo de Contato NULL/vazio'
        WHEN tipo_contato NOT IN ('Dúvida', 'Reclamação', 'Solicitação', 'Sugestão', 'Elogio') THEN 'Tipo de Contato inválido: ' || tipo_contato
        WHEN tipo_contato LIKE '%/%' OR tipo_contato LIKE '%,%' THEN 'Tipo de Contato múltiplo: ' || tipo_contato
        WHEN categoria IS NULL OR categoria = '' THEN 'Categoria NULL/vazia'
        WHEN categoria NOT IN (
            'BNPL Financiamento', 'BNPL Cobrança', 'SaaS', 'Maquininha',
            'Carnê Capim', 'Cancelamento', 'Contato comercial',
            'Mensagem incoerente', 'Inteligência artificial'
        ) THEN 'Categoria inválida: ' || categoria
        WHEN categoria LIKE '%/%' OR categoria LIKE '%,%' THEN 'Categoria múltipla: ' || categoria
        ELSE 'OK'
    END AS motivo_invalido
FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.ticket_analysis_v3
WHERE 
    -- Persona inválida
    (persona IS NULL 
     OR persona = ''
     OR persona NOT IN ('Clínica', 'Paciente', 'Indefinido')
     OR persona LIKE '%/%'
     OR persona LIKE '%,%'
     OR persona LIKE '% e %'
     OR persona LIKE '% / %')
    OR
    -- Tipo de Contato inválido
    (tipo_contato IS NULL 
     OR tipo_contato = ''
     OR tipo_contato NOT IN ('Dúvida', 'Reclamação', 'Solicitação', 'Sugestão', 'Elogio')
     OR tipo_contato LIKE '%/%'
     OR tipo_contato LIKE '%,%'
     OR tipo_contato LIKE '% e %'
     OR tipo_contato LIKE '% / %')
    OR
    -- Categoria inválida (categorias são únicas, não dependem de persona)
    (categoria IS NULL 
     OR categoria = ''
     OR categoria NOT IN (
         'BNPL Financiamento', 'BNPL Cobrança', 'SaaS', 'Maquininha',
         'Carnê Capim', 'Cancelamento', 'Contato comercial',
         'Mensagem incoerente', 'Inteligência artificial'
     )
     OR categoria LIKE '%/%'
     OR categoria LIKE '%,%'
     OR categoria LIKE '% e %'
     OR categoria LIKE '% / %')
ORDER BY conversation_date DESC;

-- =============================================================================
-- 3. QUERY DE LIMPEZA: Deletar tickets mal classificados da ticket_analysis_v3
-- =============================================================================
-- ⚠️ ATENÇÃO: Execute esta query apenas após revisar os resultados acima!

DELETE FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.ticket_analysis_v3
WHERE 
    -- Persona inválida
    (persona IS NULL 
     OR persona = ''
     OR persona NOT IN ('Clínica', 'Paciente', 'Indefinido')
     OR persona LIKE '%/%'
     OR persona LIKE '%,%'
     OR persona LIKE '% e %'
     OR persona LIKE '% / %')
    OR
    -- Tipo de Contato inválido
    (tipo_contato IS NULL 
     OR tipo_contato = ''
     OR tipo_contato NOT IN ('Dúvida', 'Reclamação', 'Solicitação', 'Sugestão', 'Elogio')
     OR tipo_contato LIKE '%/%'
     OR tipo_contato LIKE '%,%'
     OR tipo_contato LIKE '% e %'
     OR tipo_contato LIKE '% / %')
    OR
    -- Categoria inválida (categorias são únicas, não dependem de persona)
    (categoria IS NULL 
     OR categoria = ''
     OR categoria NOT IN (
         'BNPL Financiamento', 'BNPL Cobrança', 'SaaS', 'Maquininha',
         'Carnê Capim', 'Cancelamento', 'Contato comercial',
         'Mensagem incoerente', 'Inteligência artificial'
     )
     OR categoria LIKE '%/%'
     OR categoria LIKE '%,%'
     OR categoria LIKE '% e %'
     OR categoria LIKE '% / %');

-- =============================================================================
-- 4. QUERY DE LIMPEZA: Deletar do processing_control_v3
-- =============================================================================
-- Remove os tickets do controle de processamento para permitir reprocessamento

DELETE FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.processing_control_v3
WHERE ticket_id IN (
    SELECT id
    FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.ticket_analysis_v3
    WHERE 
        -- Persona inválida
        (persona IS NULL 
         OR persona = ''
         OR persona NOT IN ('Clínica', 'Paciente', 'Indefinido')
         OR persona LIKE '%/%'
         OR persona LIKE '%,%'
         OR persona LIKE '% e %'
         OR persona LIKE '% / %')
        OR
        -- Tipo de Contato inválido
        (tipo_contato IS NULL 
         OR tipo_contato = ''
         OR tipo_contato NOT IN ('Dúvida', 'Reclamação', 'Solicitação', 'Sugestão', 'Elogio')
         OR tipo_contato LIKE '%/%'
         OR tipo_contato LIKE '%,%'
         OR tipo_contato LIKE '% e %'
         OR tipo_contato LIKE '% / %')
        OR
        -- Categoria inválida (categorias são únicas, não dependem de persona)
        (categoria IS NULL 
         OR categoria = ''
         OR categoria NOT IN (
             'BNPL Financiamento', 'BNPL Cobrança', 'SaaS', 'Maquininha',
             'Carnê Capim', 'Cancelamento', 'Contato comercial',
             'Mensagem incoerente', 'Inteligência artificial'
         )
         OR categoria LIKE '%/%'
         OR categoria LIKE '%,%'
         OR categoria LIKE '% e %'
         OR categoria LIKE '% / %')
);

-- =============================================================================
-- 5. QUERY ALTERNATIVA: Limpeza mais conservadora (apenas NULL/vazios e múltiplos valores)
-- =============================================================================
-- Use esta versão se quiser ser mais conservador e remover apenas casos óbvios

DELETE FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.ticket_analysis_v3
WHERE 
    persona IS NULL 
    OR persona = ''
    OR tipo_contato IS NULL 
    OR tipo_contato = ''
    OR categoria IS NULL 
    OR categoria = ''
    OR persona LIKE '%/%'
    OR persona LIKE '%,%'
    OR tipo_contato LIKE '%/%'
    OR tipo_contato LIKE '%,%'
    OR categoria LIKE '%/%'
    OR categoria LIKE '%,%';

-- E do controle:
DELETE FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.processing_control_v3
WHERE ticket_id IN (
    SELECT id
    FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.ticket_analysis_v3
    WHERE persona IS NULL 
       OR persona = ''
       OR tipo_contato IS NULL 
       OR tipo_contato = ''
       OR categoria IS NULL 
       OR categoria = ''
       OR persona LIKE '%/%'
       OR persona LIKE '%,%'
       OR tipo_contato LIKE '%/%'
       OR tipo_contato LIKE '%,%'
       OR categoria LIKE '%/%'
       OR categoria LIKE '%,%'
);

-- =============================================================================
-- 6. QUERY DE VERIFICAÇÃO: Contar registros após limpeza
-- =============================================================================
-- Execute após a limpeza para confirmar

SELECT 
    'ticket_analysis_v3' AS tabela,
    COUNT(*) AS total_registros,
    COUNT(DISTINCT id) AS tickets_unicos,
    COUNT(DISTINCT persona) AS personas_distintas,
    COUNT(DISTINCT tipo_contato) AS tipos_contato_distintos,
    COUNT(DISTINCT categoria) AS categorias_distintas
FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.ticket_analysis_v3

UNION ALL

SELECT 
    'processing_control_v3' AS tabela,
    COUNT(*) AS total_registros,
    COUNT(DISTINCT ticket_id) AS tickets_unicos,
    NULL AS personas_distintas,
    NULL AS tipos_contato_distintos,
    NULL AS categorias_distintas
FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.processing_control_v3;

-- =============================================================================
-- 7. QUERY DE DISTRIBUIÇÃO: Ver distribuição de personas e categorias válidas
-- =============================================================================
-- Use para verificar se os dados restantes estão corretos

SELECT 
    persona,
    tipo_contato,
    categoria,
    COUNT(*) AS quantidade
FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.ticket_analysis_v3
WHERE persona IN ('Clínica', 'Paciente', 'Indefinido')
  AND tipo_contato IN ('Dúvida', 'Reclamação', 'Solicitação', 'Sugestão', 'Elogio')
  AND categoria IN (
      'BNPL Financiamento', 'BNPL Cobrança', 'SaaS', 'Maquininha',
      'Carnê Capim', 'Cancelamento', 'Contato comercial',
      'Mensagem incoerente', 'Inteligência artificial'
  )
GROUP BY persona, tipo_contato, categoria
ORDER BY persona, categoria, tipo_contato;
