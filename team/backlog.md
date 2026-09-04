# VideoToShorts — Backlog

Single shared handoff file for the one-person-company pipeline described in
`AI Virtual Team Playbook.md` and `CLAUDE.md` → Agent Coordination. Every
role reads the story it's working on here before starting, and appends its
own subsection when done — nobody re-asks a prior role's questions.

Founder = product owner. Two approval gates: **after BA drafts a story**
(scope approval) and **after Tester signs off** (release approval). Every
other handoff runs without stopping.

Status values: `needs-approval` → `approved` → `in-design` → `in-dev` →
`in-qa` → `qa-signoff-needed` → `approved-for-release` → `deployed` →
`done`.

---

## Pending founder approval

_(BA appends new stories here. Nothing below this section starts until the
founder approves it.)_

---

## Active

_(Approved stories move here as they move through Designer → Developer →
Tester → DevOps → SEO/GEO/AEO → Marketer, each appending a subsection below the
story.)_

---

### B-roll sourcing & auto-insertion (Pexels/Pixabay)

**Status:** qa-signoff-needed

Auto-sources and manually searches stock B-roll from Pexels/Pixabay per
clip, ranks results by relevance/aspect-ratio fit for the 9:16 canvas, and
composites them into the render (PIP or fullscreen) — all re-editable per
`CLAUDE.md`'s B-roll Sourcing rule.

**Backend:** `app/services/broll_sourcing.py` (search + keyword extraction
+ ranking), `app/services/video_render.py` (compositing, remote-asset
download with a 200MB/size-bounded fetch), `app/schemas/broll.py`
(request/response shapes, http(s)-only `asset_url` validator, and a
`position_end > position_start` validator added this session to reject a
degenerate window at the API boundary instead of silently dropping it at
render time), `app/routers/broll.py` (pre-existing, unchanged).

**Tester (this session):** Ran the full backend suite
(`pytest`, 246 passed) and frontend suite (`vitest`, 84 passed across 16
files), plus `tsc --noEmit` and `oxlint` (0 errors; only pre-existing
warnings unrelated to this diff). Added one regression test
(`test_manual_insert_rejects_non_positive_window`) for the new validator.
No blocking issues found.

**Founder approval needed:** this is the release-approval gate — sign off
here before DevOps deploys.

---

## Done

_(Fully shipped stories move here, complete with every role's subsection, as
a record of what was built and why.)_
