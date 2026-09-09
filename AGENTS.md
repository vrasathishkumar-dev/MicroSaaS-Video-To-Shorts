# Rules & Preferences

- **Autonomous Command Execution**: Run development, inspection, test, build, and service start commands autonomously without asking for approval unless it is a major destructive change or critical design pivot.
- **Goal**: Always deliver fully analyzed, end-to-end workable applications with backend, frontend, database, and background processing operational and verified.

---

# VPS AUTONOMOUS EXECUTION (added for the 24/7 Hermes runner)

Everything above is the founder's own project convention and takes precedence.
This section only covers **how work runs unattended on the VPS**, where Hermes
dispatches kanban cards instead of a human driving an interactive session.

## STOP — you do not write code. Claude Code does.

When Hermes runs a card, it must NOT use its own `patch`/`write_file`/`edit_file`
tools on source. Delegate every implementation, fix, review and content task:

```bash
su - worker -c 'set -a; source ~/.claude_token.env; set +a; cd <worktree>; claude -p "<card title + body + comments, verbatim>" --agent <role> --dangerously-skip-permissions'
```

`<role>` is one of this repo's own agents: `ba`, `designer`, `backend-agent`,
`frontend-agent`, `database-agent`, `tester`, `devops`, `seo-geo`, `marketer`,
`researcher`. Put the role in the card title, e.g. `[backend-agent] ...`.

Writing the code yourself is a FAILED card even if the code works. The `file`
toolset is disabled on the worker profiles specifically to prevent this.

## THIS REPO IS PUBLIC — branches only, never main

- **Never commit or push to `main`.** Ever. The founder merges.
- Work on the card's own branch and push only that branch.
- Before pushing, check you are not committing secrets, `.env`, tokens, keys,
  upload fixtures, or anything under `backend/uploads/`. A mistake here is
  world-visible immediately.
- If a task seems to require touching `main`, `kanban_block` and ask.

## Getting another card's code

```bash
ops/merge-card.sh t_xxxxxxxx      # task id, NOT a branch name
```

Hermes truncates branch names, so typed branch names fail. All worktrees share
one `.git` store — the branch is already local. **Never `git fetch`**: the
`worker` user has no GitHub credentials by design (root pushes via the hourly
sweep).

## Handoff: use this repo's own `team/backlog.md`

`team/backlog.md` is the single shared handoff file, with the founder's status
values (`needs-approval` → `approved` → `in-design` → `in-dev` → `in-qa` →
`qa-signoff-needed` → `approved-for-release` → `deployed` → `done`). Append your
subsection when done; do not re-ask a prior role's questions.

Because each card runs in an isolated worktree, a `team/backlog.md` edit on
another branch may not be visible to you. If the story you need isn't there,
pull it in with `ops/merge-card.sh <task_id>` rather than guessing.

## Never fabricate completion

- If a required input is missing, or you could not do the work: `kanban_block`
  and say exactly what is missing. Do NOT write a note describing work you did
  not do.
- "Verified by read" is not verification. If a card names a check (`pytest`,
  a build, a boot), you must actually run it and see it pass before completing.
- Never assert a cause you did not observe — paste real error output.
- Deleting a feature to make a check pass is a failed card.

## Founder approval gates (unchanged from the Playbook)

1. After `ba` drafts a story — scope approval.
2. After `tester` signs off — release approval.

Plus the founder's standing rule: **a new idea gets researched before it gets
built.** Use `ops/research-idea.sh "<idea>"` — three phases (market+problem,
money+audience, verdict), the verdict goes to Telegram, and the card blocks
until the founder approves. No build card may be created for an unapproved idea.

## Environment facts (verified on this box)

- Python/FastAPI backend, React/Vite frontend, Docker compose.
- `node` v18 + `npm` are system-wide and work as `worker`.
- Port 3000 is taken by an unrelated WhatsApp bridge — never assume a curl to
  3000 is your app.
- Reports to the founder go to Telegram:
  `/usr/local/bin/hermes send -t telegram -s '<subject>' -f <file>`
  (use the absolute path — a bare `hermes` exits 126 on the worker PATH).

## Running the backend tests (from any worktree)

The Python venv lives OUTSIDE git, so a worktree has no `.venv` of its own.
Always call it by absolute path, from the worktree's own `backend/` dir:

```bash
cd <your-worktree>/backend
/srv/microsaas-video-to-shorts/backend/.venv/bin/pytest -q
```

Verified baseline on 2026-09-09: **281 passed, 0 failed** (~3 min). If you see
"missing sqlalchemy" or similar, you used the wrong python - re-read the line
above. Never report a test result you did not actually run.
