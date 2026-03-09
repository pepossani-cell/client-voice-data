-- Migration: 004_add_full_conversation
-- Purpose: Add full_conversation field for LLM semantic extraction (Phase 2)
-- Date: 2026-02-10
-- Related: DECISIONS_IN_PROGRESS.md § 19.6 Phase 2

-- Truncate for clean restart with new field
TRUNCATE TABLE ticket_insights CASCADE;

-- Add full_conversation column
ALTER TABLE ticket_insights 
ADD COLUMN full_conversation TEXT;

-- Add index for text search (if needed later)
CREATE INDEX idx_full_conversation_gin ON ticket_insights USING gin(to_tsvector('portuguese', full_conversation));

-- Update comment
COMMENT ON COLUMN ticket_insights.full_conversation IS 'Aggregated: DESCRIPTION + first 5 COMMENTS (max 2K tokens). For LLM semantic extraction in Phase 2.';

-- Success message
SELECT 'Migration 004 applied: full_conversation field added, GIN index created' as status;
