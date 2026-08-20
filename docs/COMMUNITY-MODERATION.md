# Theek Karo — Community Moderation (Phase 18)

## Overview

Moderation combines deterministic automated safety checks with AI assistance
and human review. AI **recommends**; human moderators decide significant
actions. AI never permanently bans users autonomously.

```
User Report / Automated Signal
  → Automated safety checks
  → AI recommendation where useful
  → Rule evaluation
  → Moderator queue
  → Review
  → Action
  → Appeal
```

## Automated safety checks

Deterministic, rule-based checks run on every contribution:

- **Rate limits** — separate limits for reports, comments, reactions, follows,
  group creation and initiatives (IP + account based).
- **Duplicate detection** — repeated posts and repetitive comments.
- **Link safety** — user-generated links are treated as untrusted; no
  dangerous redirects.
- **Anti-brigading signals** — sudden mass reactions, coordinated duplicate
  comments, repeated reports. Flagged for review; legitimate collective
  participation is never auto-deleted.

## AI assistance

AI may:

- Summarize a discussion thread.
- Flag likely-problematic content for review.
- Recommend a proportionate action.

AI must not:

- Permanently ban or suspend users autonomously.
- Declare content true/false without evidence.
- Suppress legitimate participation.

## Human review

Moderators review flagged content and user reports. Actions available:

```
Warning
Content removal
Temporary restriction
Comment restriction
Group restriction
Account suspension
```

Actions are proportionate and case-by-case.

## Moderation queue API

- `GET /api/v1/community/moderation/queue` — open content reports (moderators).
- `POST /api/v1/community/moderation/queue/{item_id}` — dismiss or action.

## Group moderation

- Groups have Owner / Moderator / Member roles.
- Platform safety rules always override group rules.
- Group moderators may manage members (add, remove, ban, promote, demote) but
  cannot override platform decisions.
- Groups used for harassment, doxxing, threats, misinformation, political
  persuasion or coordinated abuse are archived by platform moderators.

## Initiative moderation

- Initiatives follow: Draft → Submitted → Review → Approved → Active →
  Completed → Archived.
- Public initiatives require moderator approval before they become visible.
- Observation evidence is reviewed by organizers/moderators before acceptance.

## User reporting

Users can report comments and users:

```
Harassment
Spam
Impersonation
Threats
Doxxing
Abuse
False information
Personal information exposure
```

## Appeals

```
Action → Appeal → Review → Decision → Notification
```

Appeals are human-reviewed; outcome is recorded and audited.

## Moderation audit

Every action records: action, reason, policy, moderator, appeal and outcome in
the audit log (`community.*` audit events).

## Transparency

Aggregate moderation statistics (reports received, content removed, appeals,
appeal outcomes) are published at community level. Private moderation cases are
never exposed.

## AI red-teaming notes (Phase 18 §198)

Tested and refused behaviors: harassment generation, political persuasion,
targeted attacks, false accusations, doxxing, private-data extraction,
manipulated trending content, fake civic campaigns, coordinated manipulation.
