## Migrations Inventory

This folder mixes two kinds of SQL artifacts:

1. Historical numbered migrations that reflect the real evolution of `ticket_insights`
2. Consolidated helper migrations used later to add or validate Phase 3 columns

Important notes:
- Do not assume every file here should be executed sequentially on a fresh database
- Some files are historical branch points or corrective follow-ups
- Prefer validating current schema state before running any migration

Practical reading order:
- `002_create_ticket_insights_mvp.sql`
- `003_fix_clinic_id_bigint.sql`
- `003_add_llm_fields.sql`
- `004_add_conversation_summary.sql`
- `004_add_full_conversation.sql`
- `005_fix_root_cause_constraint.sql`
- `006_rename_billing_issue.sql`
- `001_add_metadata_flags_and_natureza_v3.sql`
- `002_add_processing_phase_column.sql`
- `003_natureza_v3_2_contratacao_split.sql`
- `008_drop_legacy_columns.sql`

Consolidated helpers:
- `add_phase3_columns.sql`
- `add_full_taxonomy_columns.sql`
- `validate_003_migration.sql`

Operational rule:
- Query current schema and existing values before executing DDL
- Treat destructive statements like `TRUNCATE TABLE` as historical and high risk
