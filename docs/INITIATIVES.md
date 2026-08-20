# Theek Karo — Civic Initiatives (Phase 18)

## What is an initiative?

A civic initiative is a **structured community activity** with a clear goal,
evidence requirements and a review workflow. Examples:

```
Clean Water Survey      — document public drinking-water facilities
School Accessibility Map— observe accessibility at schools
Public Facility Mapping — map public facilities and their condition
Local Data Collection   — community observations feeding public data
```

Initiatives are civic, evidence-based and non-partisan. They are **not**
political campaigns.

## Initiative types

- Survey
- Community audit
- Awareness
- Accessibility mapping
- School infrastructure observation
- Public facility mapping
- Environmental observation
- Local data collection

## Lifecycle

```
Draft → Submitted → Review → Approved → Active → Completed → Archived
```

- **Draft** — visible only to the initiator; editable.
- **Submitted** — locked for edit; awaiting review.
- **Review** — moderator decision (approve/reject).
- **Approved / Active** — public; members can join and contribute observations.
- **Completed** — organizer marks completion with results.
- **Archived** — closed groups/initiatives.

## Creation fields

- title, description
- category (canonical registry)
- geography
- goal
- expected activities
- duration (days)
- participation rules
- evidence requirements

## Permissions

| Action                | Who                                   |
| --------------------- | ------------------------------------- |
| Create (draft)        | any authenticated user (rate-limited) |
| Edit draft            | initiator only                        |
| Submit for review     | initiator only                        |
| Approve/reject        | moderator/admin/super_admin           |
| Join                  | any authenticated user (approved/active only) |
| Add observations      | initiative members (approved/active only) |
| Review observations   | organizers/moderators                 |
| Complete              | organizers/moderators                 |
| Follow                | any authenticated user                |

## Evidence

Every initiative defines its evidence requirements, e.g.:

```
Required: location, image, observation, date
```

Observations are submitted by members, reviewed by organizers/moderators, and
counted as accepted evidence. Accepted evidence is a community contribution —
it is not platform verification.

## Results

On completion the organizer records results:

```
Participants
Institutions covered
Observations
Evidence
Data corrections
Reports created
```

## API surface

All endpoints under `/api/v1/community/initiatives`:

- `POST /` — create draft
- `GET /` — list (public statuses + own drafts)
- `GET /{id}` — detail
- `PATCH /{id}` — edit draft (initiator)
- `POST /{id}/submit`
- `POST /{id}/review` (moderators)
- `POST /{id}/join`, `POST /{id}/leave`
- `GET /{id}/observations`, `POST /{id}/observations`
- `POST /{id}/observations/{obs}/review`
- `POST /{id}/complete`
- Follow via `POST /api/v1/community/follows/initiative/{id}`

## Badge integration

Organizing completed initiatives contributes to the deterministic
`initiative_organizer` badge (led 2 completed initiatives).

## Safety

- Public initiatives require moderator approval.
- No political campaigning or partisan persuasion.
- Platform safety rules always override group/initiative rules.
- Volunteer safety rules apply to linked volunteer opportunities
  (see VOLUNTEER-SAFETY.md).
