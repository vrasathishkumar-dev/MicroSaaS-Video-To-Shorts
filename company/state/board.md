# state/board.md — every task the company is holding

> One owner per task. No task without a "Done when". Update every cycle.
> Format: `templates/task-template.md`

## In progress

```text
(none yet)
```

## Blocked

```text
T-001 | MISSION-001 | owner: vc-ceo | status: BLOCKED-APPROVAL | 2026-09-09
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
