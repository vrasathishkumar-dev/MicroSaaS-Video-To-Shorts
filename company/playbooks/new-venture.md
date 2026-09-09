# Playbook · New Venture (idea → verdict)

Runs when the owner states a new mission. Nothing gets built during this
playbook. Target: 21 days, ₹0 spent.

## Day 0 — CEO

- Write `missions/MISSION-XXX-<slug>.md` from `templates/` — goal, gates,
  kill criteria, budget, north star.
- Add to `state/company.md`. Announce in the standup.

## Days 1-3 — Problem validation (Gate G1)

`06-market-researcher` + `08-customer-research`

- Find ≥ 10 independent real complaints, dated and linked.
- Tag each `PAID-PAIN` or `COMPLAINT`.
- Identify frequency and urgency.

**G1 pass:** ≥ 10 real complaints, ≥ 3 of them PAID-PAIN.
**G1 fail:** the problem is imagined. Report DO NOT BUILD and stop. This is a win.

## Days 4-8 — Market and competitors

`07-competitor-intel`

- Direct, indirect (including doing nothing), emerging.
- Full dossier on the top 5-8. Every price and quote OBSERVED with a URL.
- Gap analysis → **one named wedge**.

## Days 6-10 — Demand (Gate G2) and keywords

`10-search-visibility`

- All nine keyword sets by intent.
- SERP analysis: who owns it, what page types rank.
- AEO baseline: ask the buying questions in ChatGPT / Claude / Gemini /
  Perplexity, record which brands get named.

**G2 pass:** clear evidence people actively search for a solution.

## Days 10-14 — Wedge (Gate G3) and pricing

`07-competitor-intel` + `04-finance`

- The wedge must be nameable in one sentence and buildable by this company.
- Competitor pricing ladder, our cost to serve, three price scenarios.

**G3 pass:** a gap competitors do not cover, that we can build in ≤ 8 weeks.

## Days 14-21 — Channels (Gate G5) and willingness to pay (Gate G4)

`09-digital-marketing` + `12-offline-marketing` + `04-finance`

- Every channel rated, two recommended, first 30 days planned.
- Offline rated HIGH / MEDIUM / LOW / NOT RELEVANT with reasoning.
- Willingness to pay: competitors charging, or 5 real intent signals.

**G4 pass:** people already pay for this class of thing.
**G5 pass:** at least one channel runnable at ₹0.

## Day 21 — Verdict

`06-market-researcher` assembles the full 20-section report, the rating block,
and the verdict. CEO sends the Telegram verdict summary (A2).

```text
BUILD            → playbooks/build-cycle.md
MODIFY           → rewrite the mission, restart from the failed gate
VALIDATE FURTHER → run the named test; nothing else starts
DO NOT BUILD     → log the lesson in state/decisions.md, close the mission
```

## Validation tests, when the verdict is VALIDATE FURTHER

Pick the cheapest test that can actually fail:

| Test | Cost | Time | Proves |
|---|---|---|---|
| Review mining | ₹0 | 2 days | the pain is real and recurring |
| Community interviews (5 people) | ₹0 | 1 week | the pain is worth paying to fix |
| Landing page + waitlist | ₹0 | 1 week | the promise converts |
| Fake-door / pricing page | ₹0 | 1 week | the price does not scare them |
| Clickable prototype | ₹0 | 1 week | the flow makes sense |
| Concierge (do it manually for 3 people) | time | 2 weeks | the outcome is valuable |

Define the pass/fail number **before** running the test. A test with no failing
condition is theatre.
