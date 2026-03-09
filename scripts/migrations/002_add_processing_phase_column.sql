-- Migration: Add processing_phase column for audit trail
-- Date: 2026-02-13
-- Decision: User request (session 2026-02-13)
-- Author: Phase 3.1 enhancement
--
-- Purpose:
--   Track which reprocessing phase was applied to each ticket
--   Enables:
--     - Audit trail (when was each ticket last reprocessed?)
--     - Granular rollback (revert only specific phase if needed)
--     - Quality comparison (Phase 3.1 Golden vs Subset vs Full)
--     - Debugging (isolate issues by phase)
--
-- Values:
--   NULL or 'legacy'        → Not reprocessed yet (original Phase 2 logic)
--   'phase_3.1_golden'      → Golden Set (1K tickets, GO/NO-GO validation)
--   'phase_3.1_subset'      → Subset (24.6K tickets, 3 months recent)
--   'phase_3.1_full'        → Full backfill (171K tickets, complete reprocessing)
--
-- Usage in script:
--   python reprocess_tickets_full_taxonomy.py --phase phase_3.1_golden --limit 1000
--   python reprocess_tickets_full_taxonomy.py --phase phase_3.1_subset --limit 24600
--   python reprocess_tickets_full_taxonomy.py --phase phase_3.1_full

-- =============================================================================
-- Add processing_phase column
-- =============================================================================

ALTER TABLE ticket_insights 
ADD COLUMN IF NOT EXISTS processing_phase VARCHAR(50);

COMMENT ON COLUMN ticket_insights.processing_phase IS 
'Reprocessing phase applied. Values: NULL/legacy (not reprocessed), phase_3.1_golden (1K validation), phase_3.1_subset (24.6K recent), phase_3.1_full (171K complete). Updated atomically with llm_processed_at.';

-- =============================================================================
-- Validation queries
-- =============================================================================

-- Check column exists
SELECT column_name, data_type, character_maximum_length, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'ticket_insights' 
  AND column_name = 'processing_phase';

-- Current distribution (should be 100% NULL before reprocessing)
SELECT 
    processing_phase,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as pct
FROM ticket_insights
GROUP BY processing_phase
ORDER BY count DESC;

-- =============================================================================
-- ROLLBACK (if needed)
-- =============================================================================

-- To rollback this migration:
-- ALTER TABLE ticket_insights DROP COLUMN IF EXISTS processing_phase;

-- =============================================================================
-- MIGRATION COMPLETE
-- =============================================================================

-- Next step: Update reprocess_tickets_full_taxonomy.py to accept --phase argument
