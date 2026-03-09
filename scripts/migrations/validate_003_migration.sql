-- Validation script for migration 003 (v3.2)
-- Run AFTER executing 003_natureza_v3_2_contratacao_split.sql
-- Expected result: All checks should pass

\echo '=========================================================================='
\echo 'VALIDATION: Migration 003 (v3.2 - Contratacao Split)'
\echo '=========================================================================='
\echo ''

-- =============================================================================
-- CHECK 1: Constraint exists and includes v3.2 values
-- =============================================================================
\echo '1. Checking constraint definition...'
SELECT 
    conname as constraint_name,
    pg_get_constraintdef(oid) as definition
FROM pg_constraint 
WHERE conname = 'check_root_cause_values'
  AND conrelid = 'ticket_insights'::regclass;

\echo ''
\echo 'Expected: Should include Contratacao_Acompanhamento and Contratacao_Suporte_Paciente'
\echo ''

-- =============================================================================
-- CHECK 2: Test new values are accepted
-- =============================================================================
\echo '2. Testing new values are accepted by constraint...'

-- Test insert (will rollback, just checking constraint)
BEGIN;

-- Create temp test ticket
INSERT INTO ticket_insights (
    zendesk_ticket_id,
    ticket_created_at,
    ticket_updated_at,
    root_cause,
    product_area,
    sentiment,
    llm_confidence
) VALUES 
    (999999991, NOW(), NOW(), 'Contratacao_Acompanhamento', 'BNPL', 3, 0.85),
    (999999992, NOW(), NOW(), 'Contratacao_Suporte_Paciente', 'BNPL', 3, 0.85);

\echo '[OK] New values accepted by constraint'

ROLLBACK;

\echo ''

-- =============================================================================
-- CHECK 3: Current root_cause distribution (before reprocessing)
-- =============================================================================
\echo '3. Current root_cause distribution (v3.1 vs v3.2)...'
SELECT 
    root_cause,
    COUNT(*) as ticket_count,
    ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER () * 100, 2) as pct
FROM ticket_insights
WHERE root_cause LIKE 'Contratacao%'
GROUP BY root_cause
ORDER BY ticket_count DESC;

\echo ''
\echo 'Expected: Only "Contratacao" (v3.1) for now. New values will appear after reprocessing.'
\echo ''

-- =============================================================================
-- CHECK 4: Tickets with venda_* tags (will be reclassified to BNPL)
-- =============================================================================
\echo '4. Tickets with venda_* tags (future BNPL candidates)...'
SELECT 
    COUNT(*) as total_venda_tickets,
    COUNT(*) FILTER (WHERE product_area = 'Onboarding') as currently_onboarding,
    COUNT(*) FILTER (WHERE product_area = 'BNPL') as already_bnpl,
    COUNT(*) FILTER (WHERE product_area NOT IN ('Onboarding', 'BNPL')) as other_products
FROM ticket_insights
WHERE tags::text LIKE '%venda_%';

\echo ''
\echo 'Expected: Most currently classified as Onboarding. After reprocessing, should be BNPL.'
\echo ''

-- =============================================================================
-- CHECK 5: Processing phases (to track reprocessing progress)
-- =============================================================================
\echo '5. Processing phases distribution...'
SELECT 
    processing_phase,
    COUNT(*) as ticket_count,
    MIN(llm_processed_at) as earliest_processed_at,
    MAX(llm_processed_at) as latest_processed_at
FROM ticket_insights
WHERE processing_phase IS NOT NULL
GROUP BY processing_phase
ORDER BY latest_processed_at DESC NULLS LAST
LIMIT 5;

\echo ''
\echo 'Expected: phase_3.1_golden most recent. phase_3.2_golden will appear after reprocessing.'
\echo ''

-- =============================================================================
-- CHECK 6: Legacy Contratacao in Golden Set
-- =============================================================================
\echo '6. Legacy Contratacao tickets in Golden Set...'
SELECT 
    COUNT(*) as legacy_contratacao_count,
    ROUND(AVG(llm_confidence), 3) as avg_confidence
FROM ticket_insights
WHERE processing_phase = 'phase_3.1_golden'
  AND root_cause = 'Contratacao';

\echo ''
\echo 'Expected: ~193 tickets with Contratacao from v3.1 Golden Set.'
\echo ''

-- =============================================================================
-- SUMMARY
-- =============================================================================
\echo '=========================================================================='
\echo 'VALIDATION COMPLETE'
\echo '=========================================================================='
\echo ''
\echo 'If all checks passed:'
\echo '  [OK] Migration 003 was successful'
\echo '  [OK] Database ready for v3.2 reprocessing'
\echo '  [OK] Next step: Run Golden Set reprocessing'
\echo ''
\echo 'Command for Golden Set reprocessing:'
\echo '  cd scripts'
\echo '  python reprocess_tickets_batch.py --phase phase_3.2_golden --limit 1000 --save-to-db'
\echo ''
