-- Migration: Add columns for full 3-axis taxonomy
-- Date: 2026-02-13
-- Phase 3: Full Taxonomy Reprocessing

-- PRODUTO L2 (subcategory)
-- Values: Cobranca, Servicing, Originacao (BNPL) | Clinico, Conta, Lifecycle (SaaS) | NULL (others)
ALTER TABLE ticket_insights
ADD COLUMN IF NOT EXISTS product_area_l2 VARCHAR(50);

COMMENT ON COLUMN ticket_insights.product_area_l2 IS 
    'Product subcategory (L2). BNPL: Cobranca/Servicing/Originacao. SaaS: Clinico/Conta/Lifecycle';

-- ATENDIMENTO (service_type)
-- Values: Bot_Resolvido, Bot_Escalado, Escalacao_Solicitada, Humano_Direto
ALTER TABLE ticket_insights
ADD COLUMN IF NOT EXISTS service_type VARCHAR(30);

COMMENT ON COLUMN ticket_insights.service_type IS 
    'Service handling type: Bot_Resolvido, Bot_Escalado, Escalacao_Solicitada, Humano_Direto';

-- Add constraint for service_type
ALTER TABLE ticket_insights
ADD CONSTRAINT check_service_type
    CHECK (service_type IS NULL OR service_type IN ('Bot_Resolvido', 'Bot_Escalado', 'Escalacao_Solicitada', 'Humano_Direto'));

-- Create index for common queries
CREATE INDEX IF NOT EXISTS idx_ticket_insights_product_area_l2 
    ON ticket_insights(product_area, product_area_l2);

CREATE INDEX IF NOT EXISTS idx_ticket_insights_service_type 
    ON ticket_insights(service_type);

-- Combined index for cross-dimensional queries
CREATE INDEX IF NOT EXISTS idx_ticket_insights_full_taxonomy 
    ON ticket_insights(product_area, root_cause, service_type);
