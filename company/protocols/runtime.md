# Protocol · Runtime (where each part of the company actually runs)

Three runtimes, one company. Each has a job it is best at.

## 1. Cowork scheduled tasks — the clock and the thinking

Runs in the cloud, on a schedule, **whether or not the Mac is on**. This is what
makes the company independent of the owner's laptop.

Runs here: daily standup · market research runs · weekly board review · growth
review · monthly strategy · anything that is reading, thinking, and writing.

Each scheduled task starts a **fresh session with no memory**, so every task
prompt must be self-contained:

```text
You are the CEO agent of VC-1.
1. Read ORG.md, state/company.md, state/board.md and the active mission file
   in the connected "virtual-company" folder.
2. Run the daily standup per agents/01-ceo.md.
3. Append what you did to state/board.md.
4. Send the standup to Telegram; if Telegram is unavailable, put it in the
   chat and write it to state/inbox.md.
Do not start new work without an approved mission. Do not spend money.
```

Scheduled tasks are created with the scheduled-task tools, never with in-session
cron — an in-session schedule dies with the session.

## 2. Claude Code + ECC on the Mac — the building

Runs here: architecture, code, tests, review, security scan, releases. Anything
that touches the repo.

```text
/ecc:plan          → agents/17-architect.md produces the plan
tdd-workflow       → agents/18-engineer.md implements step by step
/code-review       → agents/19-qa.md
/security-scan     → agents/19-qa.md
```

Copy `agents/*.md` into `.claude/agents/` to make them invocable subagents
alongside ECC.

## 3. n8n + Telegram on the VPS — approvals and comms

Runs here: standup delivery, approval buttons, YES/NO capture, alerts, and any
always-on integration polling. Spec in `telegram.md`.

The VPS already runs the owner's **Hermes** personal assistant. Keep them
separate: separate workflows, separate data tables, separate state. Hermes is
his life; VC-1 is the company. They may share the Telegram bot, nothing else.

## What runs where — quick table

| Work | Runtime |
|---|---|
| Research, reports, decisions, planning | Cowork (cloud) |
| Code, tests, review, deploy | Claude Code + ECC (Mac) |
| Standup delivery, approvals, alerts | n8n + Telegram (VPS) |
| Long-lived company facts | `state/` in git |
| Facts about the owner | Claude user memory |

## Failure modes to design around

- **Mac is off** → build tasks queue on the board; thinking tasks still run.
- **Telegram is down** → messages go to `state/inbox.md` and the chat; nothing
  is auto-approved.
- **Cloud session has no folder connected** → it reports in chat and asks the
  owner to connect the folder; it does not invent state.
- **Two runtimes edit state at once** → git is the referee. Commit after every
  session; resolve conflicts in favour of the append-only rule.
