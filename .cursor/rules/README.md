# Cursor Rules - client-voice-data

> **Local copies** for project autonomy (multi-repo setup)  
> **Forked from**: capim-meta-ontology/.cursor/rules/  
> **Date**: 2026-02-04

---

## Rules in This Project

| Rule | Source | Status | Customizable |
|------|--------|--------|--------------|
| **snowflake_data.mdc** | capim-meta-ontology | ✅ Local copy | Yes |
| **workspace_hygiene.mdc** | capim-meta-ontology | ✅ Local copy | Yes |

---

## Autonomy Model

These rules are **local copies** to enable project autonomy:
- ✅ No external dependencies
- ✅ Team can customize if needed
- ⚠️ Updates NOT automatic (intentional trade-off)

---

## Global Rules (Still Shared)

These rules remain in capim-meta-ontology (cross-project):
- `memory_governance.mdc` — Decision tracking protocol
- `ontology_reasoning.mdc` — Cross-domain reasoning
- `agent_protocol.mdc` — General agent behavior

**Why shared?** Organizational standards that benefit from consistency.

---

## Customization

**To customize a local rule**:
1. Edit the `.mdc` file directly
2. Document changes in header comment
3. Consider if change should be upstreamed to master

**To sync with master** (optional):
```bash
cp ../capim-meta-ontology/.cursor/rules/snowflake_data.mdc .cursor/rules/
```

---

**Last Updated**: 2026-02-04

