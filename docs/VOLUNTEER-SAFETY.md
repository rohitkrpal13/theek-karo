# Theek Karo — Volunteer Safety (Phase 18)

## Principles

Volunteering on Theek Karo is civic and privacy-respecting:

```
- No personal phone numbers
- No home addresses
- No private contact details
- No exact volunteer locations
- Controlled in-app communication only
```

The platform never publishes a public personal directory of volunteers.

## Volunteer profile

Users opt into volunteering with explicit preferences only:

- Preferred languages
- Broad interests
- Preferred categories
- Available areas (general, e.g. district/town — not exact addresses)
- Skills (photography, video, data analysis, translation, teaching,
  technology, GIS, outreach, accessibility, documentation, research)
- Availability

Skills and interests are **never inferred automatically** — the user must
confirm them.

## Volunteer opportunities

- Opportunities are created by initiative organizers or platform moderators.
- Each opportunity has a title, description, general location label, required
  skills, capacity and status.
- Joining is capped at `participants_needed`; over-capacity joins are rejected
  (`opportunity_full`).
- Volunteer signups are visible only to the volunteer and the organizer via
  `my_status`; no public attendee lists.

## What is never exposed

- Private volunteer contact details
- Exact volunteer locations (opportunities carry a general location label only)
- Attendee/participant lists by default
- Private profiles

## Communication

In-app communication is used where possible. Personal contact information is
never automatically exposed between volunteers and organizers.

## AI volunteer matching

`recommend_public_initiatives` recommends approved/active public initiatives
matching **explicit** user-declared skills and interests. It uses public data
only, never profiles participants, and never infers sensitive characteristics.

## Safety rules for initiatives

- Initiatives must be civic and non-partisan.
- Public initiatives require moderator review before becoming visible.
- Organizers are responsible for their initiative content; platform rules
  always override.
- Events and meetups must provide safety information and should avoid exposing
  private meeting points unnecessarily.

## Reporting

Volunteer safety violations (harassment, doxxing, exposure of private details)
are reported through the standard content/user reporting flow and routed to the
moderation queue.
