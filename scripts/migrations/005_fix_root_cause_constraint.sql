-- Migration 005: Fix root_cause constraint to include all taxonomy values
-- Problem: Migration 003 only included 7 values, but prompt uses 10
-- Date: 2026-02-10

-- Drop old constraint
ALTER TABLE ticket_insights
DROP CONSTRAINT IF EXISTS check_root_cause_values;

-- Recreate with ALL taxonomy values
ALTER TABLE ticket_insights
ADD CONSTRAINT check_root_cause_values CHECK (
    root_cause IN (
        'billing_issue',
        'credit_issue',           -- ADDED
        'process_issue',
        'product_gap',
        'user_error',
        'subscription_issue',     -- ADDED
        'operational_issue',      -- ADDED
        'technical_issue',
        'unclear',
        'not_applicable'
    )
);

-- Update comment
COMMENT ON COLUMN ticket_insights.root_cause IS 'Primary cause of ticket: billing_issue, credit_issue, process_issue, product_gap, user_error, subscription_issue, operational_issue, technical_issue, unclear, not_applicable';

-- Verify
DO $$
BEGIN
    RAISE NOTICE '[OK] Migration 005 completed. root_cause constraint updated with 10 values.';
END $$;
