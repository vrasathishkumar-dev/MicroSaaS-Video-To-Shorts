# Playbook · Creating a New Agent

Run by `03-agent-factory`. Default answer is **no**.

## Step 1 — Prove the gap (two strikes)

```text
GAP: nobody in the company can <capability>.
Strike 1: T-011 — <agent> attempted it, output was <what was wrong>
Strike 2: T-019 — same failure
Is it a capability gap or a briefing gap? <answer, honestly>
Can an existing agent absorb it with a small file change? <if yes, do that>
Will it be needed again? <if no, do it manually once>
```

All four answers must clear the bar. If they do not, extend an existing agent's
file and log why.

## Step 2 — Draft from the template

`templates/agent-template.md`. Required sections: frontmatter (name,
description, tools) · mandate · reports to · autonomy · inputs · process ·
output contract · handoffs · definition of done · never-list.

The **never-list is not optional.** An agent without one will drift.

## Step 3 — Check for overlap

If it duplicates more than ~40% of an existing agent, merge instead. Two agents
with fuzzy boundaries produce contradictory work that nobody is awake to catch.

## Step 4 — Ask (A2)

```text
🟠 NEW AGENT · A2
Gap: <one line>
Evidence: failed on T-011 and T-019
Proposed: vc-<name> — <mandate in one line>
Overlaps: <none / with vc-x>
Autonomy: A1 for the first month
Recommend: YES
```

## Step 5 — Register and probate

- Write `agents/NN-<name>.md`
- Add to `state/agents.md` with date, evidence, and approval
- Add to the ORG.md §14 table
- **Probation: A1 maximum for the first month.** It reports everything it does.
- Review after 30 days: used and useful → keep. Unused → retire.

## Retiring

Monthly, list agents unused for 30 days. Propose retirement (A2). Move to
`agents/retired/`. Never delete — the reasoning is worth keeping, and the same
gap may reappear.

## Anti-patterns

- Creating an agent because a task was hard once
- Creating an agent to avoid writing a better brief
- Creating a "manager of managers"
- More than one new agent per week
- An agent whose mandate overlaps the CEO's routing job
