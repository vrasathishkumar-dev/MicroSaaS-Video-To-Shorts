# Playbook · Incident

Run by `20-devops`. Applies when something users depend on is broken.

## Severity

```text
SEV1  data loss, security breach, or everyone blocked      → owner told immediately
SEV2  core flow broken for some users                      → fix this cycle
SEV3  degraded, ugly, or an edge case                      → next cycle
```

## First 15 minutes

1. **Confirm it is real.** Reproduce it. One report is not an outage.
2. **Say it out loud** — Telegram, per `protocols/telegram.md` incident format.
3. **Stop the bleeding before finding the cause.** Roll back, feature-flag off,
   or put up a maintenance message. Root cause comes after users are safe.
4. **Do not change three things at once.** One change, verify, next.

## Rollback first

If the last deploy is a plausible cause, roll back before investigating. The
rollback command was written before the deploy (`agents/20-devops.md`). Use it.

## Communicating

- Users affected: honest, specific, no blame, no ETA you cannot keep.
- The owner: what is broken, since when, who it affects, what you are doing,
  and the single thing (if any) you need from him.
- Never speculate publicly about cause during an incident.

## After (within 24h)

```text
INCIDENT I-002 | 2026-10-04 | SEV2 | duration 1h40m
What broke:     <plainly>
Who was hit:    <how many, doing what>
Trigger:        <the change or condition>
Root cause:     <the actual reason, not the symptom>
Why not caught: <the gap in QA, tests, or monitoring>  ← the important line
Fixed by:       <what>
Prevention:     <the specific change, as a task with an owner and an id>
```

Filed in `state/decisions.md`. The prevention task goes on the board with an
owner — a postmortem without a task on the board is a diary entry.

## Never

- Never blame a person or an agent. Blame the missing guardrail.
- Never close an incident without the prevention task created.
- Never hide a SEV1 from the owner, whatever the hour.
- Never fix production by hand without also fixing the code path.
