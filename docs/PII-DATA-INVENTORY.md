# PII Data Inventory, Retention & Deletion

**Status:** Live (Step 8 hardening)
**Applies to:** Theek Karo platform (API, DB, Redis, object storage, AI pipeline)
**Legal alignment:** India DPDP Act 2023 + IT Rules (see COMPLIANCE-DPDP.md)

This document is the authoritative inventory of personal data held by the
platform: what is collected, where it lives, how long it is kept, and how it is
deleted. Enforcement of the retention windows is automated by the daily worker
job `tk_worker.purge_expired_pii` (implementation: `services/api/src/tk_api/core/retention.py`).

---

## 1. Principles

- **Civic data is retained; personal data is minimized.** Reports, evidence,
  comments, resolutions and analytics are public-interest data held
  indefinitely, but always with **attribution stripped or anonymized** when the
  author exercises deletion.
- **Deletion means anonymization.** Account deletion anonymizes the user row
  immediately (PII → NULL, `status = "deleted"`, `deleted_at` set). The
  anonymized row is kept permanently as a **tombstone** for referential
  integrity: reports/comments reference `users.id` with mixed
  CASCADE/RESTRICT foreign keys, and hard-deleting the row would either destroy
  civic content or be blocked.
- **Time-limited PII is hard-deleted** by the retention job after its window.
- **No telemetry of sensitive content.** AI payloads are PII-insulated
  (ADR-019); analytics are aggregate.

---

## 2. PII Inventory by Domain

### 2.1 Identity & Authentication

| Table | PII fields | Sensitivity | Purpose | Retention | Deletion behavior |
|---|---|---|---|---|---|
| `users` | phone, email, username, password_hash, display_name, bio, profile_image_url, location_pref, locale, trust_score, status, deleted_at | High | Account + identity | Indefinite (tombstone) | `delete_account` nulls all PII immediately, sets `status="deleted"`; row retained anonymized |
| `user_roles` | user_id → role | Medium | Authorization | Indefinite | Cascade with tombstone (roles become meaningless on anonymized row) |
| `sessions` | user_id, client_id, ip, user_agent, last_seen_at, revoked_at | High | Session management | **180 days** (revoked or inactive) | Hard delete by retention job |
| `refresh_tokens` | user_id, token_hash, family_id, expires_at, revoked_at | High | Refresh-token rotation (ADR-008) | **90 days** past expiry/revocation | Hard delete by retention job |
| `email_verifications` | user_id, email, code_hash, expires_at | High | Email verification | **30 days** past expiry | Hard delete by retention job |
| `password_reset_tokens` | user_id, token_hash, expires_at | High | Password reset | **30 days** past expiry | Hard delete by retention job |
| `user_mfa` | user_id, secret (TOTP), enabled_at | High | MFA (Phase 16) | Indefinite while account active | Deleted on account deletion |
| `oauth_accounts` | user_id, provider, provider ids | High | OAuth login | Indefinite while account active | Deleted on account deletion |
| `devices` | user_id, device metadata | Medium | Push targeting | Indefinite while account active | Revoked/removed on account deletion |
| `consents` | user_id, terms_version, consent flags, timestamps | Medium | Consent evidence (DPDP §6) | **Indefinite** (regulatory evidence) | Never deleted; user_id set NULL on tombstone where schema allows |
| `security_events` | user_id, event, ip, user_agent, meta | High | Forensic review | **365 days** | Hard delete by retention job |
| `audit_logs` | actor_id, action, entity, before/after JSON, ip, user_agent | High | Write-once audit trail (DPDP §8) | **Indefinite** | Never purged; review actions may redact JSON in place |
| `user_mfa` / `login_throttle` (Redis) | phone/account keys, counters | Medium | Login backoff (Phase 16) | TTL-scoped (Redis `EX`) | Auto-expire |

### 2.2 Civic Content (user-authored)

