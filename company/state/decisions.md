# state/decisions.md — append-only decision and ADR log

> Never edit an entry. To change a decision, add a new one that supersedes it.
> Format in `protocols/comms.md` §3.

```text
D-001 | 2026-09-09 | decided by: owner | mission: COMPANY
Decision:  Run the company as a folder-based agent org (ORG.md + agents/) rather
           than one large prompt file.
Options:   A) single mega .md  B) folder + agent files  C) Claude Code plugin
Because:   agent files stay small enough to load per task; roles can change
           independently; the folder can live in git and be read by all three
           runtimes.
Cost:      more files to keep consistent; ORG.md must stay the single source of
           truth.
Reversible: yes
Revisit:   if any agent file is never used in 60 days

D-002 | 2026-09-09 | decided by: owner | mission: COMPANY
Decision:  Run across three runtimes — Cowork (cloud clock + thinking),
           Claude Code + ECC (building), n8n + Telegram (approvals).
Because:   the owner wants the company to work while his laptop is off, while
           keeping build work on the machine that has the repo.
Cost:      state must be in git or a connected folder, or the runtimes drift.
Reversible: yes

D-003 | 2026-09-09 | decided by: owner | mission: MISSION-001
Decision:  First mission is the video-to-shorts project.
Because:   owner's stated choice.
Open:      whether an existing GitHub repo already implements part of it —
           blocking T-001.
Reversible: yes
```

---

## ADR-001 · Stack facts corrected to the real codebase
**Date:** 2026-09-09 · **Decided by:** Owner (Sathish) via merge instruction · **Autonomy:** A0 (factual correction)

ORG.md and `agents/17-architect.md` were written assuming React Native / Next.js /
Node-Express / MongoDB. The actual product on this VPS is:

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2 + Alembic, PostgreSQL
- **Jobs:** Redis + RQ
- **Frontend:** React 19 + TypeScript + Vite
- **Media:** ffmpeg, faster-whisper, opencv-headless
- **Runtime:** Docker Compose on the VPS

**Changed:** `agents/17-architect.md` standing stack preference; `agents/20-devops.md`
free-tier list (Mongo Atlas -> Postgres). **Evidence:** FACT - read from
`backend/requirements.txt`, `backend/app/`, `frontend/package.json` on 2026-09-09;
281 backend tests pass.

**Consequence:** the architect must not propose Node/Mongo for this product.

---

## ADR-002 · VC-1 merges onto the existing 10 agents; no second workforce
**Date:** 2026-09-09 · **Decided by:** Owner · **Autonomy:** A2 (approved in instruction)

VC-1 supplies governance, not workers. Mapping adopted:

| VC-1 role | Mapped to |
|---|---|
| vc-researcher / vc-competitor-intel / vc-customer-research | `researcher` |
| vc-ba | `ba` · vc-designer -> `designer` · vc-qa -> `tester` · vc-devops -> `devops` |
| vc-engineer | `backend-agent` / `frontend-agent` / `database-agent` |
| vc-search-visibility | `seo-geo` · vc-digital-marketing + vc-content-social -> `marketer` |
| vc-ceo | **ADDED** as the 11th agent - nothing else owns the board or the cadence |
| vc-architect | folded into `backend-agent` for now; stack already chosen, app ~70% built |
| pm, finance, legal-risk, support, data-analyst, agent-factory | **NOT ADDED** - overhead at zero revenue / zero users |

**Consequence:** `data-analyst` returns when there are users to measure;
`legal-risk` stays a rule inside the researcher/seo prompts, not an agent.

---

## ADR-003 · VC-1 runs on the VPS, on Hermes infrastructure
**Date:** 2026-09-09 · **Decided by:** Owner ("Build on the VPS globally... agents 24/7") · **Autonomy:** A2

`protocols/runtime.md` assumed a 3-runtime split with building on the Mac and Cowork
for scheduling. The owner ruled: everything on the VPS, 24/7.

Hermes's kanban + cron are the only always-on machinery on this box, so VC-1 uses them
as its engine. **Hermes's personal side is untouched:** its n8n workflows, data tables,
Ollama, and the LinkedIn cron are out of scope. VC-1 adds its own cron jobs and its own
board only.

**Known limitation, not solved by this ADR:** Telegram is send-only here. VC-1's A2
approval flow expects YES/NO capture via an n8n webhook writing to this file. There is
no such capture. Until it exists, approvals reach the company only when the owner
relays them, and every A2 card must sit BLOCKED rather than assume consent.

---

## ADR-004 · Full company installed - 24 agents
**Date:** 2026-09-09 · **Decided by:** Owner ("install all the agents... I want like real company") · **Autonomy:** A2 approved in instruction

Installed the 13 VC-1 roles that had no existing equivalent: `vc-pm`,
`vc-architect`, `vc-finance`, `vc-legal-risk`, `vc-competitor-intel`,
`vc-customer-research`, `vc-digital-marketing`, `vc-content-social`,
`vc-offline-marketing`, `vc-sales`, `vc-support`, `vc-data-analyst`,
`vc-agent-factory`. With the existing 10 plus `vc-ceo`, the company is 24 agents.

**Not installed, deliberately:** `vc-researcher`, `vc-ba`, `vc-designer`,
`vc-qa`, `vc-devops`, `vc-engineer`, `vc-search-visibility` - these duplicate
`researcher`, `ba`, `designer`, `tester`, `devops`,
`backend-agent`/`frontend-agent`/`database-agent`, and `seo-geo`. Installing them
would create the second workforce the owner explicitly forbade.

**Reverses part of ADR-002.** ADR-002 skipped pm/finance/legal-risk/support/
data-analyst/agent-factory as overhead at zero revenue. That reasoning was wrong
on `vc-pm` in particular: the kanban dispatcher only routes cards that already
exist, it never creates them. On 2026-09-09 the board went completely idle with
11 agents employed and nothing to do - a PM-shaped hole. `vc-pm` now owns
`company/state/board.md` and keeping the queue fed.

**Consequence / open risk (R-00x):** several roles now overlap
(`marketer` vs `vc-digital-marketing` + `vc-content-social`;
`researcher` vs `vc-competitor-intel` + `vc-customer-research`). Overlap means
two agents can believe they own a task. Per ORG.md §3 that is `vc-ceo`'s call to
resolve and log here. Owner may retire `marketer` later; not deleted without
approval per the standing rule on deleting agents.

**Still not enforceable on this architecture:** A2 approval capture. Telegram is
send-only here, so every approval still reaches the company via the owner
relaying it. Agents must block, never assume consent.
