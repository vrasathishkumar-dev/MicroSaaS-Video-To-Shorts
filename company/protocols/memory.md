# Protocol · Memory and state

Agents forget everything between sessions. Three different stores exist and
mixing them is the most common way an autonomous company goes wrong.

| Store | Holds | Lifetime | Who writes |
|---|---|---|---|
| `state/*.md` in this repo | the company's facts and history | forever, in git | every agent |
| Claude user memory | facts about **Sathish** (preferences, goals, skills) | across all his sessions | Claude, per its own rules |
| Repo `CLAUDE.md` | facts about **the codebase** (conventions, commands) | with the code | architect, engineer |

**Rule:** a company fact never goes in user memory. A codebase convention never
goes in `state/`. A personal preference never goes in the repo.

## The state files

```text
state/company.md    mission list, OKRs, current focus, rung on the money ladder
state/board.md      every task: id, mission, owner, status, done-when
state/decisions.md  append-only decision + ADR log
state/risks.md      open risks with severity, mitigation, owner, review date
state/metrics.md    dated numbers with sources
state/agents.md     which agents exist and why
state/inbox.md      unstructured input from the owner, to be triaged by the CEO
```

## Writing rules

1. **Append, don't rewrite.** History is the point. To change a fact, add a new
   dated line that supersedes the old one; do not delete the old one.
2. **Date everything.** `2026-09-09 |` starts every entry.
3. **Label every claim** FACT / OBSERVATION / ESTIMATE / ASSUMPTION.
4. **Cite the source** for anything retrieved from the web.
5. **One file, one purpose.** Do not put metrics in the board.
6. **Never store secrets.** Names of env vars are fine; values never.

## Reading rules — the start of every session

```text
1. ORG.md                      the rules
2. state/company.md            what we are doing
3. missions/<active>.md        the current goal and its gates
4. state/board.md              what is in flight
5. only then, the agent's own file
```

Reading in a different order is how an agent starts confidently working on last
month's plan.

## When state and a person disagree

The file wins for *what was decided*. The owner wins for *what should happen
next*. If the owner says something that contradicts a recorded decision, log a
new decision that supersedes it — never silently edit the old one.

## Session handover

Any long-running task that ends mid-flight writes a handover block:

```text
HANDOVER | T-014 | 2026-09-09 21:40 IST
Done:        <what is finished and where it lives>
In progress: <the exact next step>
Careful:     <the thing that will bite the next session>
Files:       <paths touched>
```

Without this, the next session repeats work. With it, the company is genuinely
continuous.
