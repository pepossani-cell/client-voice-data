# CLIENT_VOICE Domain Skills

> **Domain**: CLIENT_VOICE (Voice of Customer)  
> **Project**: client-voice-data  
> **Status**: STRUCTURE_CREATED (skills not yet implemented)  
> **Last Updated**: 2026-02-04

---

## 📋 Planned Skills (Tier 3 - Domain-Specific)

### 1. `@analyze-voc-sentiment`

**Priority**: P1 (implement first)  
**Status**: Not implemented  
**Purpose**: Analyze Voice of Customer sentiment trends and patterns

**Structure**:
```
analyze-voc-sentiment/
├── SKILL.md
├── scripts/
│   └── analyze_sentiment.py
└── references/
    ├── VOC_METRICS.md
    └── CATEGORY_TAXONOMY.md
```

**Effort**: 2-3 days  
**Target**: 2026-02-08

---

### 2. `@correlate-tickets-events`

**Priority**: P2  
**Status**: Not implemented  
**Purpose**: Correlate support tickets with SAAS/FINTECH events (cross-domain)

**Composes**: `@clinic-health-check` (Tier 2)

**Structure**:
```
correlate-tickets-events/
├── SKILL.md
├── scripts/
│   └── correlate_events.py
└── references/
    └── CORRELATION_HEURISTICS.md
```

**Effort**: 3-4 days  
**Target**: 2026-02-12

---

### 3. `@classify-support-issues`

**Priority**: P4 (manual/ad-hoc)  
**Status**: Not implemented  
**Purpose**: LLM-enhanced classification of support tickets

**Structure**:
```
classify-support-issues/
├── SKILL.md
├── scripts/
│   └── classify_tickets.py
└── references/
    ├── LLM_PROMPTS.md
    └── CATEGORY_DEFINITIONS.md
```

**Effort**: 2-3 days  
**Target**: 2026-02-25

---

## 🔗 Relationship to Global Skills

**Uses from Tier 1 (Core)**:
- `@session-start`, `@session-end`, `@debate`, `@curate-memory`

**Uses from Tier 2 (Shared)**:
- `@investigate-entity`, `@clinic-health-check`
- `@eda-workflow` (planned)

**Composition Pattern**:
- `@correlate-tickets-events` → composes `@clinic-health-check` for cross-domain diagnostic

---

## 📚 References

- **Architecture**: `capim-meta-ontology/ARCHITECTURE_PRINCIPLES.md`
- **Skills Playbook**: `capim-meta-ontology/SKILLS_PLAYBOOK.md`
- **Skill Registry**: `capim-meta-ontology/SKILL_REGISTRY.yaml`
- **Analysis**: `capim-meta-ontology/DOMAIN_SKILLS_ANALYSIS.md`
- **Domain Entry**: `_domain/START_HERE.md`

---

## 🚀 Implementation Guide

When ready to implement a skill:

1. **Create skill folder**: `mkdir <skill-name>`
2. **Create SKILL.md** with frontmatter:
   ```yaml
   ---
   name: Skill Name
   description: ... (with triggers)
   version: 1.0
   auto_invoke: ask_first | silent | explicit_only
   ---
   ```
3. **Bundle resources**: Add scripts/, references/, assets/ as needed
4. **Reuse existing scripts**: Link to `scripts/`
5. **Update `.cursorrules`**: Add skill to domain skill listing
6. **Test invocation**: Verify skill discovery and execution
7. **Update SKILL_REGISTRY.yaml**: Change status from "planned" to "active"

---

## 🔄 Integration with client-voice App

**Note**: This project (client-voice-data) contains the **data ontology**.

The **Streamlit app** is in a separate project: `client-voice/` (or `client-voice-app/`)

Skills here focus on **data analysis and ETL**, not UI/dashboard.

---

**Next action**: Implement `@analyze-voc-sentiment` (P1)
