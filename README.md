# CLIENT_VOICE Data — Voice of Customer Ontology

> **Domain**: CLIENT_VOICE  
> **Type**: Data Ontology (not application)  
> **Created**: 2026-02-03 (separated from client-voice/)

---

## What is This?

This project contains the **data ontology** for Voice of Customer (VoC) intelligence:
- Entity documentation (Zendesk tickets, comments, users)
- ETL scripts and data sync
- SQL queries for data transformation
- Axioms and validation rules

**This is NOT the application**. For the Streamlit dashboard, see [`client-voice-app/`](../client-voice-app/).

---

## Structure

```
client-voice-data/
├── _domain/
│   ├── _docs/
│   │   ├── ENTITY_INDEX.yaml
│   │   ├── ONTOLOGY_INDEX.yaml
│   │   └── reference/
│   │       ├── ZENDESK_TICKETS_SEMANTIC.md
│   │       ├── ZENDESK_COMMENTS_SEMANTIC.md
│   │       └── ...
│   ├── _governance/
│   └── START_HERE.md
├── queries/
│   └── zendesk/
│       ├── setup_snowflake.sql
│       └── ...
├── scripts/
│   └── sync_zendesk_enhanced_view.py
├── .cursorrules
└── README.md (this file)
```

---

## Quick Start

### 1. Entry Point

**Read first**: `_domain/START_HERE.md`

### 2. Entity Documentation

**Semantic docs**: `_domain/_docs/reference/*_SEMANTIC.md`

Key entities:
- `ZENDESK_TICKETS_SEMANTIC.md` — Support tickets with LLM classification
- `ZENDESK_COMMENTS_SEMANTIC.md` — Ticket comments and threads
- `ZENDESK_USERS_SEMANTIC.md` — User profiles (agents, requesters)

### 3. Data Pipeline

**ETL**: Zendesk → n8n → Snowflake

**Sync script**:
```bash
python scripts/sync_zendesk_enhanced_view.py
```

---

## Integration with Ecosystem

**Registered in**: `capim-meta-ontology/federation/DOMAIN_REGISTRY.yaml`

**Consumed by**: `client-voice-app/` (Streamlit dashboard)

**Cross-domain joins**:
- `TICKETS.clinic_id` → `SAAS.CLINICS` (metadata)
- `TICKETS.clinic_id` → `FINTECH.CLINICS` (BNPL status)

---

## Separation from Application

**Before** (client-voice/):
- Mixed data ontology + Streamlit app in one project
- Violated separation of concerns

**After** (2026-02-03):
- **This project**: Data ontology and ETL
- **client-voice-app/**: Streamlit UI (separate project)

**Benefits**:
- Clear separation data vs presentation
- Independent evolution of ontology and UI
- Aligned with other domain projects (bnpl-funil, ontologia-saas)

---

**See also**: 
- Application: `../client-voice-app/README.md`
- Global rules: `../capim-meta-ontology/.cursorrules`
- Meta-ontology: `../capim-meta-ontology/START_HERE_ECOSYSTEM.md`
