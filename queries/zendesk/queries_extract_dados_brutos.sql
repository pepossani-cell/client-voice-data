-- =============================================================================
-- QUERIES PARA EXTRAÇÃO DE DADOS BRUTOS (SEM JOINS)
-- O Agente Desenvolvedor Python fará os joins
-- =============================================================================

-- =============================================================================
-- 1. CLINIC_MOST_RELEVANT_INFO
-- =============================================================================
-- Extrair dados cadastrais e comportamentais das clínicas
-- NOTA: Ajustar colunas conforme estrutura real da tabela

SELECT 
    clinic_id,
    -- Adicionar campos relevantes conforme disponível na tabela
    is_subscriber,
    was_subscriber,
    created_at as clinic_created_at
    -- Adicionar outros campos comportamentais se disponíveis
    -- total_simulacoes,
    -- total_origens,
    -- tpv_maquininha,
    -- etc.
FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.CLINIC_MOST_RELEVANT_INFO
WHERE clinic_id IS NOT NULL;


-- =============================================================================
-- 2. CLINIC_CANCELLATION_REQUESTS
-- =============================================================================
-- Extrair solicitações de cancelamento

SELECT 
    clinic_id,
    request_date,
    -- Adicionar campos de motivo se disponível
    -- reason,
    -- status,
    -- etc.
    COUNT(*) OVER (PARTITION BY clinic_id) as total_cancellations
FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.CLINIC_CANCELLATION_REQUESTS
WHERE clinic_id IS NOT NULL
ORDER BY clinic_id, request_date DESC;


-- =============================================================================
-- 3. ZENDESK_ANALYSIS
-- =============================================================================
-- Extrair análise de tickets de suporte (últimos 6 meses)

SELECT 
    clinic_id,
    id as ticket_id,
    conversation_date,
    persona,
    tipo_contato,
    categoria,
    subcategoria,
    palavras_chaves,
    resumo,
    citacao,
    sentimento_score,
    -- Adicionar outros campos se disponíveis
    confidence_score,
    depth_score,
    relevance_score
FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.ZENDESK_ANALYSIS
WHERE clinic_id IS NOT NULL
    AND conversation_date >= DATEADD(month, -6, CURRENT_DATE())
ORDER BY conversation_date DESC;

