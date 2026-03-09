-- Migration: Add Phase 3 LLM columns to ticket_insights
-- Decision: 20.7a (DECISIONS_IN_PROGRESS.md)
-- Date: 2026-02-12
-- 
-- Phase 2 → Phase 3 changes:
-- - root_cause: KEEP (15 canonical values, updated taxonomy)
-- - sentiment: KEEP (1-5 scale, unchanged)
-- - key_themes: KEEP (ARRAY, but vocabulary optimized to 45 terms)
-- - conversation_summary: KEEP (but max 200 chars in Phase 3, was 300)
-- - llm_confidence: KEEP (0.0-1.0, unchanged)
-- - customer_effort_score: NEW (1-7 scale)
-- - frustration_detected: NEW (boolean)
-- - churn_risk_flag: NEW (enum: LOW/MEDIUM/HIGH)

BEGIN;

-- Add new Phase 3 columns
ALTER TABLE ticket_insights
ADD COLUMN IF NOT EXISTS customer_effort_score INTEGER,
ADD COLUMN IF NOT EXISTS frustration_detected BOOLEAN,
ADD COLUMN IF NOT EXISTS churn_risk_flag VARCHAR(10);

-- Add constraints
ALTER TABLE ticket_insights
ADD CONSTRAINT check_customer_effort_score 
    CHECK (customer_effort_score IS NULL OR (customer_effort_score >= 1 AND customer_effort_score <= 7));

ALTER TABLE ticket_insights
ADD CONSTRAINT check_churn_risk_flag 
    CHECK (churn_risk_flag IS NULL OR churn_risk_flag IN ('LOW', 'MEDIUM', 'HIGH'));

-- Add comments
COMMENT ON COLUMN ticket_insights.customer_effort_score IS 
    'Phase 3: Customer effort to resolve issue (1=minimal, 7=extreme). Decision 20.7a.';

COMMENT ON COLUMN ticket_insights.frustration_detected IS 
    'Phase 3: Explicit frustration signals detected (capslock, negative keywords). Decision 20.7a.';

COMMENT ON COLUMN ticket_insights.churn_risk_flag IS 
    'Phase 3: Churn risk assessment (LOW/MEDIUM/HIGH). Decision 20.7a.';

-- Update version column for Phase 3 records
COMMENT ON COLUMN ticket_insights.version IS 
    'LLM processing version: v2 (Phase 2: 2-tier), v3 (Phase 3: 3-tier with new fields)';

COMMIT;

-- Verify migration
SELECT 
    column_name,
    data_type,
    character_maximum_length,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'ticket_insights'
AND column_name IN ('customer_effort_score', 'frustration_detected', 'churn_risk_flag')
ORDER BY ordinal_position;