| Table | PII fields | Sensitivity | Purpose | Retention | Deletion behavior |
|---|---|---|---|---|---|
| `reports` | reporter_id, title, description, address_hint, location, private fields | High | Core civic records | **Indefinite** | Content retained (public interest); `reporter_id` keeps the anonymized tombstone reference. `address_hint` masked on request (DPDP §) |
| `report_evidence` / `report_media` | uploader_id, object_key, media metadata | High | Evidence | **Indefinite** (civic) | Retained; media objects deleted on evidence delete (owner flow) |
| `report_comments`, `posts` | author_id, body | Medium | Discussion | **Indefinite** | Retained; author resolves to tombstone. Body redacted on moderation action |
| `content_translations` | author/target refs, text | Medium | Localization | **Indefinite** | Retained with content |
| `case_responses`, `case_actions`, `case_escalations`, `case_status_history`, `case_assignments`, `case_reopen_requests` | actor/user refs, notes | Medium | Department workflow | **Indefinite** (public record) | Retained; actor refs → tombstone |
| `resolution_submissions`, `resolution_evidence`, `resolution_reviews`, `resolution_verifications`, `resolution_disputes` | submitter/reviewer refs, notes | Medium | Resolution workflow | **Indefinite** | Retained; refs → tombstone |
| `report_verifications` | verifier refs | Low | Verification | **Indefinite** | Retained |

### 2.3 Community Layer (Phase 18)

| Table | PII fields | Sensitivity | Purpose | Retention | Deletion behavior |
|---|---|---|---|---|---|
| `user_follows`, `category_followers`, `geography_followers`, `institution_followers`, `report_followers`, `initiative_followers`, `subscriptions` | follower/followee refs | Low | Personalization | **Indefinite** | Rows kept; refs → tombstone (no PII itself) |
| `reactions`, `bookmarks`, `saved_research_queries` | user refs, target refs | Low | Engagement | **Indefinite** | Rows kept; refs → tombstone |
| `civic_initiatives` | organizer_id, description | Medium | Initiatives | **Indefinite** | Retained; organizer ref → tombstone |
| `initiative_members`, `initiative_observations` | user refs, observation text/evidence | Medium | Participation | **Indefinite** | Retained; refs → tombstone |
| `community_groups`, `group_members` | owner/moderator/member refs | Medium | Groups | **Indefinite** | Retained; refs → tombstone |
| `volunteer_profiles` | user_id, languages, interests, categories, areas, skills, availability | Medium | Volunteer matching | **Indefinite** while active | No phone/address/exact-location columns exist (by design); cleared on account deletion |
| `volunteer_opportunities`, `volunteer_signups` | organizer refs, signup refs | Medium | Volunteering | **Indefinite** | Retained; refs → tombstone |
| `user_badges`, `reputation_events` | user refs, event metadata | Low | Recognition | **Indefinite** | Retained; refs → tombstone |
| `user_blocks` | blocker/blocked refs | Medium | Safety | **Indefinite** | Retained; refs → tombstone |
| `content_reports`, `moderation_cases`, `moderation_actions`, `moderation_appeals`, `moderation_decisions` | reporter/moderator refs, reasons | High | Moderation | **Indefinite** (safety record) | Retained; personal details redacted on request; never public |

### 2.4 Notifications

| Table | PII fields | Sensitivity | Purpose | Retention | Deletion behavior |
|---|---|---|---|---|---|
| `notifications`, `notification_queue`, `notification_receipts` | user refs, delivery metadata | Medium | Notifications | **Indefinite** (delivery record) | Retained; refs → tombstone |
| `notification_preferences` | user refs, channel prefs | Low | Preference | **Indefinite** | Retained; refs → tombstone |

### 2.5 AI Pipeline

| Table | PII fields | Sensitivity | Purpose | Retention | Deletion behavior |
|---|---|---|---|---|---|
| `ai_conversations`, `ai_messages` | user_id, prompt/response text (may contain personal context) | High | AI assistant (Phase 17) | **90 days** since last activity | Hard delete by retention job (messages cascade) |
| `ai_runs`, `ai_outputs`, `ai_annotations`, `ai_citations` | report refs, analysis text | Medium | AI analysis | **Indefinite** (civic record) | Retained; payloads PII-insulated (ADR-019) |
| `ai_feedback`, `ai_evaluations`, `ai_reviews` | user refs, feedback text | Medium | Quality | **90 days** | Retained with conversation retention; user refs → tombstone |

