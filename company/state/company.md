# state/company.md — the company's current position

> Append-only. Date every entry. Never delete history — supersede it.

## Identity

```text
Company:     VC-1  (rename when the first product has a brand)
Owner:       Sathish Kumar — Chennai, IST
Started:     2026-09-09
Markets:     UAE, US, UK  (never India-rate pricing)
Budget:      ₹0 — free tiers only (protocols/money.md)
Money rung:  $0 MRR — no spend permitted
```

## Current focus

```text
2026-09-09 | ACTIVE  | MISSION-001 | video-to-shorts | stage: NOT STARTED
                     | next gate: G1 problem evidence
                     | blocked on: owner to confirm repo / scope
```

## Missions

| ID | Name | Status | Verdict | Gate | Opened | Closed |
|---|---|---|---|---|---|---|
| MISSION-001 | Video-to-Shorts | ACTIVE | pending | G1 | 2026-09-09 | — |

Statuses: `ACTIVE · PAUSED · KILLED · SHIPPED`

## OKRs — Q3/Q4 2026

```text
O1  Prove or kill one product idea with real evidence, fast.
    KR1  MISSION-001 reaches a verdict by day 21           | status: not started
    KR2  ≥ 10 sourced complaints collected (G1)            | status: not started
    KR3  A named wedge, or an honest DO NOT BUILD (G3)     | status: not started

O2  Build the company so it runs without daily owner input.
    KR1  Daily standup runs 7 days without manual help     | status: not started
    KR2  Owner touches ≤ 3 decisions per day               | status: not started
    KR3  All state lives in git, no state in chat history  | status: not started
```

Review OKRs at every weekly board review. An OKR nobody looked at in a month
gets deleted, not carried.

## Standing constraints (do not violate without owner approval)

1. ₹0 spend. Free tiers only.
2. Overseas markets only for pricing and clients.
3. Nothing published under the owner's name/brand without A2 approval.
4. No secrets in any file in this repo.
5. No code before an approved verdict.
6. Preserve existing stack choices (React/RN/Node/Mongo/Next, Python+FastAPI
   for AI, n8n on the owner's VPS) unless there is a strong stated reason.

## Log

```text
2026-09-09 | company founded. ORG.md v1.0 written. MISSION-001 opened.
```

---

## Current focus (set 2026-09-09)

FACT - MISSION-001 is an existing product, not a greenfield idea. See T-001 in
state/board.md and ADR-002/003 in state/decisions.md.

- **Product:** MicroSaaS-Video-To-Shorts (FastAPI + React, ~70% built)
- **Live work:** the founder-approved 50-score gate - clips scoring under 50 are
  listed but never rendered. Backend implemented and verified; frontend and
  tester sign-off outstanding.
- **Money rung:** 0 spent, 0 revenue. Budget stays 0 per protocols/money.md.
- **Next real gates:** G6 first value (working MVP used by >=5 non-friends),
  G7 first money.
- **Known architectural limit:** Telegram is send-only on this VPS. A2 approvals
  cannot be captured automatically; the owner relays them. Do not treat silence
  as consent.
