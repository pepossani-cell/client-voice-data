-- =============================================================================
-- CLIENT VOICE - Setup Snowflake
-- Schema: CAPIM_DATA_DEV.POSSANI_SANDBOX
-- Versão: 2.0
-- Data: 2025-12-05
-- Mudanças: Adiciona campo PERSONA, renomeia source→fonte
-- =============================================================================

-- ⚠️ ATENÇÃO: Se já existem dados, execute o ALTER TABLE ao invés do DROP/CREATE
-- ALTER TABLE CAPIM_DATA_DEV.POSSANI_SANDBOX.ticket_analysis ADD COLUMN persona VARCHAR;

-- =============================================================================
-- OPÇÃO 1: CRIAR DO ZERO (se não existem dados ou quer resetar)
-- =============================================================================

-- DROP das tabelas antigas (CUIDADO: apaga todos os dados!)
-- DROP TABLE IF EXISTS CAPIM_DATA_DEV.POSSANI_SANDBOX.ticket_analysis;
-- DROP TABLE IF EXISTS CAPIM_DATA_DEV.POSSANI_SANDBOX.processing_control;

-- 1. Tabela principal de análises de tickets
CREATE TABLE IF NOT EXISTS CAPIM_DATA_DEV.POSSANI_SANDBOX.ticket_analysis (
    id VARCHAR PRIMARY KEY,                    -- ticket_id do Zendesk
    clinic_id VARCHAR,
    conversation_date TIMESTAMP,
    
    -- 🆕 Novos campos v2.0
    fonte VARCHAR DEFAULT 'Zendesk',           -- Zendesk, Intercom, WhatsApp, etc.
    persona VARCHAR,                            -- Clínica, Paciente, Indefinido
    
    -- Classificações do AI Agent
    tipo_contato VARCHAR,                       -- Dúvida, Reclamação, Solicitação, Sugestão, Elogio
    categoria VARCHAR,                          -- Ver lista por persona
    subcategoria VARCHAR,
    palavras_chaves VARCHAR,
    resumo TEXT,
    citacao TEXT,
    sentimento_score INT,
    
    -- Texto completo (para re-análises futuras)
    conversa TEXT,
    
    -- Metadados de processamento
    conversa_hash VARCHAR,                     -- MD5 hash para detectar mudanças
    model_version VARCHAR DEFAULT 'gpt-4o-mini',
    workflow_version VARCHAR DEFAULT 'v2.0',
    
    -- Controle de timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- 2. Tabela de controle de processamento
CREATE TABLE IF NOT EXISTS CAPIM_DATA_DEV.POSSANI_SANDBOX.processing_control (
    ticket_id VARCHAR PRIMARY KEY,
    last_comment_hash VARCHAR,
    last_comment_date TIMESTAMP,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    status VARCHAR DEFAULT 'success',          -- 'success', 'error', 'pending'
    error_message TEXT,
    retry_count INT DEFAULT 0
);

-- =============================================================================
-- OPÇÃO 2: MIGRAR TABELA EXISTENTE (se já tem dados)
-- =============================================================================

-- Adicionar coluna persona (se não existir)
-- ALTER TABLE CAPIM_DATA_DEV.POSSANI_SANDBOX.ticket_analysis 
-- ADD COLUMN IF NOT EXISTS persona VARCHAR;

-- Renomear source para fonte (se necessário)
-- ALTER TABLE CAPIM_DATA_DEV.POSSANI_SANDBOX.ticket_analysis 
-- RENAME COLUMN source TO fonte;

-- =============================================================================
-- VIEWS ANALÍTICAS
-- =============================================================================

-- 3. View de resumo agregado COM PERSONA
CREATE OR REPLACE VIEW CAPIM_DATA_DEV.POSSANI_SANDBOX.v_ticket_analysis_summary AS
SELECT 
    DATE_TRUNC('day', conversation_date) AS data,
    DATE_TRUNC('week', conversation_date) AS semana,
    DATE_TRUNC('month', conversation_date) AS mes,
    fonte,
    persona,
    tipo_contato,
    categoria,
    subcategoria,
    ROUND(AVG(sentimento_score), 2) AS avg_sentimento,
    COUNT(*) AS total_tickets,
    SUM(CASE WHEN sentimento_score <= 2 THEN 1 ELSE 0 END) AS tickets_negativos,
    SUM(CASE WHEN sentimento_score >= 4 THEN 1 ELSE 0 END) AS tickets_positivos
FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.ticket_analysis
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8;

-- 4. View de frequência de palavras-chave
CREATE OR REPLACE VIEW CAPIM_DATA_DEV.POSSANI_SANDBOX.v_keywords_frequency AS
SELECT 
    DATE_TRUNC('week', conversation_date) AS semana,
    persona,
    categoria,
    TRIM(keyword.value) AS palavra_chave,
    COUNT(*) AS frequencia
FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.ticket_analysis,
    LATERAL FLATTEN(input => SPLIT(palavras_chaves, ',')) AS keyword
WHERE palavras_chaves IS NOT NULL
GROUP BY 1, 2, 3, 4;

-- 5. 🆕 View de métricas por persona
CREATE OR REPLACE VIEW CAPIM_DATA_DEV.POSSANI_SANDBOX.v_metrics_by_persona AS
SELECT 
    DATE_TRUNC('week', conversation_date) AS semana,
    persona,
    COUNT(*) AS total_tickets,
    ROUND(AVG(sentimento_score), 2) AS avg_sentimento,
    COUNT(DISTINCT categoria) AS categorias_distintas,
    SUM(CASE WHEN tipo_contato = 'Reclamação' THEN 1 ELSE 0 END) AS total_reclamacoes,
    SUM(CASE WHEN tipo_contato = 'Dúvida' THEN 1 ELSE 0 END) AS total_duvidas,
    SUM(CASE WHEN tipo_contato = 'Solicitação' THEN 1 ELSE 0 END) AS total_solicitacoes,
    SUM(CASE WHEN tipo_contato = 'Elogio' THEN 1 ELSE 0 END) AS total_elogios
FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.ticket_analysis
WHERE persona IS NOT NULL
GROUP BY 1, 2;

-- 6. 🆕 View de top categorias por persona
CREATE OR REPLACE VIEW CAPIM_DATA_DEV.POSSANI_SANDBOX.v_top_categories AS
SELECT 
    DATE_TRUNC('month', conversation_date) AS mes,
    persona,
    categoria,
    COUNT(*) AS total,
    ROUND(AVG(sentimento_score), 2) AS avg_sentimento,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY DATE_TRUNC('month', conversation_date), persona), 1) AS pct_do_total
FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.ticket_analysis
WHERE persona IS NOT NULL
GROUP BY 1, 2, 3
ORDER BY 1 DESC, 2, 4 DESC;

-- =============================================================================
-- QUERIES PARA LIMPAR E RECOMEÇAR
-- =============================================================================

-- Limpar todos os dados (TRUNCATE é mais rápido que DELETE)
-- TRUNCATE TABLE CAPIM_DATA_DEV.POSSANI_SANDBOX.ticket_analysis;
-- TRUNCATE TABLE CAPIM_DATA_DEV.POSSANI_SANDBOX.processing_control;

-- =============================================================================
-- VERIFICAÇÃO
-- =============================================================================
SELECT 'ticket_analysis' AS tabela, COUNT(*) AS registros 
FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.ticket_analysis
UNION ALL
SELECT 'processing_control', COUNT(*) 
FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.processing_control;

-- Verificar estrutura da tabela
-- DESCRIBE TABLE CAPIM_DATA_DEV.POSSANI_SANDBOX.ticket_analysis;

