-- Migration: Add metadata flags (is_proactive, has_interaction) + expand root_cause to v3
-- Date: 2026-02-13
-- Decisions: 19.26-19.29, 20.3
-- Author: Phase 3.1 implementation
--
-- Changes:
--   1. ADD COLUMN is_proactive (boolean, ~30% TRUE)
--   2. ADD COLUMN has_interaction (boolean, ~87% TRUE)
--   3. EXPAND root_cause CHECK constraint: 15 valores legacy → 18 valores v3 + legacy
--
-- Impact:
--   - Backwards compatible: legacy values still allowed during migration
--   - New columns default NULL (will be populated during Phase 3 reprocessing)
--   - Full backfill required: 171K tickets (~$263-311 batch API cost)

-- =============================================================================
-- STEP 1: Add new metadata columns
-- =============================================================================

-- is_proactive: Capim initiated contact (outbound template whitelist)
-- Derivation: curated list of 18+ templates (outbound_human + system_automated)
-- Volume: ~30% TRUE (~23.5K tickets in 6 months)
ALTER TABLE ticket_insights 
ADD COLUMN IF NOT EXISTS is_proactive BOOLEAN;

COMMENT ON COLUMN ticket_insights.is_proactive IS 
'Flag: Capim iniciou contato (proativo). TRUE = template outbound curado (~30%). FALSE = cliente iniciou (reativo). NULL = não processado ainda. Derivado de whitelist templates (decision 19.28).';

-- has_interaction: Real conversation happened (NOT sem_interacao tag)
-- Derivation: NOT tag 'sem_interacao'
-- Volume: ~87% TRUE (~68K tickets in 6 months)
ALTER TABLE ticket_insights 
ADD COLUMN IF NOT EXISTS has_interaction BOOLEAN;

COMMENT ON COLUMN ticket_insights.has_interaction IS 
'Flag: Houve conversa real. TRUE = conversa real (~87%). FALSE = tag sem_interacao (~13%). NULL = não processado. LLM confidence baixa quando FALSE (69% sentiment=3). Decision 19.29.';

-- =============================================================================
-- STEP 2: Expand root_cause CHECK constraint (15 → 18 valores v3)
-- =============================================================================

-- Drop existing constraint (if exists)
ALTER TABLE ticket_insights 
DROP CONSTRAINT IF EXISTS check_root_cause_values;

-- Add new constraint with v3 values (18) + legacy values (15) for backwards compat
ALTER TABLE ticket_insights 
ADD CONSTRAINT check_root_cause_values 
CHECK (root_cause IN (
    -- ===== NATUREZA v3 (18 valores canônicos) =====
    -- Decision 19.22-19.25: reconciliação empírica + tag audit
    
    -- FUNIL BNPL (4 etapas)
    'Simulacao_Credito',           -- C1: recusa, aprovação, score
    'Contratacao',                 -- C2: orçamento, docs, assinatura
    'Endosso_Repasse',             -- C2→C2S: confirmação, liberação
    'Cobranca_Ativa',              -- Post-C2S: boleto, renegociação
    
    -- PROCESSOS OPERACIONAIS (3)
    'Credenciamento',              -- onboarding/ativação clínica
    'Migracao',                    -- migração de sistema/dados
    'Process_Generico',            -- outros processos
    
    -- ASSINATURA SAAS (2)
    'Subscription_Pagamento',      -- inadimplência SaaS
    'Subscription_Cancelamento',   -- churn SaaS
    
    -- FINANCEIRO / TRANSACIONAL (3)
    'Forma_Pagamento',             -- consultas transacionais
    'Financial_Inquiry',           -- consultas informativas (pacientes)
    'Negativacao',                 -- Serasa, protesto
    
    -- SUPORTE / TÉCNICO (3)
    'Operational_Question',        -- dúvidas de uso
    'Technical_Issue',             -- bugs, falhas
    'Acesso',                      -- login, senha
    
    -- CROSS-CUTTING (3)
    'Carne_Capim',                 -- saque, recebimento carnê
    'Alteracao_Cadastral',         -- dados bancários, CNPJ
    'Unclear',                     -- indeterminado
    
    -- ===== LEGACY (20 valores encontrados na tabela atual) =====
    -- Mantido para backwards compatibility durante migração
    -- Será removido após full backfill (171K tickets)
    -- Nota: alguns valores não estavam documentados mas existem nos dados
    'debt_collection',
    'subscription_issue',
    'operational_issue',
    'technical_issue',
    'financial_operations',
    'process_issue',
    'pos_issue',
    'information_request',
    'complaint',
    'feature_request',
    'migration_issue',
    'integration_issue',
    'data_quality',
    'access_issue',
    'indeterminado',
    'unclear',              -- lowercase variant (4986 tickets)
    'not_applicable',       -- undocumented (1247 tickets)
    'user_error',           -- undocumented (1210 tickets)
    'credit_issue',         -- lowercase variant (709 tickets)
    'product_gap'           -- undocumented (510 tickets)
));

COMMENT ON CONSTRAINT check_root_cause_values ON ticket_insights IS 
'Natureza v3.1: 18 valores canônicos + 15 legacy (backwards compat). Legacy será removido após full backfill. Decisions 19.22-19.29.';

-- =============================================================================
-- STEP 3: Validation queries
-- =============================================================================

-- Check new columns exist
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'ticket_insights' 
  AND column_name IN ('is_proactive', 'has_interaction')
ORDER BY column_name;

-- Check constraint includes v3 values
SELECT conname, pg_get_constraintdef(oid) 
FROM pg_constraint 
WHERE conname = 'check_root_cause_values';

-- Current root_cause distribution (should be all legacy until reprocessing)
SELECT root_cause, COUNT(*) as count
FROM ticket_insights
GROUP BY root_cause
ORDER BY count DESC
LIMIT 20;

-- =============================================================================
-- ROLLBACK (if needed)
-- =============================================================================

-- To rollback this migration:
-- ALTER TABLE ticket_insights DROP COLUMN IF EXISTS is_proactive;
-- ALTER TABLE ticket_insights DROP COLUMN IF EXISTS has_interaction;
-- ALTER TABLE ticket_insights DROP CONSTRAINT IF EXISTS check_root_cause_values;
-- -- Then re-add original CHECK constraint with 15 legacy values only

-- =============================================================================
-- MIGRATION COMPLETE
-- =============================================================================

-- Next steps:
--   1. Run Golden Set reprocessing (1K tickets, ~$2-3)
--   2. Validate precision >= 90% (manual review 100-200 tickets)
--   3. If GO: reprocess subset (24.6K, 3 months)
--   4. If still GO: full backfill (171K tickets, ~$263-311)
--   5. After full backfill: remove legacy values from CHECK constraint
