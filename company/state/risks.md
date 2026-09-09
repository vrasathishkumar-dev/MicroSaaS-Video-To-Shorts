# state/risks.md — open risks

> Severity: LOW / MEDIUM / HIGH. Every risk has an owner and a review date.
> A HIGH risk is escalated to the owner the day it becomes HIGH.

```text
R-001 | 2026-09-09 | HIGH | Platform dependency
  Risk:       A video-to-shorts product that pulls from YouTube/TikTok/Instagram
              depends on those platforms' terms and APIs, which change without
              notice and can forbid automated access.
  Trigger:    ToS change, API restriction, or account action
  Mitigation: design direct upload as the primary path; treat any platform
              integration as optional. Legal-risk must GREEN any pull-based flow
              before it is built.
  Owner:      vc-legal-risk → vc-architect
  Review:     before any architecture decision on MISSION-001

R-002 | 2026-09-09 | HIGH | Crowded category
  Risk:       Automated short-clip tools are a well-funded, fast-moving
              category. Entering without a specific wedge means competing on
              features against companies with far more resource.
  Trigger:    competitor research finds no defensible gap
  Mitigation: Gate G3 exists precisely for this. If no wedge can be named in one
              sentence, the verdict is MODIFY or DO NOT BUILD.
  Owner:      vc-researcher
  Review:     at G3

R-003 | 2026-09-09 | MEDIUM | Model and compute cost
  Risk:       Video processing and AI inference cost real money per user, and
              the company has a ₹0 budget.
  Trigger:    any design that requires paid GPU or paid model calls per job
  Mitigation: cost-per-job must be modelled by vc-finance BEFORE the architect
              picks an approach; prefer local/open models on the owner's VPS.
  Owner:      vc-finance
  Review:     at G4

R-004 | 2026-09-09 | MEDIUM | Owner bandwidth is the real constraint
  Risk:       The company can only move as fast as the owner answers A2/A3
              items. Unanswered approvals stall everything.
  Trigger:    more than 2 approvals older than 24h
  Mitigation: batch approvals into the standup; keep the daily message budget
              to 3; make every request decidable in 10 seconds.
  Owner:      vc-ceo
  Review:     weekly

R-005 | 2026-09-09 | MEDIUM | Copyright and rights on user content
  Risk:       Users will upload video they do not own; the product could be seen
              as facilitating infringement.
  Trigger:    product launch
  Mitigation: rights are the user's responsibility, stated in the UI and terms;
              no library of others' content; no republishing on the user's behalf
              without explicit action. A lawyer must confirm the terms.
  Owner:      vc-legal-risk
  Review:     before launch
```
