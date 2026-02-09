# SOURCE_ZENDESK_COMMENTS — Semantic Documentation

> **Domain**: CLIENT_VOICE
> **Related Reference**: [SOURCE_ZENDESK_COMMENTS.md](../../../docs/reference/SOURCE_ZENDESK_COMMENTS.md)
> **Last Updated**: 2026-02-02

---

## 1. Business Definition

**What is this entity?**
This entity contains the actual content of the messages exchanged in support tickets. Every time an agent or a user writes something, a new row is created here.

**In one sentence**: The raw historical record of all written communication within Zendesk tickets.

---

## 2. Grain (Business Perspective)

**What does one row represent?**

A single message or note within a ticket thread. A ticket (ZENDESK_TICKET) is composed of multiple comments.

---

## 3. Key Relationships

### Upstream (Dependencies)

| Entity | Relationship | Description |
|:---|:---|:---|
| ZENDESK_TICKETS | Belongs to | Every comment must be part of a ticket |

---

## 4. Common Questions This Answers

- [x] What did the customer actually say?
- [x] How many interactions did it take to solve a specific problem?
- [x] Is the tone of the conversation positive or negative (via NLP)?

---

## 5. Status Semantics

- **Public (TRUE)**: Messages sent to the requester.
- **Private (FALSE)**: Internal notes shared only between agents.

---

## 6. PII & Sensitivity

| Column | Sensitivity | Notes |
|:---|:---|:---|
| BODY_COMMENT | **HIGH** | May contain any kind of sensitive information typed by users (CNPJ, Names, etc.) |

---

## 7. Limitations & Caveats

- **Formatting**: The `BODY_COMMENT` may contain HTML or markdown tags depending on the source channel.
- **Deletions**: If a comment is deleted in Zendesk, its behavior in the data lake depends on the Hevo sync mode (usually soft-deleted or marked).
