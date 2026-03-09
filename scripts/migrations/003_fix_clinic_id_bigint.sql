-- Migration: 003_fix_clinic_id_bigint
-- Purpose: Change clinic_id from INTEGER to BIGINT (clinic_ids exceed 2B range)
-- Date: 2026-02-10
-- Related: Backfill MVP discovered clinic_ids like 5998080295956 > INTEGER max (2147483647)

-- Truncate existing data
TRUNCATE TABLE ticket_insights CASCADE;

-- Alter clinic_id to BIGINT
ALTER TABLE ticket_insights 
ALTER COLUMN clinic_id TYPE BIGINT;

-- Success message
SELECT 'Migration 003 applied: clinic_id now BIGINT, table truncated' as status;
