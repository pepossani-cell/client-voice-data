# Data Dictionaries — CLIENT_VOICE

> **Purpose**: Technical documentation (schema, columns, data types) for domain entities.  
> **Location**: `docs/reference/`  
> **Related**: Semantic docs in `_domain/_docs/reference/*_SEMANTIC.md`

---

## Documentation Standard

### Data Dictionary (`*.md` — this folder)
- **Focus**: Technical/schema details
- **Content**: Column names, data types, nullability, FK references
- **Audience**: Developers, data engineers

### Semantic Doc (`*_SEMANTIC.md` — `_domain/_docs/reference/`)
- **Focus**: Business context
- **Content**: What the entity represents, business rules, relationships
- **Audience**: Analysts, product managers, AI agents

---

## Entity Index

| Entity | Data Dictionary | Semantic Doc |
|:-------|:----------------|:-------------|
| ZENDESK_TICKETS | [ZENDESK_TICKETS.md](./ZENDESK_TICKETS.md) | [ZENDESK_TICKETS_SEMANTIC.md](../../_domain/_docs/reference/ZENDESK_TICKETS_SEMANTIC.md) |
| ZENDESK_USERS | [ZENDESK_USERS.md](./ZENDESK_USERS.md) | [ZENDESK_USERS_SEMANTIC.md](../../_domain/_docs/reference/ZENDESK_USERS_SEMANTIC.md) |
| ZENDESK_TICKETS_ENHANCED | [ZENDESK_TICKETS_ENHANCED.md](./ZENDESK_TICKETS_ENHANCED.md) | [ZENDESK_TICKETS_ENHANCED_SEMANTIC.md](../../_domain/_docs/reference/ZENDESK_TICKETS_ENHANCED_SEMANTIC.md) |
| SOURCE_ZENDESK_COMMENTS | [SOURCE_ZENDESK_COMMENTS.md](./SOURCE_ZENDESK_COMMENTS.md) | [SOURCE_ZENDESK_COMMENTS_SEMANTIC.md](../../_domain/_docs/reference/SOURCE_ZENDESK_COMMENTS_SEMANTIC.md) |

---

**Standard**: Based on `bnpl-funil/docs/reference/` structure.
