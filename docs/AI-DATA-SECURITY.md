# AI DATA SECURITY

**Phase 23 — AI Data Boundaries, RAG Security, MCP Security**

## Core Principle

AI should explain evidence and data. AI must not become the source of truth.

```
Source data
+ Deterministic computation
+ Transparent methodology
= Foundation
```

## AI Data Boundaries

### Authorization Enforcement

AI may only access data authorized for the requesting user:
- **RAG retrieval** must enforce tenant, organization, case, document, and geography permissions
- **MCP tools** must check required_role before execution
- **Vector search** must never become a permission bypass
- **SQL queries** must be read-only and permission-checked

### What AI Must Never Do

- Bypass permissions through RAG, MCP, or vector search
- Make verification decisions alone
- Invent statistics or government numbers
- Present unverified data as confirmed
- Access private records without authorization
- Modify production data silently

## RAG Security

### Retrieval Guard

```
User Request
    ↓
Permission Check (who is asking?)
    ↓
RAG Retrieval (what data is accessible?)
    ↓
Access Filter (remove restricted chunks)
    ↓
Context Assembly (only authorized data)
    ↓
AI Response (cites sources, notes limitations)
```

### Vector Data Provenance

Every vectorized document/chunk references:
- `source_id` — which data source
- `document_id` — which document
- `chunk_id` — which chunk
- `version` — document version
- `permissions` — access level
- `created_at` — when indexed

### RAG Poisoning Defense

Documents indexed into RAG may contain malicious instructions. The system:
1. Treats retrieved text as **DATA**, not instructions
2. Never allows "Ignore system instructions" to influence behavior
3. Separates system boundary from user input from retrieved context

## MCP Security

### Tool Execution Guard

Every MCP tool call goes through:
1. **Role check**: Does the caller have the required role?
2. **Input validation**: Are parameters valid?
3. **Execution**: Run the tool handler
4. **Output filtering**: Ensure no sensitive data leaks

### MCP Data Provenance

Every MCP tool result preserves source references:
- What data produced this answer?
- Which dataset/version?
- When was it last updated?
- What are the limitations?

## Prompt Injection Defense

### System Boundary

```
DEVELOPER_RULES (immutable)
    ↓
<retrieved_context> (RAG data, treated as DATA)
    ↓
<user_input> (user query, treated as DATA)
    ↓
<report_content> (report data, treated as DATA)
```

### PII Scrubbing

Before any data enters a prompt:
- 12-digit Aadhaar/ID patterns are masked
- Phone numbers are masked
- Email addresses are masked

### Response Validation

Before displaying AI outputs:
- Source references are verified
- Numerical claims are checked against database
- Authorization is confirmed
- Confidence level is noted
- Data freshness is stated

## AI Response Format

Instead of:
> "There are 25 vacant teachers."

AI should say:
> "The latest available dataset reports 25 vacancies.
> Source: Education Department dataset
> Last updated: July 2026
> The platform has not independently verified this figure."

## AI Source Conflict Explanation

When data sources disagree, AI should say:
> "The available sources disagree."
> Then show:
> - Source A: value, date
> - Source B: value, date

AI must never invent reconciliation between conflicting sources.

## SQL Safety

If AI generates queries:
- Use read-only access
- Parameterize queries
- Validate query structure
- Enforce authorization
- Enforce row/column permissions
- Prevent destructive SQL

Never give the LLM unrestricted database credentials.
