-- Migration 006: Split billing_issue into debt_collection (BNPL) + financial_operations (SAAS)
-- Decision: 20.4b — "billing_issue" was ambiguous across domains
-- Date: 2026-02-10
--
-- debt_collection: boleto, parcela, renegociacao, quitacao, PIX (o que Cobranca faz)
-- financial_operations: orcamento, checkout, comissao, recebivel (ops financeiras da clinica)

-- Step 1: Drop existing constraint
ALTER TABLE ticket_insights
DROP CONSTRAINT IF EXISTS check_root_cause_values;

-- Step 2: Rename existing billing_issue rows based on product_area
-- BNPL tickets → debt_collection
UPDATE ticket_insights
SET root_cause = 'debt_collection'
WHERE root_cause = 'billing_issue'
  AND product_area IN ('BNPL_Cobranca', 'BNPL_Financiamento', 'BNPL_Suporte');

-- SAAS tickets → financial_operations
UPDATE ticket_insights
SET root_cause = 'financial_operations'
WHERE root_cause = 'billing_issue'
  AND product_area IN ('SaaS_Operacional', 'SaaS_Billing');

-- Remaining billing_issue (POS, Venda, Indeterminado) → debt_collection as default
-- Rationale: Generic/POS billing tickets are more similar to BNPL cobranca pattern
UPDATE ticket_insights
SET root_cause = 'debt_collection'
WHERE root_cause = 'billing_issue';

-- Step 3: Recreate constraint with new taxonomy (11 values, replacing billing_issue with 2 new)
ALTER TABLE ticket_insights
ADD CONSTRAINT check_root_cause_values CHECK (
    root_cause IN (
        'debt_collection',        -- NEW: replaces billing_issue for BNPL (boleto, parcela, renegociacao)
        'financial_operations',   -- NEW: replaces billing_issue for SAAS (orcamento, checkout, comissao)
        'credit_issue',
        'process_issue',
        'product_gap',
        'user_error',
        'subscription_issue',
        'operational_issue',
        'technical_issue',
        'unclear',
        'not_applicable'
    )
);

-- Step 4: Update column comment
COMMENT ON COLUMN ticket_insights.root_cause IS 'Primary cause of ticket: debt_collection, financial_operations, credit_issue, process_issue, product_gap, user_error, subscription_issue, operational_issue, technical_issue, unclear, not_applicable';

-- Step 5: Verify no billing_issue remains
DO $$
DECLARE
    remaining_count INT;
BEGIN
    SELECT COUNT(*) INTO remaining_count
    FROM ticket_insights
    WHERE root_cause = 'billing_issue';
    
    IF remaining_count > 0 THEN
        RAISE EXCEPTION '[FAIL] Migration 006: % tickets still have billing_issue!', remaining_count;
    END IF;
    
    RAISE NOTICE '[OK] Migration 006 completed. billing_issue split into debt_collection + financial_operations. 0 billing_issue remaining.';
END $$;
