# Architecture Decision: vox_popular as Single Source of Truth

> **Date**: 2026-02-09  
> **Status**: ✅ Decided / historically implemented  
> **Impact**: CRITICAL - Changes all future ticket analysis workflows  
> **Last Reviewed**: 2026-03-09

## Current State Note

This ADR records the architectural decision correctly, but several implementation details below describe an earlier transition plan.

What is true today:
- `vox_popular.ticket_insights` is the operational table in use
- `TICKET_ANALYSIS_V3` is legacy and should not be used for new analysis
- the current semantic contract is based on the 3-axis taxonomy plus LLM variables
- the migration path no longer centers on a planned `zendesk_tickets_classified` table

Use these files for the live contract:
- `../../START_HERE.md`
- `../TAXONOMY_3_AXES.md`
- `../reference/TICKET_INSIGHTS_SEMANTIC.md`
- `../../../docs/reference/TICKET_INSIGHTS.md`

---

## Decision

**All ticket analysis, classification, and enrichment MUST be centralized in `vox_popular` (PostgreSQL RDS).**

---

## Context

### Current State (Before Decision)

- **TICKET_ANALYSIS_V3** (`CAPIM_DATA_DEV.POSSANI_SANDBOX.TICKET_ANALYSIS_V3`) contains:
  - 7,847 tickets (partial population)
  - LLM-enhanced classification (category, sentiment)
  - Legacy storage in Snowflake sandbox

- **Problem**: Data fragmentation
  - Ontology in `vox_popular.ontology_entities` (58 entities)
  - Tickets in `TICKET_ANALYSIS_V3` (Snowflake)
  - Federation queries require dual-source access
  - Agent reasoning cannot access tickets via PG

---

## Rationale

### 1. **Aligns with Hot/Cold Architecture**

From `DECISIONS_ARCHIVE/2026-02_archived_decisions.md`:

```
Hot Layer (PostgreSQL):
- Operational data
- Low latency
- Real-time writes
- Agent-accessible

Cold Layer (Snowflake):
- Analytical data
- Historical data
- Cross-domain joins
```

**Tickets are operational data** → Belong in Hot Layer (PostgreSQL)

### 2. **Enables Real-Time Agent Reasoning**

- Agents can query `vox_popular` directly via `psycopg2`
- No need for Snowflake credentials in agent context
- Faster queries (local RDS vs Snowflake cloud)
- Simplifies federation queries (ontology + tickets in same DB)

### 3. **Consolidates Ontology + Tickets**

**Current vox_popular schema**:
```
ontology_entities (58 entities)
  ├── CLIENT_VOICE entities (6)
  ├── FINTECH entities (29)
  ├── SAAS entities (18)
  └── ECOSYSTEM entities (5)
```

**After decision**:
```
ontology_entities (58 entities)
ticket_insights (operational VoC table)
  ├── 3-axis taxonomy
  ├── LLM semantic extraction
  ├── Cross-domain enrichment hooks
  └── Temporal alignment (ticket_created_at)
```

**Benefit**: Single query for "What are tickets about clinic X?" (no cross-database join)

---

## Consequences

### ✅ Positive

1. **Simplified agent architecture**: No dual-source complexity
2. **Faster queries**: PostgreSQL RDS co-located with agents
3. **Better federation**: Ontology + tickets in same system
4. **Clearer ownership**: Hot layer owned by this project, Cold layer by Data Engineering

### ⚠️ Negative

1. **Migration effort**: required significant backfill from Snowflake to PostgreSQL
2. **Schema evolution**: required convergence toward the current `ticket_insights` contract
3. **ETL complexity**: required transition away from Snowflake-first operational usage

### 🔄 Mitigation

- **Backfill**: Create script to read from Snowflake and write to PostgreSQL (one-time)
- **ETL**: Update n8n workflow to write to PostgreSQL instead of Snowflake
- **Snowflake**: Keep `ZENDESK_TICKETS_RAW` as cold storage (historical, read-only)

---

## Historical Implementation Plan

### Phase 1: Schema Design (historical snapshot)

Earlier transition draft:

```sql
CREATE TABLE zendesk_tickets_classified (
    -- Primary Key
    zendesk_ticket_id BIGINT PRIMARY KEY,
    
    -- Source Data (from ZENDESK_TICKETS_RAW)
    ticket_created_at TIMESTAMP,
    ticket_updated_at TIMESTAMP,
    status VARCHAR(50),
    subject TEXT,
    tags TEXT,
    clinic_id INTEGER,
    requester_id BIGINT,
    assignee_id BIGINT,
    
    -- Stage 1: Product Area
    product_area VARCHAR(50),
    product_area_confidence FLOAT,
    product_area_keywords TEXT[],
    
    -- Stage 2: Workflow Type
    workflow_type VARCHAR(50),
    workflow_confidence FLOAT,
    workflow_keywords TEXT[],
    
    -- Metadata
    classification_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    classification_version VARCHAR(10) DEFAULT 'v1.0'
);

CREATE INDEX idx_ticket_created_at ON zendesk_tickets_classified(ticket_created_at);
CREATE INDEX idx_clinic_id ON zendesk_tickets_classified(clinic_id);
CREATE INDEX idx_product_area ON zendesk_tickets_classified(product_area);
```

### Phase 2: Backfill (historical step)

```python
# scripts/backfill_to_vox_popular.py
1. Read from CAPIM_DATA.CAPIM_ANALYTICS.ZENDESK_TICKETS_RAW (Snowflake)
2. Apply classify_integrated_stage1_stage2.py
3. Write to PostgreSQL operational storage
4. Batch processing: 10K tickets per batch
5. Progress logging + error handling
```

### Phase 3: ETL Update (historical step)

Update n8n workflow (`eQEByyVKRHtD4uBa`):
- Input: Zendesk API (unchanged)
- Classification: LLM + rule-based (unchanged)
- **Output**: PostgreSQL (vox_popular) instead of Snowflake

### Phase 4: Deprecate TICKET_ANALYSIS_V3 (historical step)

- Mark as `@deprecated` in docs
- Add warning to START_HERE.md
- Update all analysis scripts to use `vox_popular`
- Archive TICKET_ANALYSIS_V3 (keep for reference, don't write to it)

---

## Decision Status

| Component | Status | Owner |
|:----------|:-------|:------|
| **Decision documented** | ✅ Done | Agent (2026-02-09) |
| **Decision documented** | ✅ Done | Agent (2026-02-09) |
| **Operational table in PostgreSQL** | ✅ Done | Implemented later in `ticket_insights` |
| **Backfill path** | ✅ Done | Historical execution completed |
| **3-axis taxonomy adoption** | ✅ Done | See current semantic docs |
| **TICKET_ANALYSIS_V3 deprecation** | ✅ Ongoing but effective | Do not use for new analysis |

---

## References

### Decisions
- `_memory/DECISIONS_IN_PROGRESS.md` § 19.0 (Data Layer for Ticket Analysis)
- `_memory/DECISIONS_ARCHIVE/2026-02_archived_decisions.md` § 2.1 (Hot/Cold Architecture)

### Documentation
- `_domain/START_HERE.md` § 2 (Relationship to Ecosystem)
- `docs/AUDIT_VOX_POPULAR_2026-03-09.md`

### Scripts
- `scripts/sync_zendesk_enhanced_view.py` (legacy Snowflake sync - to be replaced)
- `scripts/classify_integrated_stage1_stage2.py` (classifier - to be reused)

---

**Last Updated**: 2026-03-09  
**Decision Owner**: User + Agent  
**Implementation Owner**: Agent (backfill), User (n8n ETL)
