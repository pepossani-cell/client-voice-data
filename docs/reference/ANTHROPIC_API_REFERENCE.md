# Anthropic Claude API — Reference

> **Purpose**: Persistent reference for Anthropic Claude API details relevant to the CLIENT_VOICE pipeline.  
> **Status**: Living document — updated when model availability changes.  
> **Last Updated**: 2026-02-13  
> **Last Validated**: 2026-02-13 (empirical test of all model endpoints)

---

## 1. Available Models (Validated 2026-02-13)

### Current Generation

| Model | API Identifier (Alias) | Specific Version | Status | Notes |
|-------|------------------------|------------------|--------|-------|
| **Opus 4.6** | `claude-opus-4-6` | — | ✅ Available | Latest Opus. Best quality. |
| **Opus 4.5** | `claude-opus-4-5` | — | ✅ Available | Previous gen Opus. |
| Opus 4 | — | `claude-opus-4-20250514` | ✅ Available | Alias `claude-opus-4` NOT FOUND. |
| **Sonnet 4.5** | `claude-sonnet-4-5` | — | ✅ Available | Latest Sonnet. Best cost/quality ratio. |
| Sonnet 4 | — | `claude-sonnet-4-20250514` | ✅ Available | Alias `claude-sonnet-4` NOT FOUND. |
| **Haiku 4.5** | `claude-haiku-4-5` | `claude-haiku-4-5-20251001` | ✅ Available | Latest Haiku. Note: date is `20251001`. |
| Haiku 3.5 | — | `claude-3-5-haiku-20241022` | ⚠️ Deprecated | EOL: 2026-02-19. **DO NOT USE.** |
| Haiku 3 | — | `claude-3-haiku-20240307` | ✅ Available | Legacy, still functional. |

### NOT Available (404 errors)

