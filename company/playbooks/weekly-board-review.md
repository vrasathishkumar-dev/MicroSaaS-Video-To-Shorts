# Playbook · Weekly Board Review (Monday 08:00 IST)

Run by `01-ceo`. This is the meeting that keeps an unsupervised company honest.

## Inputs

`state/company.md` · `state/board.md` · `state/metrics.md` · `state/risks.md` ·
`state/decisions.md` (last 7 days) · the active mission file · last week's
growth review · support pattern report.

## Agenda — in this order, no reordering

**1. Numbers first, story second.**
`21-data-analyst` reports what moved, what did not, and the one number that
contradicts the current plan. Nobody explains anything until the numbers are on
the table.

**2. Gates.** For each active mission: which gate is next, when is it due, is it
on track / at risk / missed?

**3. What actually shipped.** Not what was worked on. Shipped.

**4. What is stuck.** Every `BLOCKED` task older than one cycle, with the reason
and the owner. Blocked on the owner is a separate list.

**5. Risks.** Anything that moved severity. Anything overdue for review.

**6. Money.** Spend, revenue, which rung of the ladder (`protocols/money.md`).

**7. The decision.** Exactly one proposal per mission:

```text
MISSION-001
Evidence:  <3 lines, numbers not adjectives>
Gate G2:   MISSED — no search demand found for the wedge
Proposal:  MODIFY — narrow to agencies, re-run G2 with their vocabulary
Cost:      1 week
Alternative considered: KILL — rejected because G1 evidence was strong
```

**8. One improvement to the system itself.** What made the company slow or
confused this week? Fix the file that caused it — a rule, a brief, an agent's
never-list. A company that does not improve its own operating manual stops
working the moment its owner looks away.

## Output

- Appended to `state/decisions.md`
- One Telegram message to the owner: numbers, gate status, the proposal, the ask
- Board re-prioritised for the week

## The rule that makes this real

**Every mission must be proposed for CONTINUE, MODIFY, or KILL every week.**
No mission gets to quietly continue by default. The CEO must actively re-argue
for it. Missions that cannot be re-argued are missions that should be killed.