### 2.6 Public Data & Exports

| Table | PII fields | Sensitivity | Purpose | Retention | Deletion behavior |
|---|---|---|---|---|---|
| `data_export_jobs` | requester refs, export params | Medium | Public-data exports | **90 days** past completion | Job files deleted; row retained |
| `public_api_keys` | owner refs, key hash | High | API access | Indefinite while active | Revoked on account deletion |
| `public_api_usage` | key refs, ip | Medium | Usage accounting | **365 days** | Hard delete by retention job (extend window if billing/abuse needs longer) |
| `gov_raw_payloads` | imported raw rows (may embed contact details) | High | Import audit | **Indefinite** (import provenance) | Retained; quarantined from public API (Phase 15) |
| `gov_dataset_records` | public dataset rows | Low–Medium | Open data | **Indefinite** | Public by design; review before publishing |

### 2.7 Reference / no-PII tables

Categories, geography, institutions, departments, roles/permissions, SLA
policies, badges, notification templates, data sources, RAG documents (reviewed
corpus), measurement snapshots, analytics rollups: **no personal data** (may
carry user-ID aggregates only). Retained indefinitely as reference data.

---

## 3. Retention Policy Summary

| Data class | Window | Enforced by |
|---|---|---|
| Refresh tokens | 90 d | `purge_expired_pii` (daily) |
| Sessions | 180 d | `purge_expired_pii` (daily) |
| Email verifications | 30 d | `purge_expired_pii` (daily) |
| Password reset tokens | 30 d | `purge_expired_pii` (daily) |
| Security events | 365 d | `purge_expired_pii` (daily) |
| AI conversations + messages | 90 d | `purge_expired_pii` (daily) |
| Public API usage | 365 d | `purge_expired_pii` (daily) |
| OTP codes / login throttle (Redis) | TTL (60–300 s) | Redis `EX` |
| Audit logs | Indefinite (write-once) | Manual redaction only |
| Consents | Indefinite (evidence) | Never deleted |
| Civic content (reports, evidence, comments, cases, resolutions) | Indefinite | Retention by design |
| Anonymized account tombstones | Indefinite | Retention by design |

Constants live in `services/api/src/tk_api/core/retention.py`; keep this table
in sync when they change.

---

## 4. Deletion Workflow

### 4.1 Account deletion (right to erasure, DPDP §)

1. Authenticated user calls `DELETE /api/v1/auth/me` (or via profile settings).
2. `auth/service.delete_account` (implementation) immediately:
   - Nulls all PII on `users` (phone, email, username, password_hash, bio,
     profile_image_url, location_pref); sets `display_name = "Anonymous
     Citizen"`, `status = "deleted"`, `deleted_at = now`.
   - Revokes every session + refresh token.
   - Deletes OAuth links and MFA state.
   - Records a `SECURITY_EVENT` and an audit entry.
3. Civic content authored by the user is **retained** (public interest) and its
   `user_id` now points at the anonymized tombstone — the identity is gone, the
   record remains.
4. Volunteer profiles, notification preferences and saved items retain their
   rows; their `user_id` references become inert tombstone refs.

### 4.2 Content-level deletion

- Evidence/media: owner or moderator deletes via the reports media endpoints;
  the object is removed from storage and the row marked deleted.
- Comments/posts: moderation removal hides the content; full body redaction on
  high-impact actions.
- Reports: never hard-deleted (public record); visibility can be set to
  private, and PII-bearing `address_hint` fields masked on request.

### 4.3 Automated purge (daily)

`tk_worker.purge_expired_pii` runs every 24 h and hard-deletes every row past
its retention window (see §3). It is idempotent, reports per-table counts, and
is unit-tested (`tests/test_retention_purge.py`).

---

## 5. Known Gaps / Open Items

- Audit-log redaction tooling (manual today) — automate when a DPO is
  appointed.
- `devices` rows for deleted accounts are revoked, not purged; a tombstone
  cleanup pass can be added once push volumes are known.
- Consent evidence is intentionally never deleted; counsel confirmed this is
  the DPDP §6 position (COMPLIANCE-DPDP.md).
