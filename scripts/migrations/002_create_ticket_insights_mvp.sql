-- Migration: 002_create_ticket_insights_mvp
-- Purpose: Create ticket_insights table for MVP backfill (Phase 1)
-- Date: 2026-02-09
-- Related: DECISIONS_IN_PROGRESS.md § 19.6, 20.1

-- Drop table if exists (for rerun safety)
DROP TABLE IF EXISTS ticket_insights CASCADE;

-- Create main table (MVP - minimal schema)
CREATE TABLE ticket_insights (
    -- Primary Key
    zendesk_ticket_id BIGINT PRIMARY KEY,
    
    -- Source Data (from ZENDESK_TICKETS_ENHANCED_V1)
    ticket_created_at TIMESTAMP NOT NULL,
    ticket_updated_at TIMESTAMP,
    status VARCHAR(50),
    subject TEXT,
    tags TEXT, -- comma-separated (mantido como string para compatibilidade)
    
    -- Clinic Context (from ENHANCED - 50.3% fill rate)
    clinic_id INTEGER,
    clinic_id_source VARCHAR(20), -- 'org', 'restricted', 'requests', 'none'
    
    -- Assignee Context (from ENHANCED)
    assignee_name VARCHAR(100),
    is_claudinha_assigned BOOLEAN DEFAULT FALSE,
    
    -- Channel (from ENHANCED)
    via_channel VARCHAR(50), -- 'whatsapp', 'api', 'web', 'email'
    
    -- Classification Stage 1: Product Area (scripts já implementados)
    product_area VARCHAR(50), -- POS, BNPL_Cobranca, BNPL_Financiamento, BNPL_Suporte, SaaS_Operacional, SaaS_Billing, Venda, Indeterminado
    product_area_confidence FLOAT CHECK (product_area_confidence >= 0.0 AND product_area_confidence <= 1.0),
    product_area_keywords TEXT[], -- Array de keywords que matcharam
    
    -- Classification Stage 2: Workflow Type (scripts já implementados)
    workflow_type VARCHAR(50), -- Info_L1, Info_L2, Suporte_L1, Suporte_L2, Reclamacao_L1, Reclamacao_L2, Solicitacao_L1, Solicitacao_L2, Transbordo, Indeterminado
    workflow_confidence FLOAT CHECK (workflow_confidence >= 0.0 AND workflow_confidence <= 1.0),
    workflow_keywords TEXT[], -- Array de keywords que matcharam
    
    -- Metadata
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    version VARCHAR(10) DEFAULT 'v1.0_mvp' -- MVP: apenas Stage 1+2, sem LLM
    
    -- Future Phase 2: LLM Semantic Extraction (placeholders comentados)
    -- root_cause VARCHAR(100),
    -- sentiment_score INTEGER,
    -- sentiment_label VARCHAR(20),
    -- key_themes TEXT[],
    -- customer_intent VARCHAR(50),
    -- urgency_level VARCHAR(20)
);

-- Indexes para performance
CREATE INDEX idx_ticket_created_at ON ticket_insights(ticket_created_at DESC);
CREATE INDEX idx_ticket_updated_at ON ticket_insights(ticket_updated_at DESC);
CREATE INDEX idx_clinic_id ON ticket_insights(clinic_id) WHERE clinic_id IS NOT NULL;
CREATE INDEX idx_product_area ON ticket_insights(product_area);
CREATE INDEX idx_workflow_type ON ticket_insights(workflow_type);
CREATE INDEX idx_status ON ticket_insights(status);
CREATE INDEX idx_is_claudinha ON ticket_insights(is_claudinha_assigned) WHERE is_claudinha_assigned = TRUE;
CREATE INDEX idx_via_channel ON ticket_insights(via_channel);

-- Composite indexes para queries comuns
CREATE INDEX idx_created_product ON ticket_insights(ticket_created_at DESC, product_area);
CREATE INDEX idx_created_clinic ON ticket_insights(ticket_created_at DESC, clinic_id) WHERE clinic_id IS NOT NULL;
CREATE INDEX idx_product_workflow ON ticket_insights(product_area, workflow_type);

-- Comments para documentação
COMMENT ON TABLE ticket_insights IS 'MVP: Zendesk tickets with Stage 1+2 classification. Source: ZENDESK_TICKETS_ENHANCED_V1. Phase 2 will add LLM semantic extraction. Phase 3 will add agent enrichment (separate table). Updated: 2026-02-09';
COMMENT ON COLUMN ticket_insights.zendesk_ticket_id IS 'Primary key. Corresponds to ZENDESK_TICKETS_ENHANCED_V1.zendesk_ticket_id';
COMMENT ON COLUMN ticket_insights.clinic_id IS 'From ENHANCED.clinic_id_enhanced (50.3% fill rate, best available)';
COMMENT ON COLUMN ticket_insights.clinic_id_source IS 'Provenance: org (37.8%), requests (8.6%), restricted (4.0%), none (49.7%)';
COMMENT ON COLUMN ticket_insights.is_claudinha_assigned IS 'Deterministic flag: assignee_id = 19753766791956. 19% of tickets are bot-handled.';
COMMENT ON COLUMN ticket_insights.product_area IS 'Stage 1 classification. 8 categories. 67.8% coverage (Indeterminado 32.2%). Top 200 keywords validated (81% high-confidence).';
COMMENT ON COLUMN ticket_insights.workflow_type IS 'Stage 2 classification. 9 categories. 36.1% coverage (Indeterminado 63.9%). Heuristic rules based on keyword patterns.';
COMMENT ON COLUMN ticket_insights.version IS 'v1.0_mvp = MVP backfill (Stage 1+2 only). v1.1 will add LLM fields. v2.0 will add agent enrichment.';

-- Success message
SELECT '[OK] Migration 002 applied successfully! Table ticket_insights created.' as status;
SELECT 'Next step: Run backfill_tickets_mvp.py to populate from Snowflake' as next_action;
