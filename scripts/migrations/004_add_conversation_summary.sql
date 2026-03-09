-- Migration 004: Add conversation_summary field
-- Purpose: Store LLM-generated narrative summary of ticket conversation
-- Date: 2026-02-10

-- Add conversation_summary column
ALTER TABLE ticket_insights
ADD COLUMN conversation_summary TEXT;

-- Add comment
COMMENT ON COLUMN ticket_insights.conversation_summary IS 
'LLM-generated summary (1-3 sentences) describing: (1) problem reported, (2) action taken, (3) outcome. Max 300 chars.';

-- Create index for full-text search on summaries
CREATE INDEX idx_ticket_insights_summary_fts 
ON ticket_insights 
USING gin(to_tsvector('portuguese', conversation_summary));

-- Verify
SELECT 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns
WHERE table_name = 'ticket_insights'
  AND column_name = 'conversation_summary';
