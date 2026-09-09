# VC-1 — a virtual company that runs itself

This folder is an operating system for an AI-run software company. It is not
documentation about a company; it *is* the company. Read `ORG.md` first.

```text
ORG.md         the constitution — decision rights, autonomy levels, cadence,
               money rules, kill criteria, and the honest list of what only
               a human can do
missions/      the only place goals live. One file per mission.
state/         the company's brain: board, decisions, risks, metrics, roster
agents/        21 role definitions, each usable as a Claude Code subagent
protocols/     comms envelope, Telegram, money, memory, runtime
playbooks/     new venture · build cycle · growth loop · board review ·
               agent creation · incident
templates/     agent · task · market report
```

## Start it

**Claude Code / ECC (on the Mac)**

```text
Read ORG.md and state/company.md. You are the CEO agent (agents/01-ceo.md).
Run today's cycle.
```

Copy `agents/*.md` into `.claude/agents/` to make every role an invocable
subagent (`vc-ceo`, `vc-researcher`, `vc-engineer`, …) alongside ECC.

**Cowork (cloud, laptop off)** — a scheduled task runs the daily standup and
the weekly board review. See `protocols/runtime.md`.

**n8n + Telegram** — approvals and alerts. Spec in `protocols/telegram.md`.

## The three rules that make it work

1. **No code before an approved verdict.** The researcher decides whether the
   thing is worth building, and the owner approves that verdict.
2. **Every mission has gates and a kill rule.** Missing two gates proposes a
   kill. Killing early is a win, not a failure.
3. **Every claim is labelled** FACT / OBSERVATION / ESTIMATE / ASSUMPTION,
   with a confidence level. A report with no LOW-confidence items has not been
   honestly written.

## Day 0

`ORG.md` §15.
