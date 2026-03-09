-- Migration 003: Add LLM Semantic Extraction Fields
-- Phase 3: LLM processing for root cause, sentiment, themes
-- Date: 2026-02-10
-- Cost estimate: $202 for 172K tickets
-- Reference: PHASE_3_LLM_SPECIFICATION.md

-- Add new columns for LLM extraction
ALTER TABLE ticket_insights
ADD COLUMN IF NOT EXISTS root_cause VARCHAR(50),
ADD COLUMN IF NOT EXISTS sentiment INTEGER,
ADD COLUMN IF NOT EXISTS key_themes TEXT[],
ADD COLUMN IF NOT EXISTS llm_confidence FLOAT,
ADD COLUMN IF NOT EXISTS llm_model VARCHAR(50),
ADD COLUMN IF NOT EXISTS llm_processed_at TIMESTAMP;

-- Add constraints
ALTER TABLE ticket_insights
ADD CONSTRAINT check_sentiment_range CHECK (sentiment BETWEEN 1 AND 5),
ADD CONSTRAINT check_confidence_range CHECK (llm_confidence BETWEEN 0.0 AND 1.0),
ADD CONSTRAINT check_root_cause_values CHECK (
    root_cause IN (
        'technical_issue',
        'user_error',
        'product_gap',
        'process_issue',
        'billing_issue',
        'unclear',
        'not_applicable'
    )
);

-- Create indexes for efficient queries

-- Index for filtering unprocessed tickets
CREATE INDEX IF NOT EXISTS idx_llm_unprocessed 
ON ticket_insights(llm_processed_at) 
WHERE llm_processed_at IS NULL;

-- Index for filtering low-confidence tickets
CREATE INDEX IF NOT EXISTS idx_llm_low_confidence 
ON ticket_insights(llm_confidence) 
WHERE llm_confidence < 0.6;

-- Index for root cause analysis
CREATE INDEX IF NOT EXISTS idx_root_cause 
ON ticket_insights(root_cause);

-- Index for sentiment analysis
CREATE INDEX IF NOT EXISTS idx_sentiment 
ON ticket_insights(sentiment);

-- GIN index for key_themes array searches
CREATE INDEX IF NOT EXISTS idx_key_themes 
ON ticket_insights USING GIN(key_themes);

-- Composite index for common queries (root_cause + sentiment)
CREATE INDEX IF NOT EXISTS idx_root_cause_sentiment 
ON ticket_insights(root_cause, sentiment);

-- Comments for documentation
COMMENT ON COLUMN ticket_insights.root_cause IS 'Primary cause of ticket: technical_issue, user_error, product_gap, process_issue, billing_issue, unclear, not_applicable';
COMMENT ON COLUMN ticket_insights.sentiment IS 'Customer sentiment score 1-5 (1=very negative, 5=very positive)';
COMMENT ON COLUMN ticket_insights.key_themes IS 'Array of 1-3 main topics discussed (e.g., ["payment", "access", "bug"])';
COMMENT ON COLUMN ticket_insights.llm_confidence IS 'Model confidence in classification (0.0-1.0). <0.6 triggers validation.';
COMMENT ON COLUMN ticket_insights.llm_model IS 'Model used for extraction: claude-haiku-4.5, gpt-4o-mini, or gemini-2.0-flash';
COMMENT ON COLUMN ticket_insights.llm_processed_at IS 'Timestamp when LLM extraction completed (UTC)';

-- Validation query (run after migration)
-- Verify migration success
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'ticket_insights' 
        AND column_name IN ('root_cause', 'sentiment', 'key_themes', 'llm_confidence', 'llm_model', 'llm_processed_at')
        GROUP BY table_name
        HAVING COUNT(*) = 6
    ) THEN
        RAISE NOTICE '[OK] Migration 003 completed successfully. All 6 columns added.';
    ELSE
        RAISE EXCEPTION '[ERROR] Migration 003 incomplete. Check column creation.';
    END IF;
END $$;