| Model Identifier | Why |
|------------------|-----|
| `claude-opus-4-latest` | Alias format not supported for Opus |
| `claude-sonnet-4-latest` | Alias format not supported for Sonnet |
| `claude-3-5-sonnet-latest` | Alias format not supported |
| `claude-opus-4` | Short alias not recognized (need version date or full alias) |
| `claude-sonnet-4` | Short alias not recognized |
| `claude-haiku-4-20250514` | Wrong date for Haiku 4 (doesn't exist) |
| `claude-haiku-4-5-20250514` | Wrong date for Haiku 4.5 (correct is `20251001`) |
| `claude-3-5-sonnet-20241022` | Fully deprecated |

---

## 2. Naming Convention & Gotchas

### Pattern

```
claude-{family}-{major}-{minor?}-{date?}
```

Examples:
- `claude-opus-4-6` → Opus family, version 4.6 (alias, resolves to latest build)
- `claude-opus-4-20250514` → Opus 4, specific build from May 14, 2025
- `claude-haiku-4-5-20251001` → Haiku 4.5, specific build from Oct 1, 2025

### ⚠️ Critical Gotchas

1. **Dates vary by model family**: Opus 4 is `20250514`, Haiku 4.5 is `20251001`. **Never assume same date** across families.
2. **Aliases without dates are preferred**: `claude-opus-4-6` will auto-resolve to the latest build. Version-pinned identifiers (`-20250514`) lock to a specific build.
3. **`-latest` suffix doesn't work** for Opus/Sonnet as of 2026-02-13. Only works for Haiku 3.5 (`claude-3-5-haiku-latest`).
4. **Short aliases sometimes fail**: `claude-opus-4` → NOT FOUND, but `claude-opus-4-20250514` → OK. Use the full family alias (`claude-opus-4-6`) instead.
5. **Deprecation warnings appear as Python DeprecationWarning**, not as API errors. A deprecated model may still work but will stop on EOL date.

### Recommendation

**Always use aliases without date** for production pipelines:
```python
TIER_MODELS = {
    'T1': 'claude-opus-4-6',     # Auto-resolves to latest Opus 4.6 build
    'T2': 'claude-sonnet-4-5',   # Auto-resolves to latest Sonnet 4.5 build
    'T3': 'claude-haiku-4-5',    # Auto-resolves to latest Haiku 4.5 build
}
```

---

## 3. Pricing (Standard API)

### Per Million Tokens

| Model | Input $/1M | Output $/1M | Notes |
|-------|-----------|-------------|-------|
| Opus 4.6 | $5.00 | $25.00 | |
| Opus 4.5 | $5.00 | $25.00 | |
| Opus 4.1 | $15.00 | $75.00 | Legacy, more expensive |
| Opus 4 | $15.00 | $75.00 | Legacy, more expensive |
| Sonnet 4.5 | $3.00 | $15.00 | |
| Sonnet 4 | $3.00 | $15.00 | |
| Haiku 4.5 | $1.00 | $5.00 | |
| Haiku 3.5 | $0.80 | $4.00 | Deprecated 2026-02-19 |
| Haiku 3 | $0.25 | $1.25 | |

> **Note**: Opus 4.6/4.5 are significantly cheaper than Opus 4/4.1 ($5 vs $15 input). This is a **67% price drop** for better quality.

---

## 4. Message Batches API (50% Discount)

### Overview

The Message Batches API enables asynchronous batch processing of large request volumes at **50% off standard pricing**.

- **Endpoint**: `POST https://api.anthropic.com/v1/messages/batches`
- **SDK**: `client.messages.batches.create(requests=[...])`
- **GA since**: December 17, 2024

### Batch Pricing (50% off)

| Model | Batch Input $/1M | Batch Output $/1M | Savings vs Sync |
|-------|-----------------|-------------------|-----------------|
| **Opus 4.6** | $2.50 | $12.50 | 50% |
| **Opus 4.5** | $2.50 | $12.50 | 50% |
| Opus 4.1 | $7.50 | $37.50 | 50% |
| **Sonnet 4.5** | $1.50 | $7.50 | 50% |
| Sonnet 4 | $1.50 | $7.50 | 50% |
| **Haiku 4.5** | $0.50 | $2.50 | 50% |
| Haiku 3.5 | $0.40 | $2.00 | 50% |
| Haiku 3 | $0.125 | $0.625 | 50% |

### Batch API Limits & Characteristics

| Parameter | Value |
|-----------|-------|
| Max requests per batch | 100,000 |
| Max batch size | 256 MB |
| Typical processing time | < 1 hour |
| Guaranteed max processing | 24 hours |
| Results availability | 29 days from creation |
| Rate limits | Separate from standard API |
| Prompt caching compatible | ✅ Yes (discounts stack) |

### Usage Pattern

```python
import anthropic

client = anthropic.Anthropic()

# 1. Create batch
batch = client.messages.batches.create(
    requests=[
        {
            "custom_id": f"ticket-{ticket_id}",
            "params": {
                "model": "claude-sonnet-4-5",
                "max_tokens": 1024,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
        }
        for ticket_id, prompt in ticket_prompts.items()
    ]
)

# 2. Poll for completion
import time
while True:
    batch = client.messages.batches.retrieve(batch.id)
    if batch.processing_status == "ended":
        break
    time.sleep(60)

# 3. Stream results
for result in client.messages.batches.results(batch.id):
    if result.result.type == "succeeded":
        message = result.result.message
        # Process message.content
```

### Result Types

| Type | Description | Billed? |
|------|-------------|---------|
| `succeeded` | Request completed successfully | ✅ Yes |
| `errored` | Invalid request or server error | ❌ No |
| `canceled` | Batch was canceled before processing | ❌ No |
| `expired` | 24h timeout reached before processing | ❌ No |

### Best Practices for Batching

1. **Use meaningful `custom_id`**: e.g. `ticket-{zendesk_ticket_id}` for easy result matching
2. **Results are NOT ordered**: Match by `custom_id`, not by position
3. **Break large datasets**: 171K tickets → 2 batches of 85.5K each (under 100K limit)
4. **Prompt caching**: Use `cache_control` blocks for shared system prompts (30-98% cache hit rate)
5. **Dry-run first**: Test single request shape with standard Messages API before batching
6. **Monitor via Console**: Batches visible at `console.anthropic.com` under workspace

---

## 5. Prompt Caching (Stackable with Batch)

### Overview

Prompt caching reduces cost for repeated prefixes (e.g., system prompt + taxonomy).

| Model | Cache Write $/1M | Cache Read $/1M | Savings vs Standard |
|-------|-----------------|-----------------|---------------------|
| Opus 4.6 | $6.25 | $0.50 | 90% on reads |
| Sonnet 4.5 | $3.75 | $0.30 | 90% on reads |
| Haiku 4.5 | $1.25 | $0.10 | 90% on reads |

**Cache TTL**: 5 minutes (standard) or **1 hour** (for batch processing)

**Relevance for our pipeline**: System prompt (~500 tokens) + taxonomy (~200 tokens) are identical across all tickets. With batching, cache hit rate is typically 30-98%.

---

## 6. SDK Version

```
anthropic==0.79.0  (validated 2026-02-13)
```

Required in `requirements.txt`. Breaking changes possible between major versions.

---

## 7. Environment Setup

```bash
# Required env var
ANTHROPIC_API_KEY=sk-ant-api...

# Optional
ANTHROPIC_BASE_URL=https://api.anthropic.com  # default
```

Stored in `client-voice-data/.env` (gitignored). Template: `.env.example`.

---

## 8. Changelog

| Date | Change | Decision |
|------|--------|----------|
| 2026-02-12 | Initial model selection: Opus 4.6, Sonnet 4.5, Haiku 4.5 | 20.7b-d |
| 2026-02-13 | Discovered wrong model versions (`claude-opus-4-20250514` → `claude-opus-4-6`). Updated to latest aliases. | 20.7g |
| 2026-02-13 | Confirmed Batch API availability (50% discount). Revised budget from $263-311 → $132-156. | 20.7h |
| 2026-02-13 | Empirically validated all model endpoints. Documented NOT FOUND patterns. | 20.7g |

---

**END OF DOCUMENT**
