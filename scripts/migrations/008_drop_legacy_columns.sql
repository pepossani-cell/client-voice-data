-- Migration 008: Drop legacy Stage 1/2 columns
-- Purpose: Remove stale fields that conflict with Phase 3 taxonomy
-- Date: 2026-02-13
-- Related: taxonomy_circular_dependency_fix decision

-- Drop legacy Stage 1 columns (product classification)
ALTER TABLE ticket_insights DROP COLUMN IF EXISTS product_area_confidence;
ALTER TABLE ticket_insights DROP COLUMN IF EXISTS product_area_keywords;

-- Drop legacy Stage 2 columns (workflow classification)
ALTER TABLE ticket_insights DROP COLUMN IF EXISTS workflow_type;
ALTER TABLE ticket_insights DROP COLUMN IF EXISTS workflow_confidence;
ALTER TABLE ticket_insights DROP COLUMN IF EXISTS workflow_keywords;

-- Verify remaining columns
SELECT 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns
WHERE table_name = 'ticket_insights'
ORDER BY ordinal_position;
