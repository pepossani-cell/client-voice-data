-- Migration: Split Contratacao + Correção venda_* → BNPL (Natureza v3.2)
-- Date: 2026-02-13
-- Decisions: venda_* investigation + Contratacao split
-- Author: Taxonomy refinement Phase 3.2
--
-- Changes:
--   1. EXPAND root_cause CHECK constraint: 18 valores v3.1 → 19 valores v3.2 + legacy
--   2. Split 'Contratacao' → 'Contratacao_Acompanhamento' + 'Contratacao_Suporte_Paciente'
--   3. Absorb 'venda_dificuldade_na_assinatura' → 'Technical_Issue'
--   4. Correção: venda_* tags NOW map to BNPL (not Onboarding)
--
-- Impact:
--   - Backwards compatible: 'Contratacao' (legacy) still allowed for Golden Set (N=1000)
--   - New values will be applied in subset/full backfill
--   - Net change: 18 → 19 Naturezas (split +2, absorb -1)
--
-- Semantic Clarification:
--   - ALL venda_* tags relate to BNPL sales support (clinic helping patient get credit)
--   - venda_* NO LONGER maps to Onboarding (product classifier updated)
--   - Contratacao split provides granular insight: follow-up vs friction

-- =============================================================================
-- STEP 1: Expand root_cause CHECK constraint (18 → 19 valores v3.2)
-- =============================================================================

-- Drop existing constraint
ALTER TABLE ticket_insights 
DROP CONSTRAINT IF EXISTS check_root_cause_values;

-- Add new constraint with v3.2 values (19) + legacy for backwards compat
ALTER TABLE ticket_insights 
ADD CONSTRAINT check_root_cause_values 
CHECK (root_cause IN (
    -- ===== NATUREZA v3.2 (19 valores canônicos) =====
    -- Decision: Contratacao split + venda_* → BNPL
    
    -- FUNIL BNPL (5 etapas — Contratacao split expands funnel)
    'Simulacao_Credito',                -- C1: recusa, aprovação, score
    'Contratacao_Acompanhamento',       -- C2: follow-up genérico (venda_si_suporte, venda_apenas_acompanhamento)
    'Contratacao_Suporte_Paciente',     -- C2: fricção de docs/telefone/assinatura (venda_si_*)
    'Endosso_Repasse',                  -- C2→C2S: confirmação, liberação
    'Cobranca_Ativa',                   -- Post-C2S: boleto, renegociação
    
    -- PROCESSOS OPERACIONAIS (3)
    'Credenciamento',                   -- onboarding/ativação clínica (BNPL/POS)
    'Migracao',                         -- migração de sistema/dados
    'Process_Generico',                 -- outros processos
    
    -- ASSINATURA SAAS (2)
    'Subscription_Pagamento',           -- inadimplência SaaS
    'Subscription_Cancelamento',        -- churn SaaS
    
    -- FINANCEIRO / TRANSACIONAL (3)
    'Forma_Pagamento',                  -- consultas transacionais
    'Financial_Inquiry',                -- consultas informativas (pacientes)
    'Negativacao',                      -- Serasa, protesto
    
    -- SUPORTE / TÉCNICO (3)
    'Operational_Question',             -- dúvidas de uso
    'Technical_Issue',                  -- bugs, falhas (NOW includes venda_dificuldade_na_assinatura)
    'Acesso',                           -- login, senha
    
    -- CROSS-CUTTING (3)
    'Carne_Capim',                      -- saque, recebimento carnê
    'Alteracao_Cadastral',              -- dados bancários, CNPJ
    'Unclear',                          -- indeterminado
    
    -- ===== LEGACY (kept for Golden Set + old tickets) =====
    -- 'Contratacao' (v3.1) → KEPT for backwards compatibility
    'Contratacao',                      -- legacy v3.1 (193 tickets in Golden Set)
    
    -- Other legacy values (20+ from previous migrations)
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
    'unclear',              -- lowercase variant
    'not_applicable',
    'user_error',
    'credit_issue',         -- lowercase variant
    'product_gap'
));

COMMENT ON CONSTRAINT check_root_cause_values ON ticket_insights IS 
'Natureza v3.2: 19 valores canônicos (Contratacao split) + legacy. venda_* tags NOW map to BNPL (NOT Onboarding). Legacy maintained for Golden Set (N=1000). Will be removed after full backfill.';

-- =============================================================================
-- STEP 2: Validation queries
-- =============================================================================

-- Check constraint includes v3.2 values
SELECT conname, pg_get_constraintdef(oid) 
FROM pg_constraint 
WHERE conname = 'check_root_cause_values';

-- Current root_cause distribution
SELECT root_cause, COUNT(*) as count
FROM ticket_insights
WHERE root_cause IN ('Contratacao', 'Contratacao_Acompanhamento', 'Contratacao_Suporte_Paciente')
GROUP BY root_cause
ORDER BY count DESC;

-- Count tickets with venda_* tags (should map to BNPL after reprocessing)
SELECT COUNT(*) as venda_tag_tickets
FROM ticket_insights
WHERE tags::text LIKE '%venda_%';

-- =============================================================================
-- ROLLBACK (if needed)
-- =============================================================================

-- To rollback this migration:
-- ALTER TABLE ticket_insights DROP CONSTRAINT IF EXISTS check_root_cause_values;
-- -- Then re-add v3.1 CHECK constraint (18 valores) from migration 001

-- =============================================================================
-- MIGRATION COMPLETE
-- =============================================================================

-- Next steps:
--   1. Update PRODUTO_TAG_RULES: venda_* → BNPL (DONE in reprocess_tickets_full_taxonomy.py)
--   2. Update TIER1_NATUREZA_RULES: Contratacao → split (DONE in prompt_compiler.py)
--   3. Update LLM prompt: 18 → 19 valores
--   4. Update TAXONOMY_3_AXES.md: document v3.2
--   5. Run validation tests (unit tests + population counts)
--   6. Reprocess subset (24.6K tickets, 3 months)
--   7. After validation: full backfill (171K tickets)
