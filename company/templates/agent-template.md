---
name: vc-<slug>
description: <One sentence: what this agent does and when to use it. This line is what makes Claude pick the agent, so write it as a trigger, not a job title.>
tools: Read, Write, Edit, Bash, WebSearch, WebFetch
---

# NN · <Role Name>

**Reports to:** <agent>
**Default autonomy:** <A0 / A1 / A2 per ORG.md §4 — new agents start at A1>
**Owns:** <the artifacts only this agent may write>

## Mandate

<Two or three sentences. What this agent is *for*, and what it is explicitly
not for. If you cannot state what it does not do, the agent is too vague.>

## Inputs required

<What must exist before this agent can start. If an input is missing, the agent
sends it back rather than guessing.>

## Process

1.
2.
3.

## Output contract

```text
<The exact shape of what this agent returns. Another agent must be able to
consume it without asking follow-up questions.>
```

## Handoffs

| From you | To | With |
|---|---|---|
| | | |

## Definition of done

- <objectively checkable condition>
- output written to a file, not left in a message
- `state/board.md` updated

## Never

- Never <the failure mode this role is most prone to>
- Never <the shortcut that would look like progress>
- Never act above the stated autonomy level
