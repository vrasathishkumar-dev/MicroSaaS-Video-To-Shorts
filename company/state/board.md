# state/board.md — every task the company is holding

> One owner per task. No task without a "Done when". Update every cycle.
> Format: `templates/task-template.md`

## In progress

```text
(none yet)
```

## Blocked

```text
T-001 | MISSION-001 | owner: vc-ceo | status: DONE | resolved 2026-09-09
Goal:       Confirm what MISSION-001 actually is
Done when:  Owner confirms whether "video to shorts" is an existing repo (and
            its path/URL) or a new idea to build from scratch, and confirms the
            mission file as written.
Autonomy:   A2
Output to:  missions/MISSION-001-video-to-shorts.md
Notes:      Everything downstream depends on this. Do not start G1 research on
            a scope that may change.
```

## Todo

```text
T-002 | MISSION-001 | owner: vc-researcher | status: TODO | depends on: T-001
Goal:       Gate G1 — prove the problem is real
Done when:  ≥ 10 independent, dated, linked complaints collected; ≥ 3 tagged
            PAID-PAIN; frequency and urgency stated.
Autonomy:   A0
Output to:  missions/research/001-problem-validation.md

T-003 | MISSION-001 | owner: vc-competitor-intel | status: TODO | depends on: T-001
Goal:       Competitor landscape and gap analysis
Done when:  Direct + indirect + emerging mapped; top 5-8 full dossiers with
            OBSERVED pricing (URL + date); gap table; one named wedge.
Autonomy:   A0
Output to:  missions/research/001-competitors.md

T-004 | MISSION-001 | owner: vc-search-visibility | status: TODO | depends on: T-001
Goal:       Keyword sets + SERP + AEO baseline
Done when:  All 9 keyword sets produced; SERP ownership described; the buying
            questions asked in 4 AI assistants and the named brands recorded.
Autonomy:   A0
Output to:  missions/research/001-search.md

T-005 | COMPANY | owner: vc-devops | status: TODO
Goal:       Wire the Telegram approval loop in n8n
Done when:  A test approval message reaches the owner's Telegram with YES/NO
            buttons and the reply lands back in state/decisions.md.
Autonomy:   A2 (needs the owner's Telegram chat ID — A3 step)
Output to:  protocols/telegram.md (mark as built)
```

## Done

```text
D-000 | 2026-09-09 | Company operating system written (ORG.md + 21 agents +
        protocols + playbooks + templates)
```

### VC-1 standup — 2026-09-09 11:37 UTC
```text
🏢 VC-1 · 2026-09-09 · MISSION-001
Done: Company OS scaffolded (ORG.md, 21 agent files, protocols, playbooks) — D-000. No mission work completed.
Today: Get owner's answer on T-001 (existing repo vs new build) to unblock G1 research.
Blocked: T-001 — scope confirmation, owner. Also `hermes kanban --board microsaas list` denied approval, so live kanban state could not be read this cycle.
Waiting on you: Confirm whether "video to shorts" = your existing repo (path/URL) or an OSS project to build from, per MISSION-001-video-to-shorts.md.
Gate: G0 Scope due 2026-09-09 — at risk (due today, unconfirmed).
Money: ₹0 spent / ₹0 revenue.
```

## Resolved

```text
T-001 | MISSION-001 | owner: vc-ceo | status: DONE | RESOLVED 2026-09-09
Answer:     CASE A - the owner has an EXISTING repo to finish and commercialise.
Repo:       github.com/vrasathishkumar-dev/MicroSaaS-Video-To-Shorts (public)
On VPS:     /srv/microsaas-video-to-shorts
Evidence:   FACT - FastAPI backend with 8 routers, React/Vite frontend, Docker;
            281 backend tests pass (verified 2026-09-09); stories already marked
            deployed in team/backlog.md.
Therefore:  the mission is FINISH AND SHIP, not validate-and-build. G1-G4 are
            largely satisfied by the researcher run of 2026-09-09 (BUILD verdict,
            competitor + pricing + channel evidence). Remaining real gates are
            G6 first value and G7 first money.
```

### VC-1 standup — 2026-09-09 11:38 UTC
```text
🏢 VC-1 · 2026-09-09 · MISSION-001
Done: 50-score gate story (ba), UI spec for unrendered-clips state (designer), backend gate on virality score≥50 (backend-agent), and tester audit of pytest results — all closed on kanban.
Today: Route to frontend-agent to implement the designer's unrendered-clips UI, then back to tester for full sign-off.
Blocked: nothing.
Waiting on you: nothing.
Gate: G6 first value due — at risk (backend gate shipped, frontend + tester sign-off still open).
Money: 0 spent
```
