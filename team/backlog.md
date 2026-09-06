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

### Clip virality score is fake — needs a real, server-computed score before the founder trusts it to skip manual review

**Status:** deployed (2026-09-06)

**Priority:** P0 — the founder has stated they intend to publish clips to
YouTube based on this number without reviewing each one by hand. A
fabricated score isn't cosmetic here, it's actively misleading a publish
decision.

**Module:** Clip Library (primary — `Clip` model/migration, the scoring
logic, `PUT /clips/{id}`). Touches Export & Publish only in that the render
pipeline (`video_render.py`) is the one existing background-job entry point
this story hangs its "refine after render" behavior off of — no change to
what Export & Publish actually renders or how a user downloads a clip. Does
not touch B-roll Sourcing (separate, already release-approved story) or
Auth. Does not touch `reframe.py`'s internal analysis logic — it calls the
existing public `compute_speaker_framing()`, same as `video_render.py`
already does; nothing inside that file changes.

As a creator who plans to publish clips straight to YouTube without
reviewing each one, I want the "Score X/100" shown on a clip to reflect that
specific clip's actual hook strength, whether it starts and ends on a
complete thought, and whether the speaker is visibly well-framed throughout
— not a formula that only reads the auto-generated title against a fixed
keyword list — so that a low score is a real signal to review the clip by
hand, and a high score is trustworthy enough to publish without one.

**Context (root cause, already investigated — do not re-derive):**
- The displayed score comes from `computeViralityInsights()` in
  `frontend/src/lib/virality.ts`, called from **two** places —
  `ClipCard.tsx:33` and `ClipEditorPage.tsx:328` — both as
  `computeViralityInsights(clip.caption_text || clip.title, duration)`. The
  second call site isn't in the founder's own report; found while confirming
  scope here, must be fixed alongside the first or the editor page will keep
  showing the fake score even after `ClipCard` is corrected.
- The function only ever inspects the clip's ~60-character auto-generated
  title/caption string against 16 hardcoded keywords (`VIRAL_HOOK_KEYWORDS`),
  plus a duration-bucket heuristic that clusters nearly all 25-60s clips into
  the same band. Its own `baseScore` parameter — documented in its own code
  as "Base raw score from backend" — is never passed by either call site, so
  it silently defaults to `0.65` every time.
- Critically, the final formula is `Math.max(65, Math.min(99, ...))` — the
  score can **never** go below 65 or above 99. Combined with the fixed
  `explanation` strings per band (fabricated prose like "high-retention
  keywords and fast narrative progression" — asserted regardless of what the
  clip actually contains) and the detail panel's hardcoded "Wayin AI Score"
  header (a naming artifact from an unrelated reference product, not this
  app's own computation), today's badge cannot ever tell a founder "review
  this one," which defeats the entire point of scoring a clip before
  publishing it unreviewed.
- Nothing server-side computes or stores a score on `Clip` today, but the
  frontend `Clip` type (`frontend/src/types/index.ts:79-82`) already
  declares unused, never-populated optional fields —
  `virality_score`, `virality_reason`, `hook_score`, `engagement_score` —
  dead scaffolding from an earlier, abandoned attempt at this. Reuse these
  field names (renaming `engagement_score`, see below) instead of adding new
  ones next to them.

**Real signals that already exist server-side (reuse; do not build new
analysis):**
1. **Hook strength** — `highlight_detection.hook_score(text: str) -> float`
   (pattern-matches openings: questions, "here's the...", numbers,
   superlatives) plus its insight-keyword-density companion
   (`_payoff_score`/`INSIGHT_KEYWORDS`). Run against the clip's actual
   spoken transcript — its opening `TranscriptSegment` for the hook check,
   its full in-window text for the insight-density check — not the title.
2. **Complete start-to-end flow** — reuse the sentence-terminal-punctuation
   check (segment text ending `.`/`!`/`?`) that `clip_service.py`'s
   `_extend_to_sentence_boundary`/`_clamp_start_to_boundary` (shipped in the
   immediately-prior story) already use, evaluated against the clip's
   *current* `start_time`/`end_time` at score-computation time — not assumed
   true from generation time. Both the drag-trim editor and
   `TextBasedTrimmer`'s per-sentence Start/End buttons can move a clip onto
   a mid-sentence cut after generation.
3. **Speaker visibility/framing** — `reframe.compute_speaker_framing(source_path,
   start_time, duration, target_width, target_height) -> SpeakerFraming | None`.
   This is a **pass/fail** signal (`None` = no confident subject found), not
   a gradient — treat "a `SpeakerFraming` was returned" as the full framing
   score and `None` as zero. Do not invent a confidence scale it doesn't
   have.

**Decision on signal #3's availability (the founder's own callout — resolved
here, not left to the developer):** `compute_speaker_framing` does real
OpenCV frame analysis and, per `CLAUDE.md`'s rule against synchronous video
processing in a request handler, cannot run inline when a clip is first
created via `POST /clips/generate` (a request handler). Today it only runs
inside `video_render.py`'s render pipeline (an existing background job) —
and only when `framing_mode == speaker_focus`; `dynamic_blur`/`fit` clips
never trigger it at all, today, for any purpose.
- **A clip's score is computed in two passes, not one:**
  - **Partial score** (`draft`, and any time after boundaries change — see
    below): hook + completeness only, computed synchronously and cheaply —
    no video decode, text/pattern matching only.
  - **Refined score** (once render succeeds and `status` reaches `ready`):
    hook + completeness + framing. The render pipeline's own existing call
    to `compute_speaker_framing` (for `speaker_focus` clips) is untouched;
    this story adds a call to the same function, from the same background
    job, **for every clip regardless of `framing_mode`** — the function is
    cached per `(file, range, target size)` per its own docstring, so this
    is one extra cheap call for `dynamic_blur`/`fit` clips, not a new
    analysis pass, and it means every clip gets a real framing signal once
    it renders, not only `speaker_focus` ones. A render that ends in
    `failed` leaves the clip at its partial score — framing is only added on
    a successful `ready` transition.
  - These two states must be **distinguishable in the UI**, not only in the
    stored data — a founder skimming the Clip Library must be able to tell
    "this is a text-only estimate" from "this includes the framing check,"
    not just see two numbers that happen to differ.

**Bounds (the real decisions this story makes, so weighting isn't left to
developer improvisation):**
- Store per-component sub-scores on `Clip`, not only the final number:
  reuse/repurpose the existing dead frontend fields as the contract —
  `virality_score` (0-100, always populated once a clip exists),
  `hook_score`, a renamed `completeness_score` (replacing the dead,
  wrongly-named `engagement_score` field, which measured nothing about
  engagement), and a nullable `framing_score` (`null` until the refined pass
  runs — its nullness *is* the partial/refined marker, no separate boolean
  needed), plus `virality_reason` (a short string built from which
  sub-signals actually drove the number, not fixed per-band marketing copy).
- Weights must be named constants (backend-side), each with a one-line
  justification, the same bar the prior story's
  `_SENTENCE_BOUNDARY_ALLOWANCE_SECONDS` was held to — not inline magic
  numbers. They must sum to 1.0 across whichever signals are actually
  available at that computation time (i.e. the partial-score weights are a
  renormalization of the refined-score weights over hook+completeness only,
  not a separately-invented pair). Hook and completeness should carry more
  combined weight than framing — framing is a binary pass/fail, not a
  graded signal, so it should refine the score, not dominate it.
- Completeness is not binary — score it in at least three tiers (both edges
  on a real sentence boundary / one edge / neither), so two clips that are
  "mostly" but not perfectly on-boundary don't collapse to the same value
  as a clip that's clean on both ends.
- Rating-label bands must be recalibrated for a genuine 0-100 range (today's
  65-99 floor/ceiling is gone). The lowest band must read as an instruction
  to review, not a shrug — rename the current bottom label ("Standard
  Clip," which reads as "this is fine") to something that unambiguously
  signals manual review is warranted for that clip.
- `virality_reason` is composed from the clip's actual computed sub-scores
  (e.g. naming which of hook/completeness/framing was weak), not selected
  from a fixed per-band string — the current fabricated explanation prose is
  exactly the same problem as the fake score, just in text form, and must
  not survive as "the number is now real but the reason is still made up."
- Existing `Clip` rows (pre-migration): backfilled with `virality_score =
  NULL` (a raw SQL default can't run the scoring logic). The frontend must
  render `null` as a distinct "not yet scored" state — never as a coerced
  `0` or a hidden badge — and the score is populated the next time that clip
  is edited (`PUT /clips/{id}`) or re-rendered. A bulk backfill job for all
  existing clips immediately is out of scope here; flag to the founder as a
  follow-up if immediate values for old clips matter.

**What this is not (non-goals):**
- No new CV/ML model or visual analysis — reuse `compute_speaker_framing`'s
  existing pass/fail signal exactly as it exists today.
- No change to `highlight_detection.py`'s or `reframe.py`'s internal logic —
  both are called read-only, as public functions already used elsewhere.
  `reframe.py` in particular is flagged elsewhere as verified/working and
  off-limits to internal edits; this story only adds a second *caller* of
  its existing public function.
- Not bundled with the in-flight B-roll story or any other work — unrelated
  files, do not touch.
- No new `Clip`/`VideoProject` `status` value — the two-pass scoring
  (partial/refined) is a property of the score field itself, not a new
  pipeline state.
- Does not change what `update_clip` does to `status` when boundaries move
  (that's existing, separate behavior) — this story only adds score
  recomputation/invalidation on that same edit, not a status change.

**Acceptance criteria:**
- A newly generated draft clip has a real, non-hardcoded-default
  `virality_score` computed from hook strength + completeness at creation
  time, with `framing_score` null.
- Once a clip's render succeeds (`status` reaches `ready`), its score is
  refined to include the framing signal — a `null`→populated `framing_score`
  and a recalculated `virality_score` — regardless of the clip's
  `framing_mode` (not only `speaker_focus`). A render ending in `failed`
  leaves the prior partial score untouched.
- Two clips built from meaningfully different transcript content and framing
  quality (e.g. one with strong hook markers, a clean sentence-boundary cut,
  and a confident framing result, vs. one with no hook markers, a
  mid-sentence cut, and no confident subject found) must **not** converge on
  the same or nearly the same score by coincidence of duration — the two
  scores must differ by a clearly non-coincidental margin, not a rounding
  artifact.
- A clip that scores weakly on all three signals lands in the lowest rating
  band, and that band's label reads as an instruction to review the clip,
  not as a passable/default result.
- `virality_reason` names the actual weak/strong signals for that specific
  clip — verified by asserting its content differs between two clips with
  different sub-scores, not just asserting it's non-empty.
- Editing a clip's `start_time`/`end_time` via `PUT /clips/{id}` (drag-trim
  or the per-sentence Start/End buttons) triggers a recomputation of the
  partial (hook + completeness) score against the new boundaries, and
  invalidates (`null`s) any previously-computed `framing_score` even if the
  clip was already `ready` — a stale framing result computed for the old
  boundaries must not silently keep describing the new ones.
- Existing `Clip` rows created before this migration load without error,
  display a distinct "not yet scored" state (not a coerced zero), and get a
  real score the next time they're edited or re-rendered.
- Frontend (`ClipCard.tsx` and `ClipEditorPage.tsx` — both call sites)
  displays the backend-provided score/sub-scores instead of computing its
  own from the title; `virality.ts` keeps only score→label/color mapping
  (`ViralityScoreBadge` still consumes the same shape it does today), the
  scoring math itself (`computeViralityInsights`'s formula) is deleted, not
  kept dead alongside the real one.
- Full backend + frontend test suites pass; new tests cover the
  discrimination case, the draft-vs-ready refinement transition, the
  failed-render-leaves-partial-score case, the boundary-change invalidation
  case, and the legacy-row null-score display.

**Designer:** not a full design pass, but **not silently skipped either** —
this changes what's visually shown (scores that can now go low, and a new
partial-vs-refined distinction) in ways the sentence-boundary story's
UI-untouched skip didn't. One narrow question for Designer before
Developer starts: can the existing `ViralityScoreBadge`/detail-panel visual
treatment carry (a) a genuinely low score with its new "review this" label,
and (b) a visible partial/refined distinction, as-is — or does it need a
redesign for these new ranges/states? Also flag for Designer/Developer while
touching this component: the detail panel's hardcoded "Wayin AI Score"
header names an unrelated product and should go, since the panel is about
to show this app's own real computation.

**Scope note:** this is a real multi-file feature, not a one-file tweak —
expected touch points: `Clip` model + a new Alembic migration, a new backend
scoring path (reusing `highlight_detection.hook_score`/`_payoff_score` and
`reframe.compute_speaker_framing`), the `clips` router/schema
(`ClipResponse`/`ClipUpdateRequest`), the render pipeline's call site in
`video_render.py`, and the frontend (`virality.ts`, `ViralityScoreBadge.tsx`,
`ClipCard.tsx`, `ClipEditorPage.tsx`, `types/index.ts`). Size the design and
implementation plan accordingly.

---

#### Designer

**Verdict:** the pill's shape/layout carries all of this as-is. One new
color band + two new marker states are needed; no new component, no new
file. Reviewed `ViralityScoreBadge.tsx`, `lib/virality.ts`, `ClipCard.tsx`
(+ `ClipGrid.tsx` for card width), and both `ClipEditorPage.tsx` call sites
(header pill + detail-panel `showDetails` block) before writing this.

**1. Can the existing visual treatment carry a genuinely low/"needs review" score?**

Layout/shape: yes, unchanged — same pill, same icon+text pattern.
Colors: no — today's three bands (emerald ≥90, amber 80-89, primary/blue
<80) have no tier below "the default blue," and blue reads as "fine," not
"review this." Add a fourth band:

- score ≥ 90 → `emerald` (unchanged) — "Viral Potential"
- 80–89 → `amber` (unchanged) — "High Performing"
- 50–79 → `primary`/blue (unchanged treatment, just a narrowed range) — "Good Insight"
- score < 50 → **new** — `bg-destructive/15 text-destructive border-destructive/30`
  (the same destructive token already used for the `failed` clip-status pill
  and every error banner in this app — no new color introduced) — label
  **"Needs Manual Review"**.
  - Icon: reuse `AlertCircle` (the app's existing warning/error icon — see
    `ExportPanel.tsx`, `VideoDetailPage.tsx`) in place of `TrendingUp` for
    this band. Not `AlertTriangle` — stay consistent with the icon this app
    already uses for "something needs attention."
  - No `animate-pulse` on this icon — that's reserved for the top-tier
    flame's "hot" read; a review-needed indicator shouldn't look exciting.
  - The 50 cutoff is a starting point, not a derived constant — the real
    distribution depends on backend weights that don't exist yet. Make it a
    named constant in `virality.ts` (e.g. `REVIEW_THRESHOLD = 50`) so it's a
    one-line tune, and flag to founder/tester that it likely needs a
    calibration pass once real scores are visible — a middling clip (one
    clean boundary, a weak-ish hook) could plausibly land right at the edge;
    if early data clusters mediocre clips just above 50, lower the constant
    rather than rename the bands.
  - `bg-destructive/15` is already the `failed` clip-status pill's color
    (`ClipCard.tsx:20`) — a failed-render clip with a low score will show
    two red pills with different meanings on one card (status: failed,
    score: needs review). Considered, kept anyway: it's the only red
    semantic token in the app, and the two pills are spatially separated
    (top-left status vs. bottom-row score) with distinct text, so they
    don't read as a duplicate.
  - The tier can flip on refinement (blue at draft → red once framing comes
    back negative, or vice versa). That's expected — no transition
    animation, no "score changed" toast.

Also required in this same component — a **null/unscored state** (legacy
pre-migration clips, `virality_score = null` until the next edit or
re-render): never coerce to 0, never hide the badge.
  - Pill: neutral, matching `ClipCard`'s existing `draft`-status treatment
    (`bg-muted text-muted-foreground`, no tier border color), no numeric
    score, static icon. Text: **"Not yet scored"**.
  - Detail panel (`showDetails`): the three sub-score boxes each render
    `—` instead of a number, and the explanation line reads "This clip
    hasn't been scored yet — it'll be scored the next time it's edited or
    re-rendered." instead of `virality_reason`.

**2. Partial-vs-refined marker**

Placement: inside the pill itself, at **all sizes** (`sm`/`md`/`lg`), not
only the detail panel. Reason: `ClipCard.tsx` (the Clip Library grid, size
`sm`, no `showDetails`) is exactly where "a founder skimming the Clip
Library" — the story's own acceptance bar — needs to see this; the expanded
detail panel isn't rendered there at all.

- Add a third bullet segment to the pill, shown only while partial
  (`framing_score` is `null` and the clip hasn't completed a successful
  render): `• Estimate`, same muted/opacity-75 treatment as the existing
  `ratingLabel` segment. Once refined (`framing_score` populated), no tag —
  the pill goes quiet, matching how the rest of this app marks "done" (no
  badge = default; the exception state is the one that gets marked).
- Responsive: checked `ClipGrid.tsx` — cards render 1/2/3 per row
  (`grid-cols-1 sm:grid-cols-2 lg:grid-cols-3`), and the `sm`-size pill
  already shares its row with the Download pill in a tight `justify-between`
  footer (`ClipCard.tsx:105-110`). A third segment (icon + "Score 42/100" +
  "• Needs Manual Review" + "• Estimate") is too long for that row at the
  3-column width. **On `size === 'sm'` only:** drop the `ratingLabel` text
  segment (color already encodes the tier) and keep `Score {score}/100` +
  `• Estimate` when partial. `md`/`lg` keep all segments — those render in
  single-column headers/panels with more width.
- Detail panel (`showDetails`, `lg` only today): **delete** the "Wayin AI
  Score" span entirely, no replacement text in that slot — don't repurpose
  it as a second copy of the Estimate tag, since the pill above it
  (`ClipEditorPage.tsx:747` renders both the pill and the panel together in
  the same view) already carries that marker once; showing it twice is
  redundant. The `h4` "AI Virality Analysis" already labels the panel on its
  own.
- Detail panel's third sub-score box (today "Shorts Flow," the duration
  heuristic this story deletes) becomes the framing box: label **"Speaker
  Framing"**, value is not a percentage — it's `Confirmed` (framing_score
  populated + positive) / `Not confident` (populated, no subject found) /
  `Not checked` (still null — same label whether that's "hasn't rendered
  yet" or "rendered but a failed render left it null" per this story's own
  rule; don't say "Pending" — a failed render can leave this null
  permanently, not "in flight").

**3. "Wayin AI Score" header replacement**

Delete the span outright (see above) — not a rename. The panel already has
a real header ("AI Virality Analysis"), and the vacated slot's only other
candidate job (the partial/refined marker) now lives in the pill instead.
No product name, no replacement text needed in that slot.

**4. Bottom-tier label copy**

Rename `"Standard Clip"` → **`"Needs Manual Review"`**. Reads as an
instruction, not a shrug — matches the acceptance criteria's own phrasing
("review the clip by hand"). This is the new `ratingLabel` union member
replacing the deleted `'Standard Clip'`.

**Type-shape note for frontend-agent (so this isn't re-derived):** the
acceptance criteria says `ViralityScoreBadge` "still consumes the same
shape it does today" — that's the **prop signature**
(`insights: ViralityInsights` unchanged at all three call sites), not the
interface's member names verbatim. The interface's contents change:
- `score: number | null` (`null` → the unscored state above)
- `ratingLabel`: drop `'Standard Clip'`, add `'Needs Manual Review'`
- `engagementScore` → renamed `completenessScore` (matches the backend's
  renamed `completeness_score`)
- `flowScore` → replaced by a framing signal that is **not a 0-100
  number** — pass/fail/null, per the story's own definition of signal #3
  ("treat 'a SpeakerFraming was returned' as the full framing score and
  `None` as zero... do not invent a confidence scale it doesn't have").
  Whatever type frontend-agent picks (e.g.
  `framingStatus: 'confirmed' | 'not_confident' | 'not_checked'`), it must
  not be rendered as a percentage in the detail panel's third box.
- Add whatever field frontend-agent uses to signal "still partial" — this
  spec's behavior trigger is simply "`framing_score` is `null`"; map that
  through however the final type is shaped.

Scope check: no new component, no new file, no icon-set change beyond
swapping `TrendingUp` → `AlertCircle` for one band. Everything above lives
inside `ViralityScoreBadge.tsx`, `virality.ts`, and the two existing call
sites (`ClipCard.tsx`, `ClipEditorPage.tsx`).

---

#### Database (database-agent, 2026-09-06)

**Scope:** `Clip` model + migration only, per this story's split — scoring
logic (`backend-agent`) and UI (`frontend-agent`) are out of scope here and
untouched.

**Files touched:**
- `backend/app/models/clip.py` — added five nullable columns to `Clip`, no
  `server_default` on any of them (NULL is the intentional default per the
  story's Bounds section — a coerced 0/fake value would repeat the exact
  problem this story exists to fix):
  - `virality_score: Mapped[float | None]` — `Float`, nullable
  - `hook_score: Mapped[float | None]` — `Float`, nullable
  - `completeness_score: Mapped[float | None]` — `Float`, nullable. **Net-new
    column, not a rename**: grepped the model file and all five prior
    migrations before adding this — no `engagement_score` column exists in
    the live `clips` table. The frontend's dead `engagement_score` field
    (`frontend/src/types/index.ts:79-82`) was never backed by a database
    column, so there's nothing to rename at the schema layer; frontend-agent
    renames the TS field name only.
  - `framing_score: Mapped[float | None]` — `Float`, nullable
  - `virality_reason: Mapped[str | None]` — `Text`, nullable
- `backend/alembic/versions/9f3c1a7d5e2b_clip_virality_scores.py` — new
  migration, hand-written (no reachable local Postgres to autogenerate
  against, same constraint the last two migrations in this repo noted).
  - **Revision ID:** `9f3c1a7d5e2b`
  - **down_revision:** `e276d71b9110` (confirmed via `alembic heads` before
    writing — this was the actual head, the `clip_broll_placement`
    migration from the in-flight B-roll story).
  - `upgrade()`: five `op.add_column("clips", ...)` calls, all
    `nullable=True`, no `server_default`. `downgrade()`: five
    `op.drop_column` calls in reverse order.
- `backend/app/schemas/clip.py` — added all five fields to `ClipResponse`
  only, in the same types as the model (`float | None` / `str | None`), so
  the response actually serializes them once backend-agent populates them.

**Deliberately NOT added to `ClipUpdateRequest`:** these five fields are
server-computed and read-only from the client's perspective. Making
`virality_score` (etc.) client-writable via `PUT /clips/{id}` would let a
client set an arbitrary fake score again — exactly the problem this story
exists to kill. The story's AC is explicit that boundary edits trigger
*server-side* recomputation, not a client-supplied value. backend-agent:
write these columns directly in the update/recompute code path, not via the
request schema.

**Scale note (underspecified in the story otherwise, stating it here so it
isn't re-derived or guessed differently by the two consumers):**
`virality_score`, `hook_score`, `completeness_score` are all on a **0-100**
scale, not 0-1 — the Designer's band cutoffs (`<50` Needs Manual Review,
`50-79`, `80-89`, `>=90`) read `virality_score` directly on that scale. No
DB-level CHECK constraint added (deliberately — a bad write should surface
in backend-agent's own tests, not as a Postgres 500); staying in range is
the scoring service's responsibility, not enforced at the schema layer.

**`framing_score` encoding — read this before implementing the scoring
service, don't re-derive it:**
- `null` — not yet checked. Three distinct paths land here, all meaning the
  same thing to the reader: (1) still `draft`, hasn't rendered yet; (2) a
  `failed` render left it unset (partial score untouched, per the story's
  own rule); (3) a boundary edit via `PUT /clips/{id}` invalidated a
  previously-computed value on an already-`ready` clip, per the AC that a
  stale framing result must not silently keep describing new boundaries.
  `null` on a `ready` clip is a legitimate state from path 3, not a bug.
- `0.0` — checked, `compute_speaker_framing()` returned `None` (no
  confident subject found). Still a nullable float column, but `0.0` is a
  real, distinct value from `null` here, not "unscored."
- `1.0` — checked, `compute_speaker_framing()` returned a `SpeakerFraming`.
- This is a **two-value signal on a nullable float**, not a gradient — do
  not average it, do not store any value other than `null`/`0.0`/`1.0`.
  Corroborated directly by the Designer subsection's detail-panel spec
  (three states: `Confirmed` = populated + positive, `Not confident` =
  populated + no subject, `Not checked` = null) — backend-agent's write
  path and frontend-agent's read path should both key off exactly these
  three states, nothing finer-grained.

**No index added.** No query pattern in this story filters or sorts by any
of these five columns — clips are already fetched per `video_project_id`/
`user_id` and the score renders per-row in an already-loaded list. Add one
later only if a real query pattern needs it (e.g. a future "sort library by
score" feature), not speculatively.

**Verification run (in order):**
1. `alembic heads` → confirmed `e276d71b9110 (head)` before writing
   `down_revision`.
2. `alembic upgrade head` against the real dev Postgres (`DATABASE_URL`) →
   applied cleanly: `Running upgrade e276d71b9110 -> 9f3c1a7d5e2b, clip
   virality scores`. No errors.
3. Verified via SQLAlchemy engine query against
   `information_schema.columns` (psql binary not on PATH in this shell) —
   confirms exactly what was expected in production, not just what was
   written:
   ```
   completeness_score  | double precision | YES | (null)
   framing_score       | double precision | YES | (null)
   hook_score          | double precision | YES | (null)
   virality_reason     | text             | YES | (null)
   virality_score      | double precision | YES | (null)
   ```
   All five nullable, no default — matches the story's legacy-row backfill
   requirement exactly.
4. `alembic downgrade -1` then `alembic upgrade head` → both ran clean; the
   five columns disappeared after downgrade (confirmed via
   `information_schema.columns`, empty result) and were back with correct
   nullability after re-upgrade. Rollback path is real, not just assumed
   from reading the file.
5. `pytest backend/tests -v` → **267 passed**, 0 failed (same count as the
   B-roll story's last full-suite baseline in this file — these are
   additive nullable columns plus response-schema fields, not behavior
   changes, so no regression expected or found). Specifically checked
   `test_clips.py`/`test_broll.py`/etc. for any `response.json() == {...}`
   exact-body assertions that five new `ClipResponse` keys could break —
   found none touching `Clip`'s response shape (`test_broll.py`'s two exact-
   body assertions are against B-roll search results, unrelated).

**Not touched, per scope:** scoring logic, `clip_service.py`'s business
logic, `video_render.py`, `highlight_detection.py`, `reframe.py`, any
frontend file, `ClipUpdateRequest`.

Handing off to `backend-agent` to build the scoring service (weights,
`virality_reason` composition, recomputation-on-edit, refinement-on-render)
against this schema, and to `frontend-agent` to consume the five new
`ClipResponse` fields per the Designer spec above.

---

#### Frontend (frontend-agent, 2026-09-06)

**Scope:** consumed the fixed API contract (five new `ClipResponse` fields)
per Designer's spec, built directly against `#### Database`'s schema without
waiting on `backend-agent`'s scoring service, which is in flight in
parallel.

**Files touched:**
- `frontend/src/types/index.ts` — `Clip`'s dead optional fields replaced
  with the real, required-and-nullable contract:
  `virality_score`/`hook_score`/`completeness_score`/`framing_score`
  (`number | null`) and `virality_reason` (`string | null`). Net-new
  `completeness_score` (no `engagement_score` rename at this layer — the
  Database subsection confirmed there was never a matching DB column to
  rename). Made required (not optional) rather than optional-and-nullable:
  grepped for `Clip` object literals repo-wide first (`grep -rln
  "video_project_id" src | grep -i "test|mock|fixture"`) — only one fixture
  file existed (`ClipCard.test.tsx`), so tightening the type to match
  `ClipResponse` exactly (always present, nullable) was the cheaper, truer
  option; updated that one fixture.
- `frontend/src/lib/virality.ts` — deleted `computeViralityInsights` and its
  entire fake-scoring math (keyword list, duration-bucket heuristic, the
  `Math.max(65, Math.min(99, ...))` floor/ceiling, fixed per-band
  explanation strings). Kept only score→label/color mapping: `getRatingLabel`
  (pure function, new `REVIEW_THRESHOLD = 50` named constant per Designer's
  note that it's a starting point, not a derived value) and a new
  `clipToViralityInsights(clip)` helper that builds a `ViralityInsights`
  object directly from a clip's real backend fields — shared by both call
  sites instead of duplicating the mapping. `ViralityInsights`'s members
  renamed per Designer's type-shape note: `score: number | null`,
  `completenessScore` (was `engagementScore`), `framingStatus: 'confirmed' |
  'not_confident' | 'not_checked'` (was the percentage `flowScore` — pass/
  fail per the story's own definition, not a gradient; guarded
  `null`/`undefined` explicitly before the `> 0` check so a real `0.0`
  isn't mistaken for "not checked"), `ratingLabel` drops `'Standard Clip'`
  and adds `'Needs Manual Review'` (and is `null` when `score` is `null`).
  `getExpectedShortsCount` untouched, per scope.
- `frontend/src/components/clips/ViralityScoreBadge.tsx` — added the 4th
  color band (score < 50, `bg-destructive/15`/`AlertCircle`, no pulse,
  label "Needs Manual Review") and a null-score neutral state ("Not yet
  scored", `bg-muted`, no numeric score, all three detail-panel boxes
  render `—`, explanation replaced with the fixed "hasn't been scored yet"
  copy) — both at all sizes. Added the "Estimate" pill segment (shown only
  when `score !== null && framingStatus === 'not_checked'`), and dropped
  the `ratingLabel` text segment at `size === 'sm'` only (numeric score +
  Estimate still show there) per Designer's `ClipGrid` width note. Deleted
  the "Wayin AI Score" header span outright, no replacement. Third
  sub-score box relabeled "Speaker Framing", renders
  `Confirmed`/`Not confident`/`Not checked` text instead of a percentage.
  **Left the second box's visible label as "Retention"** (unchanged) even
  though it now displays `completeness_score` rather than an engagement
  metric — Designer's spec only called out renaming the third box; flagging
  back rather than improvising a new label unilaterally. Added `AlertCircle`
  to the icon import (the file never had `AlertTriangle`); no new
  component, no new file, per Designer's scope check. The 4th band's color
  tier is derived from `ratingLabel` (not a second `score < 50` comparison
  in this file), so it can't drift out of sync with `REVIEW_THRESHOLD` in
  `virality.ts` if that constant is retuned later.
- `frontend/src/components/clips/ClipCard.tsx` and
  `frontend/src/pages/ClipEditorPage.tsx` — both call sites now call
  `clipToViralityInsights(clip)` instead of the deleted
  `computeViralityInsights(clip.caption_text || clip.title, duration)`; no
  more title/duration text feeding the score. `duration`/`rawDuration`
  locals kept where still used elsewhere on those pages (formatting,
  preview label) — untouched beyond the one call-site swap.
- `frontend/src/components/clips/__tests__/ClipCard.test.tsx` — fixture
  updated with the five new required fields; added a null-score ("Not yet
  scored") test and a sub-50-band test (asserting `"Score 32/100"` — not the
  `"Needs Manual Review"` text, since `ClipCard` renders at `size="sm"`,
  which drops that text segment by spec).
- `frontend/src/lib/__tests__/virality.test.ts` (new) — `getRatingLabel`
  band coverage (null → null, <50 → "Needs Manual Review", existing
  thresholds unchanged), `clipToViralityInsights` discrimination test
  (two clips with different sub-scores produce different scores/labels/
  explanations, not a coincidental convergence), null → "not yet scored"
  mapping, and `framing_score` → `framingStatus` (null/0/1 → not_checked/
  not_confident/confirmed).
- `frontend/src/components/clips/__tests__/ViralityScoreBadge.test.tsx`
  (new) — null-state render, sub-50 band render at `size="md"` (where the
  label text does show), Estimate-marker appears/disappears with
  `framing_score`, `sm` drops the label text but keeps the score, and the
  detail panel's framing box renders pass/fail text, not a percentage.

**Not touched, per scope:** no backend/migration files, no
`team/backlog.md` Database/Backend subsections, no B-roll frontend files.

**Verified:**
- `npm run type-check` (`tsc -b --noEmit`) — clean, no errors.
- `npm run lint` (`oxlint`) — no new warnings/errors from any touched file
  (pre-existing warnings in unrelated files unchanged).
- `npm test` (`vitest run`) — 18 test files, 98 tests, all passing,
  including the 9 new virality/badge tests above.

**Not verified — flagging explicitly:** no browser tool available in this
session, so the golden path was not exercised in an actual browser. Also,
even if it had been: `backend-agent`'s scoring service is still in flight in
parallel, so a live `GET /clips` right now would return `null` for all five
fields on every clip — a dev-server pass at this moment could only ever show
the "Not yet scored" state, not the four real score bands. `tester` should
hold end-to-end/visual verification of the four bands and the
partial→refined transition until `backend-agent` hands off and real scores
exist to render. Also carrying forward Designer's own calibration flag:
`REVIEW_THRESHOLD = 50` in `virality.ts` is a starting point, not a derived
constant — once real scores are visible, if mediocre clips cluster just
above 50, founder/tester should expect the constant to be lowered rather
than the bands renamed.

Handing off to `tester`.

---

#### Backend (backend-agent, 2026-09-06)

**Scope:** the scoring service itself (hook/completeness/framing
sub-scores, the composite `virality_score`, `virality_reason`), wired into
the three pipeline points the story calls out: clip generation, `PUT
/clips/{id}`, and the render pipeline's `ready` transition. Built directly
against `#### Database`'s schema (exact `framing_score` null/0.0/1.0
encoding) and read `#### Frontend`'s handoff first to confirm the contract
it already consumes (`framingStatus` guards null/undefined before `> 0`,
so `0.0` reads as `not_confident`, matching what this service writes).

**Files touched:**
- `backend/app/services/clip_service.py` — all new scoring logic lives
  here (no new `virality_service.py` module: the completeness/hook checks
  reuse `_sentences_in`/`_extend_to_sentence_boundary`'s boundary logic
  already private to this file, and a separate module importing back into
  `clip_service` for those helpers would create a circular import for no
  real benefit — keeping it in one file is the smaller, more discoverable
  diff). Added:
  - `_BOUNDARY_MATCH_TOLERANCE_SECONDS = 0.05` — a boundary compared
    exactly would spuriously fail against a value that only differs by
    float rounding (this module itself stores `start_time`/`end_time` via
    `round(..., 2)`, and a client's drag-trim edit is arbitrary float
    precision).
  - `_HOOK_OPENING_WEIGHT = 0.6` / `_HOOK_PAYOFF_WEIGHT = 0.4` — the
    opening two seconds decide whether anyone stays (same rationale
    `highlight_detection`'s own module docstring gives its `_HOOK_WEIGHT`
    being its largest single term), so the opening line's `hook_score`
    carries the majority share of the hook sub-score; the window's
    insight-keyword density (`_payoff_score`) still counts for something —
    a strong opener that trails into filler shouldn't score identically to
    one that follows through.
  - `_COMPLETENESS_BOTH_CLEAN = 100.0` / `_COMPLETENESS_ONE_CLEAN = 55.0` /
    `_COMPLETENESS_NEITHER_CLEAN = 20.0` — three tiers per the story's
    Bounds section. `20.0` (not `0.0`) so a transcript with no terminal
    punctuation anywhere doesn't zero out a clip that may otherwise be
    fine on hook/framing.
  - `_HOOK_WEIGHT_PARTIAL` / `_COMPLETENESS_WEIGHT_PARTIAL` — **derived**,
    not hand-picked: `_HOOK_WEIGHT_REFINED / (_HOOK_WEIGHT_REFINED +
    _COMPLETENESS_WEIGHT_REFINED)` = `0.4 / 0.75` ≈ `0.5333`, and its
    complement ≈ `0.4667`. This is the actual renormalization of the
    refined weights over just hook+completeness the story requires (an
    even 0.5/0.5 split would have been the separately-invented pair the
    story explicitly prohibits) — computing it from the refined constants
    also means it can't drift out of that ratio if the refined weights are
    ever retuned.
  - `_HOOK_WEIGHT_REFINED = 0.4` / `_COMPLETENESS_WEIGHT_REFINED = 0.35` /
    `_FRAMING_WEIGHT_REFINED = 0.25` — framing is a binary pass/fail signal
    (per the Database handoff's exact encoding), not a graded one, so it
    refines the score rather than dominating it: hook + completeness
    (0.75 combined) outweigh it, per the story's own bound.
  - `_HOOK_WEAK_THRESHOLD = 35.0` / `_HOOK_STRONG_THRESHOLD = 70.0` —
    thresholds for naming the hook sub-signal explicitly in
    `virality_reason` rather than folding it silently into the number;
    completeness's thresholds just key off its three fixed tier values
    directly, since it never lands anywhere else.
  - `_is_terminal_end`/`_is_terminal_start` — the exact
    `seg.text.strip().endswith((".", "!", "?"))` / "first segment or
    preceding segment ended in terminal punctuation" checks
    `_extend_to_sentence_boundary`/`_clamp_start_to_boundary` already use,
    reused read-only against the clip's *current* `start_time`/`end_time`
    rather than reimplemented.
  - `_completeness_subscore`, `_opening_text`, `_hook_subscore`,
    `_composite_virality_score`, `_virality_reason` — the actual
    computation, composed from the constants above.
  - `score_clip_partial(clip, segments)` — sets
    `hook_score`/`completeness_score`/`virality_score`/`virality_reason`
    from the clip's current boundaries; never touches `framing_score`
    (callers own invalidating that).
  - `refine_clip_with_framing(clip, framing_score)` — takes the raw
    `0.0`/`1.0` signal, stores it on `Clip.framing_score` unchanged (per
    the Database handoff's "never store any value other than
    null/0.0/1.0"), and recomputes `virality_score`/`virality_reason` using
    that value scaled to 0-100 (`1.0 → 100`, `0.0 → 0`) purely for the
    composite formula's own scale.
  - `create_clips_from_highlights` — every new clip gets
    `score_clip_partial(clip, all_segments)` called right after
    construction (reusing the `all_segments` list already fetched for
    boundary-snapping), before `db.add`. `framing_score` stays `null` (the
    column's own default — no explicit write needed).
  - `update_clip` — a `start_time`/`end_time` change in the payload now
    re-queries the project's transcript segments, calls
    `score_clip_partial` against the *new* boundaries, and sets
    `clip.framing_score = None` unconditionally (even on an already-`ready`
    clip) to invalidate a stale framing result. Fields other than the
    boundaries (caption text, framing_mode, etc.) do not trigger this —
    verified by a dedicated test.
- `backend/app/services/video_render.py` — wired the render pipeline's
  refinement pass:
  - `_frame_9x16` now returns `(video_stream, speaker_framing)` instead of
    just the stream, so the `auto`/`speaker_focus` path's own
    `compute_speaker_framing` call can be reused for scoring instead of
    calling it twice. `_run_ffmpeg` propagates that value up as its return.
  - `_render_and_persist`: on the success path (just before the `ready`
    transition), reuses the `speaker_focus` clip's already-computed
    `speaker_framing` result, or calls `compute_speaker_framing` directly
    for `dynamic_blur`/`fit` clips (cheap/cached per its own docstring, so
    this is one extra call, not a new analysis pass) — for every clip,
    regardless of `framing_mode`, per the story's explicit instruction.
    Converts the result to `1.0`/`0.0`, backfills `hook_score`/
    `completeness_score` first via `score_clip_partial` if either is
    `None` (a legacy pre-migration clip being re-rendered — one of the
    story's two allowed backfill triggers), then calls
    `refine_clip_with_framing`. Every `failed`-transition branch (missing
    source, invalid trim window, ffmpeg missing/error, unexpected
    exception) returns *before* this code runs, so a failed render
    provably never touches any score field — verified by a dedicated test,
    not just by inspection.
- `backend/tests/test_video_render.py` — fixed one existing call site
  (`TestSplitScreenFraming._graph`) for `_frame_9x16`'s new tuple return
  (`stream, _ = ...`), and a stray line accidentally split off
  `test_a_silent_source_still_exports` during editing was restored to its
  original test (no behavior change, self-caught before running the
  suite). Added `TestViralityScoreRefinement`: refines a `dynamic_blur`
  clip's score on a successful render (not just `speaker_focus`), confirms
  a no-confident-subject render scores framing `0.0`, confirms the default
  `speaker_focus` path reuses `_frame_9x16`'s own `compute_speaker_framing`
  call instead of calling it a second time (asserted via
  `mock.call_count == 1`, not just inspection), and confirms a `failed`
  render (no `source_file_path` at all) leaves a pre-set partial score
  completely untouched.
- `backend/tests/test_clips.py` — added `TestViralityScorePartial`: a
  freshly generated clip has a real, non-null partial score with null
  `framing_score`; two clips built from meaningfully different hook/
  completeness signals score >=30 points apart (not a rounding artifact)
  and get different `virality_reason` strings; editing `end_time` via
  `PUT /clips/{id}` on an already-`ready`, already-framing-scored clip
  recomputes the partial score and nulls `framing_score`; editing a
  non-boundary field (`caption_text`) leaves an existing `framing_score`
  untouched.

**Not touched, per scope:** `highlight_detection.py`/`reframe.py` internals
(called read-only via their existing public functions), any frontend file,
B-roll files, `ClipUpdateRequest` (these five fields stay server-computed
only, per the Database handoff's explicit note).

**Verification run:**
- `pytest backend/tests -v` → **275 passed**, 0 failed (267 prior baseline
  + 8 new: 4 in `test_clips.py`, 4 in `test_video_render.py`).
- `pytest backend/tests/test_video_render.py -v` → **25 passed** (21 prior
  + 4 new), ffmpeg available in this environment so the real pipeline ran
  end to end, not skipped.
- `ruff check` on every file this story touched
  (`app/services/clip_service.py`, `app/services/video_render.py`,
  `tests/test_clips.py`, `tests/test_video_render.py`) → clean. (A
  pre-existing `E501` on an unrelated, untouched line in
  `test_video_render.py`'s `TestRenderClip` parametrize list, from before
  this story, still fires on a repo-wide `ruff check backend/app` +
  `backend/tests`; confirmed via `git diff` that line is unchanged by this
  story's diff.)
- Self-review caught one real defect before handoff: the first draft of
  `_HOOK_WEIGHT_PARTIAL`/`_COMPLETENESS_WEIGHT_PARTIAL` was a hand-picked
  0.5/0.5 even split, which is exactly the "separately-invented pair" the
  story's Bounds section prohibits — the true renormalization of
  `_HOOK_WEIGHT_REFINED`/`_COMPLETENESS_WEIGHT_REFINED` over just those two
  is ≈0.5333/0.4667. Fixed by deriving the partial constants from the
  refined ones at module load time (`_HOOK_WEIGHT_REFINED /
  (_HOOK_WEIGHT_REFINED + _COMPLETENESS_WEIGHT_REFINED)`, and its
  complement) instead of hardcoding either pair, so they can't drift out
  of ratio if the refined weights are retuned later. Re-ran the full suite
  after the fix (counts above are post-fix) — the discrimination test's
  margin only grew (weak clip's partial score moves from 50.0 to ~46.67),
  well clear of its `>= 30` assertion.

**Frontend contract note (nothing to re-derive, confirming what
`#### Frontend` already built against):** `framing_score` is always
exactly `null`/`0.0`/`1.0` on write — never averaged, never any other
float — so `clipToViralityInsights`'s `> 0` guard maps this service's
output to `not_checked`/`not_confident`/`confirmed` exactly as that
section describes. Real (non-null) scores will now appear on the next
`GET /clips` after this lands — the "Not yet scored" state Frontend
verified against is retained for legacy pre-migration rows and any clip
between generation and its first edit/render only.

Handing off to `tester`.

---

#### QA (tester, 2026-09-06)

**Scope:** re-verified all four agents' work end to end against the story's
own acceptance criteria -- did not just re-run the counts each agent
reported. Read the full story + Designer/Database/Backend/Frontend
subsections, then read the actual code (`clip_service.py`, `video_render.py`,
`app/models/clip.py`, `app/schemas/clip.py`, `virality.ts`,
`ViralityScoreBadge.tsx`, `ClipCard.tsx`, `ClipEditorPage.tsx`,
`types/index.ts`) and hand-traced the data flow and the weight math, rather
than trusting the handoffs' own descriptions of what the code does.

**Test suite re-run (independent):**
- `pytest backend/tests -v` -> **275 passed**, 0 failed. Matches backend-agent's count.
- `npm test` (`vitest run`) -> **18 test files, 98 tests, all passing**. Matches frontend-agent's count.
- `npx tsc --noEmit` -> clean, no errors.
- `npm run lint` (`oxlint`) -> only pre-existing warnings in files this story didn't touch; nothing new.
- `alembic heads` -> single head (`9f3c1a7d5e2b`), confirmed the five migrations form one linear chain, no branch.
- Live dev Postgres (`\d clips` / `SELECT ... FROM clips`): confirmed the five
  columns exist, nullable, no default, and that the existing pre-migration
  clip rows (ids 302, 304-312) all carry `virality_score = NULL` today --
  the legacy-row acceptance criterion isn't just schema-correct, it's true
  of real rows in the real database right now.

**Cross-agent integration verdict (the story's own highest-risk item):**
**PASS.** Traced `Clip` model -> `ClipResponse` -> frontend `Clip` type ->
`clipToViralityInsights` -> `ViralityScoreBadge` props by hand, field by
field:
- All five DB columns (`virality_score`, `hook_score`, `completeness_score`,
  `framing_score` all `float | None`; `virality_reason` `str | None`) are
  declared identically in `ClipResponse` and are always serialized (never
  omitted), confirmed both by reading the schema and by the live DB query
  above returning real `null`s through would-be JSON.
- Frontend's `Clip` type in `types/index.ts` declares the same five fields
  as required-but-nullable, matching `ClipResponse` exactly (not
  optional-and-sometimes-absent) -- `tsc --noEmit` clean is real evidence
  here, since a shape mismatch at any object-literal construction site
  (fixtures included) would have failed the build.
- `framing_score`'s `null`/`0.0`/`1.0` encoding maps to `framingStatus`
  correctly: `clipToViralityInsights`'s `framingStatusFromScore` guards
  `null`/`undefined` explicitly before the `> 0` check (`frontend/src/lib/virality.ts:44-49`),
  so a real `0.0` (checked, no confident subject) reads as `'not_confident'`,
  not `'not_checked'` -- verified this is not a `!framingScore` truthy check,
  which would have collapsed `0.0` into "not checked" and silently hidden a
  real negative signal.
- `REVIEW_THRESHOLD = 50` and all four band boundaries in
  `getRatingLabel` (>=90 Viral Potential, >=80 High Performing, >=50 Good
  Insight, else Needs Manual Review) match Designer's spec exactly, numbers
  and labels both.
- No dead scoring code survives: grepped the repo for
  `computeViralityInsights`, `engagement_score`, `flowScore`,
  `Standard Clip`, `VIRAL_HOOK_KEYWORDS` -- zero hits in `frontend/src` or
  `backend/app` (one unrelated `"Wayin AI Engine"` string on the marketing
  `HomePage.tsx`, outside this story's scope -- not the clip detail panel's
  header, which is confirmed deleted).

The naming/type risk the launch brief called out did not materialize. The
integration risk that *did* materialize is on the render side, not the
schema side -- see Bug 1 below.

**Weight-math sanity check (hand-computed against the real functions, not
trusted from the docstrings):**

| case | hook | completeness | framing | expected | actual |
|---|---|---|---|---|---|
| partial weights sum | - | - | - | 1.0 | 0.5333+0.4667=1.0 (confirmed via `_HOOK_WEIGHT_PARTIAL + _COMPLETENESS_WEIGHT_PARTIAL`) |
| refined weights sum | - | - | - | 1.0 | 0.4+0.35+0.25=1.0 |
| strong clip, partial | 100.0 | 100.0 | null | 100.0 | **100.0** (ran `score_clip_partial` directly) |
| weak clip, partial | 0.0 | 55.0 | null | 0.4667*55=25.67 | **25.67** |
| refined, hook=80/comp=100/framing confirmed | 80 | 100 | 100 | 0.4*80+0.35*100+0.25*100=92.0 | **92.0** (matches `test_render_refines_score_regardless_of_framing_mode`) |
| refined, hook=80/comp=100/framing not confident | 80 | 100 | 0 | 0.4*80+0.35*100+0=67.0 | **67.0** (matches `test_render_with_no_confident_subject_scores_framing_zero`) |

All five check out exactly. The renormalized partial-weight derivation
(`_HOOK_WEIGHT_REFINED / (_HOOK_WEIGHT_REFINED + _COMPLETENESS_WEIGHT_REFINED)`)
is real, not just described as real in the handoff -- confirmed by reading
the module-load-time expression, not the comment above it.

**Per-acceptance-criterion results:**

1. **New draft clip gets real hook+completeness score at creation, framing_score null.** PASS.
   `create_clips_from_highlights` calls `score_clip_partial` before `db.add`;
   `test_generated_clip_gets_a_real_partial_score_with_null_framing` covers
   it and I re-ran it independently.
2. **Render success refines the score regardless of framing_mode; failed render leaves partial score untouched.** PASS with an open bug (see Bug 1).
   The refinement logic itself is correct and covered for `speaker_focus`,
   `dynamic_blur`, and a no-confident-subject case, and all five `failed`
   branches provably return before the scoring block runs (confirmed by
   reading every branch, not just the one under test). But see Bug 1: the
   `dynamic_blur`/`fit` path's new `compute_speaker_framing` call is
   unguarded and sits *after* a successful render, which is a different and
   worse failure mode than the pre-existing `speaker_focus` path.
3. **Two meaningfully-different clips must not converge on the same score by coincidence.** PASS.
   Hand-computed via the real functions: strong clip scores 100.0, weak
   clip scores 25.67 partial (19.25 refined) -- a ~74-80pt gap, not a
   rounding artifact. `virality_reason` differs between them and is
   non-templated (see next item).
4. **Sub-50 clip lands in the lowest band, and that band reads as an instruction to review.** PASS.
   `< 50` -> `"Needs Manual Review"`, `bg-destructive/15` + `AlertCircle`,
   confirmed in `ViralityScoreBadge.tsx` and its test.
5. **`virality_reason` differs between clips with different sub-scores, and isn't templated.** PASS overall, with an open bug (see Bug 2).
   The strong/weak clip example above produces genuinely different,
   sub-score-driven text ("Strong hook, sentence completeness." vs. "Weak
   hook -- review before publishing."). But there's a reproducible band
   where the *reason* contradicts the *label* -- see Bug 2.
6. **Editing start_time/end_time recomputes partial score and nulls framing_score, even on a `ready` clip.** PASS.
   Verified directly in `update_clip`'s code (unconditional
   `clip.framing_score = None` on any boundary change) and via
   `test_editing_boundaries_recomputes_partial_score_and_nulls_framing`.
   Also confirmed by grepping the whole backend for other writers of
   `clip.start_time`/`clip.end_time`: `create_clips_from_highlights` and
   `update_clip` are the only two -- no other router/service can move a
   clip's boundaries without going through the recompute-and-invalidate
   path, so this isn't a hole that only holds for the one tested endpoint.
7. **Legacy pre-migration clips render "Not yet scored," not coerced to 0 or hidden.** PASS.
   Confirmed at three layers: DB model (no `server_default`, nullable),
   live DB query showing real NULL rows today, and
   `ViralityScoreBadge.tsx`'s explicit `insights.score === null` branch
   (neutral pill, `—` sub-scores, fixed explanation) plus its test.
8. **Frontend's `REVIEW_THRESHOLD=50` and band boundaries match Designer's spec.** PASS.
   Verified numerically above -- exact match, not approximate.
9. **Full backend + frontend suites pass, with the required new test coverage.** PASS.
   Re-run independently (275 / 98), and confirmed by reading the actual
   test bodies (not just their names) that the discrimination test asserts
   a real >=30pt gap from hand-computable sub-scores, not a mocked
   convergence.

**Open bugs (not fixed, per QA scope) -- routed to backend-agent unless noted:**

**Bug 1 (backend-agent, `video_render.py`, moderate-to-high severity):**
in `_render_and_persist`, the framing refinement call for non-`auto`
framing modes is unguarded:
```python
if framing_mode_str == "auto":
    framing_result = speaker_framing_result   # computed inside the earlier try/except
else:
    framing_result = compute_speaker_framing(...)   # NOT inside any try/except here
```
This call happens *after* `_run_ffmpeg` has already succeeded and the
output MP4 already exists on disk. If `compute_speaker_framing` raises for
any reason it hasn't already defended against internally (it does catch
its own probe/analysis exceptions and return `None` in the paths I read,
but the post-`_analyse` shot/face/conversation logic in
`reframe._compute_framing` is not fully wrapped), the exception propagates
to `render_clip`'s outer `except Exception -> _mark_failed_best_effort`,
which marks the clip `failed` and never sets `video_file_path` or extracts
a thumbnail -- **a clip whose render actually succeeded gets reported to
the user as failed**, purely because of a scoring-only call. This is a new
risk this story introduces for `dynamic_blur`/`fit` clips specifically:
before this story those framing modes never called
`compute_speaker_framing` at all, so this failure mode didn't exist for
them; for `speaker_focus`/`auto` clips the same call already happens, but
*before* the render, so a failure there correctly produces no file rather
than discarding a completed one. `_extract_thumbnail` right below this same
function already uses the defensive pattern (try/except, log-and-continue)
that this call is missing. Recommend wrapping the `else` branch the same
way, defaulting to `framing_score = 0.0`/`framing_score = None`-preserved
on failure rather than letting it fail the whole render. Flagging to
backend-agent (owns `video_render.py`) -- not fixed here, per QA scope.

**Bug 2 (backend-agent, `clip_service.py`, moderate severity, reproducible):**
`_virality_reason`'s fallback string ("Middling signals across the board --
no standout strength or weakness.") fires for a real, non-rare partial-score
band. Hand-computed and confirmed by executing the actual functions:

| hook | completeness | virality_score | rating band | virality_reason |
|---|---|---|---|---|
| 35.0 | 55.0 | 44.33 | Needs Manual Review | "Middling signals across the board -- no standout strength or weakness." |
| 40.0 | 55.0 | 47.0 | Needs Manual Review | (same) |
| 45.0 | 55.0 | 49.67 | Needs Manual Review | (same) |

`completeness = 55.0` (one clean edge -- the middle tier, not a rare
outcome) never crosses either of `_virality_reason`'s completeness
thresholds (`<= 20` weak, `>= 100` strong), and `hook` in `[35, 45.6)`
crosses neither hook threshold either (`< 35` weak, `>= 70` strong) while
still producing a sub-50 composite score. The result: a clip the badge
tells the founder to manually review, with an explanation claiming there is
nothing to review. This is exactly the failure mode the story exists to
kill (fabricated/generic prose), just relocated from "always" to "one
specific, non-rare band" -- worth a real fix (e.g., naming the lower of the
two sub-scores when neither crosses a threshold), not a rounding-error to
ignore. Flagging to backend-agent -- not fixed here, per QA scope.

**Open bug (frontend-agent, `ViralityScoreBadge.tsx`, cosmetic but
trust-relevant):** the detail panel's second sub-score box is still
labeled **"Retention"** while it now renders `completeness_score` (sentence-
boundary cleanliness), a metric that has nothing to do with audience
retention. Frontend-agent flagged this back rather than improvising a
label unilaterally, which was the right call, but on a story about a
founder trusting what a number literally means, a box asserting the wrong
metric name is a smaller version of the exact problem this story exists to
fix (label claims something the computation doesn't measure). Not blocking
on its own (the math and the number shown are both correct), but routing
to Designer/frontend-agent for a one-word relabel rather than leaving it
parked indefinitely.

**Calibration observation (not a bug, upgrading Designer's own flag with
measured evidence):** Designer's note worried scores might cluster
*just above* `REVIEW_THRESHOLD=50`, meaning mediocre clips could slip
through as reviewable. My hand-computation found the opposite risk is at
least as real: `hook_score` saturates to 100.0 from a **single 7-word
question** (`min(hits/2.0, 1.0)` needs only two pattern hits), and
`_payoff_score` saturated at 5 hits over 17 words in the same fixture --
an ordinary clip with one question-opener and a couple of insight words
can hit the numeric ceiling. For a founder using this score to *skip*
review, the dangerous direction is a merely-decent clip scoring as high
as a genuinely exceptional one, not a mediocre one landing just above 50.
Recommend the founder/backend-agent watch top-band saturation once real
clips flow through, not only the 50-cutoff Designer already flagged.

**Not verified — flagging explicitly:** no browser automation tool is
available in this session, so the four rating bands and the
partial-to-refined visual transition were not exercised in an actual
running browser. In their place: the full data-flow hand-trace above, the
component-level tests (which do render real DOM via `@testing-library/react`
and assert on visible text), and a live query against the real dev
database's legacy rows. This is the same limitation frontend-agent
disclosed for the same reason; nothing here contradicts what a browser
check would show, but it is inferred from code + component tests + live
data, not observed end-to-end in a browser.

**Overall recommendation:** the scoring is real, server-computed, weight
math checks out exactly, the four-agent handoff lines up cleanly at every
schema/type boundary, and the acceptance criteria substantively pass. Given
the P0/trust-critical framing (founder publishing without manual review),
I recommend **Bug 1 (render-marked-failed-on-a-scoring-side-effect) be
fixed before release** -- it's a regression risk in Export & Publish
triggered by this story, and "a good render silently reported as failed"
undermines trust in the opposite direction from what this story is meant to
fix. Bug 2 (templated fallback reason in a real sub-50 band) should also be
fixed before release given the story's explicit bar that `virality_reason`
must never read as fabricated. The "Retention" label and the calibration
observation are legitimately deferrable to a fast follow-up, not blockers.

This is a QA test-plan-and-results report only -- **not** a release
sign-off. Per governance, release approval is the founder's call, not
QA's or any agent's. Awaiting founder go/no-go, and awaiting backend-agent's
fix (or the founder's explicit acceptance of the risk) on Bug 1 before this
goes to DevOps.

#### Fix (backend-agent, 2026-09-06)

Both bugs QA found above are fixed. Scope stayed inside
`backend/app/services/video_render.py` and `backend/app/services/clip_service.py`
(plus their test files) per the fix task's own scope -- no frontend,
migration, or model changes.

**Bug 1 -- `video_render.py`, `_render_and_persist`:** the framing
refinement block (the `compute_speaker_framing` call for `dynamic_blur`/
`fit` clips, `score_clip_partial`, and `refine_clip_with_framing`) that
runs after a successful ffmpeg render was outside the try/except guarding
the render itself, so any exception there flipped an already-successful
render (file written, thumbnail extracted) to `failed`. Wrapped that whole
block in its own `try/except Exception`, placed *before* the
`video_file_path`/`thumbnail_path`/`status = ready` writes so those still
happen regardless of a scoring failure. On exception: logged
(`logger.exception`) and the clip's prior score fields are left exactly as
they were -- no partial write, no status change. The `speaker_focus` path
(reuses `speaker_framing_result` computed earlier, already inside the
render's own try/except) is now consistent with `dynamic_blur`/`fit`: a
scoring failure can no longer surface as a failed render for either.

**Bug 2 -- `clip_service.py`, `_virality_reason`:** added a
`_REVIEW_THRESHOLD = 50.0` module constant mirroring frontend
`virality.ts`'s `REVIEW_THRESHOLD`. When neither hook/completeness/framing
crosses its own individual weak/strong threshold (the previous fallback
condition), `_virality_reason` now computes the composite score
(`_composite_virality_score`) and checks it against `_REVIEW_THRESHOLD`
before falling through to the generic "Middling signals..." text. If the
composite is in the sub-50 review band, the reason instead names
whichever sub-score(s) are lowest relative to their own scale (e.g. "Below-
average hook -- review before publishing."), so a "Needs Manual Review"
clip never gets reassuring/neutral reason text. The generic fallback is
now only reachable when scores are genuinely middling *and* the composite
is at or above the review threshold (e.g. completeness=55, framing None,
hook in [46.25, 70) -- verified by hand against the constants, not just
asserted).

Two things worth flagging explicitly rather than leaving implicit:
- In the **refined** pass (post-render), `framing` is always exactly `0.0`
  or `100.0`, so it always trips the existing weak-or-strong check and
  `parts` is never empty there -- this new review-band branch only ever
  fires on the **partial** (pre-render) score. That's expected, not a gap:
  a refined-pass repro of this bug can't exist by construction.
- The new "Below-average X -- review before publishing." text is templated
  per named sub-score the same way the pre-existing "Weak X -- review
  before publishing." text already is (identical string for hook=40 and
  hook=44, e.g.) -- consistent with the story's own accepted pattern (see
  the "Design" subsection's own `virality_reason` AC), not a new violation
  of the "must never read as fabricated" bar QA raised.

While fixing Bug 1, also tightened `refine_clip_with_framing` itself: it
previously assigned `clip.framing_score`, then `clip.virality_score`, then
`clip.virality_reason` one at a time, so an exception partway through
(from either scoring call) could leave the clip with some fields updated
and others stale -- e.g. a fresh sub-50 `virality_score` next to a stale,
reassuring `virality_reason`, which is Bug 2's failure mode reached by a
different route. Now computes `score`/`reason` into locals first and
assigns all three fields together only once both calls succeed, so a
mid-computation exception leaves every field exactly as it was (matching
what Bug 1's fix already guarantees at the render layer).

**Tests added:**
- `backend/tests/test_video_render.py::TestViralityScoreRefinement::test_scoring_failure_after_a_successful_render_does_not_mark_it_failed`
  -- a `dynamic_blur` clip where `compute_speaker_framing` raises; asserts
  `status == ready`, `video_file_path`/`thumbnail_path` are set, and the
  clip's prior `framing_score`/`hook_score`/`completeness_score`/
  `virality_score`/`virality_reason` are all untouched.
- `backend/tests/test_clips.py::TestViralityScorePartial::test_review_band_reason_is_not_the_generic_middling_fallback`
  -- QA's exact repro (`hook_score=40.0` inside `[35, 45.6)`,
  `completeness_score=55.0`); asserts the composite is `< 50.0`, the
  reason is not the generic "Middling signals..." string, and it mentions
  both "review" and "hook".

**Validation run:**
- `pytest backend/tests/test_video_render.py -v` -- 26 passed.
- `pytest backend/tests -v` (full suite) -- 277 passed, 0 failed.
- `ruff check backend/app/services/video_render.py backend/app/services/clip_service.py backend/tests/test_video_render.py backend/tests/test_clips.py` --
  all checks passed. (Found one pre-existing `E501` at
  `tests/test_video_render.py:411`, from this story's earlier
  Implementation-phase test additions rather than this fix round, but it
  was in a file this fix's own scope covers -- fixed it too, by wrapping
  the parametrize list across lines, rather than leaving a dirty `ruff
  check` on a touched file for the next QA pass to trip over.)

Not re-verified by QA yet -- handing back to `tester` for a second QA pass
against these two bugs specifically. Still not cleared for founder release
approval.

#### QA re-verification (tester, 2026-09-06)

**Scope:** re-verifying `backend-agent`'s "Fix" subsection above against
Bug 1 (`video_render.py`) and Bug 2 (`clip_service.py`) from my first QA
pass. Did not re-run the full nine-AC trace from scratch -- spot-checked
the parts these narrow fixes could plausibly have disturbed.

**1. Independent test run:**
- `.venv/bin/python -m pytest backend/tests -v` -> **277 passed**, 0
  failed. Matches backend-agent's count exactly.
- `pytest backend/tests/test_video_render.py::TestViralityScoreRefinement -v`
  -> 5 passed (isolated re-run of the touched class).
- `ruff check backend/app/services/video_render.py backend/app/services/clip_service.py backend/tests/test_video_render.py backend/tests/test_clips.py`
  -> all checks passed.

**2. Bug 1 -- read the actual control flow, don't trust the description.**
Read `_render_and_persist` in `video_render.py` directly (lines 217-346).
Confirmed:
- The framing-refinement block (`compute_speaker_framing` for
  `dynamic_blur`/`fit`, `score_clip_partial`, `refine_clip_with_framing`)
  is now wrapped in its own `try: ... except Exception: logger.exception(...)`
  at lines 314-338, with **no `raise`, no `return`** in the except body --
  it logs and falls straight through.
- That fall-through lands at lines 340-346
  (`clip.video_file_path = ...` / `thumbnail_path` / `clip.status =
  ClipStatus.ready` / `session.commit()`), which sit textually and
  causally *after* the try/except, not gated behind it. A scoring
  exception genuinely cannot reach the code that would flip the clip to
  `failed` -- there is no `failed` write anywhere past this try/except in
  the success path. Confirmed by tracing control flow, not by pattern-
  matching the diff.
- **Exact repro re-run (not just the new test's name):** wrote and ran an
  independent `dynamic_blur` clip fixture identical to my original Bug 1
  repro, patched `compute_speaker_framing` to raise `RuntimeError`, called
  `render_clip`. Result: `status == ready`, `video_file_path` and
  `thumbnail_path` both set, and `framing_score` stayed `None` (prior
  partial-score fields untouched). **Bug 1 is fixed at the exact repro.**
- **Precision correction to backend-agent's own writeup:** the claim that
  "the `speaker_focus` path ... is now consistent with `dynamic_blur`/
  `fit`" is only true for the *scoring* calls (both now sit inside the new
  try/except). It is **not** true for `compute_speaker_framing` itself on
  an `auto`/`speaker_focus` clip: that call still runs inside `_frame_9x16`,
  invoked from `_run_ffmpeg` inside the *earlier* try/except (lines
  268-300), and a failure there is still render-fatal (clip -> `failed`,
  no file). That's correct behavior (no file was produced, so `failed` is
  the honest status) -- but it is not "the same" failure mode as
  `dynamic_blur`/`fit`'s post-render call, it's a different, still-fatal
  path that this fix didn't touch and shouldn't have. Matches the
  distinction my original QA drew; not a new bug, just flagging that one
  sentence in the Fix writeup overstates the symmetry.
- **Legacy-clip sanity check:** if a legacy clip (`hook_score is None`)
  hits this same exception path, `score_clip_partial` never runs (the
  exception fires before reaching it), so all five score fields stay
  `NULL` and the clip still commits `ready`. This is exactly AC7's "Not
  yet scored" display case -- correct by design, not a gap.

**3. Bug 2 -- read `_virality_reason`'s control flow, don't trust the new
branch exists in isolation.** Read lines 473-517 directly. The `if not
parts:` block (only reachable when no sub-score crossed its own
weak/strong threshold) now computes `_composite_virality_score` first and
checks `< _REVIEW_THRESHOLD` **before** the generic "Middling signals..."
`return` two lines below -- confirmed this is the only `return` reachable
from that branch when composite `< 50`, not an added-but-unreachable
branch.

**Exact repro re-run (my original table, executed against the fixed
code):**

| hook | completeness | score | reason |
|---|---|---|---|
| 35.0 | 55.0 | 44.33 | "Below-average hook -- review before publishing." |
| 40.0 | 55.0 | 47.0 | "Below-average hook -- review before publishing." |
| 45.0 | 55.0 | 49.67 | "Below-average hook -- review before publishing." |

The generic fallback is gone at all three original repro points. **Bug 2
is fixed at the exact repro.**

**Boundary re-check (own addition, not in the original repro):** confirmed
the generic fallback still fires correctly just above the line --
`hook=46.0/completeness=55.0` (score=50.2) and `hook=69.9` (score=62.95)
both still return "Middling signals..." -- so the fix narrows the fallback
to exactly the claimed range rather than over-firing. Also checked the
exact boundary: `hook=45.63, completeness=55.0` -> composite rounds to
`50.0` -- backend's `< 50` and frontend `virality.ts`'s `>= 50` (`Good
Insight`) agree at this value (neither is "review band"), so there's no
split-brain at the boundary itself, just two independent copies of the
same `50.0` constant (see risk note below).

**4. Does Bug 2's fix actually change what the founder sees, or only the
DB value?** Checked this because field-wiring alone wasn't enough --
grepped `ViralityScoreBadge.tsx` and `frontend/src/lib/virality.ts` for how
`virality_reason` is consumed. It is rendered **verbatim** as
`{insights.explanation}` (`virality.ts:68` passes `clip.virality_reason`
straight through when `score !== null`; `ViralityScoreBadge.tsx:64,147`
render it as plain text) -- no prefix-matching, no parsing, no
band-derived substitute text. The new "Below-average X -- review before
publishing." string reaches the founder's screen exactly as computed.
**Bug 2's fix is real and user-visible, not just a DB-layer change.**

**5. Third self-found hardening (atomic assignment in
`refine_clip_with_framing`) -- does it leave a gap?**
Read the code (lines 538-560): `score` and `reason` are computed into
locals via `_composite_virality_score`/`_virality_reason` *before* any of
`clip.framing_score`/`virality_score`/`virality_reason` is assigned; all
three assignments happen only after both calls succeed. **Empirically
verified**, not just read: patched `_virality_reason` to raise mid-call on
a fake clip object with known prior values (`framing_score=None,
virality_score=90.0, reason="Strong hook..."`) and called
`refine_clip_with_framing` -- all three fields were bit-for-bit identical
before and after the caught exception. No gap in this function.

**Found, but a different function -- `score_clip_partial` does NOT get the
same treatment.** `score_clip_partial` (lines 520-535, called from the
*same* try/except block in `_render_and_persist` for legacy clips) assigns
`clip.hook_score` and `clip.completeness_score` directly, then separately
computes and assigns `clip.virality_score`/`virality_reason` -- not
locals-first. Empirically confirmed: patching `_composite_virality_score`
to raise mid-call left `hook_score=0.0`/`completeness_score=20.0` freshly
written but `virality_score`/`virality_reason` still `None` on the fake
clip. Since this whole block sits inside the same outer try/except that
Bug 1's fix added, this partial state **would commit** to the DB with the
clip still landing `ready` (correct per Bug 1's fix) -- but with mismatched
sub-scores vs. composite/reason for one call, on a legacy clip.

Not a blocking finding: reaching it requires `_composite_virality_score`
or `_virality_reason` -- both pure `round`/`min`/`max`/f-string operations
over two already-computed floats -- to raise, which cannot happen on the
real code path (I only reproduced it by patching the function itself to
raise). Reporting as an **architectural asymmetry** to backend-agent for
consistency (the same locals-first pattern applied to
`refine_clip_with_framing` wasn't applied to its sibling in the identical
try/except block), not as a release blocker.

**6. Regression spot-check (not a full re-run of all nine ACs):**
- Weight math re-run against the live constants: partial weights sum to
  `1.0`, refined weights sum to `1.0`, strong-partial `100.0`,
  weak-partial `25.67`, refined-confident `92.0`, refined-not-confident
  `67.0` -- all six numbers match my original QA table exactly. No drift.
- Grepped for all callers of `score_clip_partial`/
  `refine_clip_with_framing` -- both still only called from
  `video_render.py` and `clip_service.py`'s own `create_clips_from_highlights`/
  `update_clip`; signatures unchanged. Cross-agent wiring (schema/types)
  untouched by this fix round -- confirmed backend-agent's claim of
  "no frontend, migration, or model changes" against `app/models/clip.py`
  and `app/schemas/clip.py` (unchanged by this diff; any modifications to
  those files predate this fix round).

**Durable risk worth naming (not a bug, not blocking):**
`clip_service.py`'s `_REVIEW_THRESHOLD = 50.0` and
`frontend/src/lib/virality.ts`'s `REVIEW_THRESHOLD = 50` are two
independent copies of the same number, with no test pinning them together.
If either drifts on a future change, Bug 2's exact failure mode (reason
text disagreeing with the badge's band) returns silently. Same class of
observation as the original QA's designer-spec-match check, just noting
there's no regression guard against future drift.

**Verdict on both fixes: PASS.**
- **Bug 1: PASS.** Confirmed by control-flow trace and independent repro
  re-run -- a scoring exception can no longer flip a successfully-rendered
  clip to `failed`, for both `dynamic_blur`/`fit` (the bug's own repro)
  and legacy pre-migration clips (checked as a sanity extension).
- **Bug 2: PASS.** Confirmed by control-flow trace, independent repro
  re-run at the exact original numbers, a boundary check, and (new this
  round) confirming the fixed string actually reaches the rendered UI
  verbatim, not just the DB.
- **Point 4 (atomic-assignment hardening): confirmed clean for
  `refine_clip_with_framing`** (empirically, not just read). **One
  non-blocking asymmetry found** in its sibling `score_clip_partial` --
  routed to backend-agent as a consistency nit, not a bug report, since it
  is unreachable on the real code path.
- **Point 5 (regression check): no disturbance found** in the weight math,
  cross-agent wiring, or the nine acceptance criteria from the first QA
  pass -- spot-checked rather than fully redone, per the task's own
  instruction, since this fix is narrowly scoped to code already traced
  once.

**Overall recommendation:** both flagged bugs are genuinely fixed, at
their exact repros, with no new regressions found and only one
non-blocking architectural nit. This story is ready for founder
release-approval review. This is a test-plan-and-results report only --
**not** a release sign-off; per governance, release approval is the
founder's call. Awaiting founder go/no-go before this goes to DevOps.

#### Deployment (devops, 2026-09-06)

**Shipped:** the real, server-computed virality score exactly as described
in the Backend/Frontend/Fix subsections above -- `Clip.virality_score`,
`Clip.hook_score`, `Clip.completeness_score`, `Clip.framing_score`,
`Clip.virality_reason` (all nullable, server-computed, never client-writable),
`score_clip_partial`/`refine_clip_with_framing`/`_composite_virality_score`/
`_virality_reason` in `clip_service.py` wired into clip creation, `PUT
/clips/{id}`, and the post-render refinement step in `video_render.py`
(including both QA-flagged bug fixes: the try/except safety net so a
scoring failure can never flip a successful render to `failed`, and the
sub-50 review-band `virality_reason` fix). Frontend: `ViralityScoreBadge`'s
4th "Not yet scored" state, `clipToViralityInsights(clip)` replacing the
deleted client-side `computeViralityInsights` fabrication at both call sites
(`ClipCard.tsx`, `ClipEditorPage.tsx`).

**Files committed (this commit only):**
- `backend/app/models/clip.py` -- only the 5 score columns (`virality_score`,
  `hook_score`, `completeness_score`, `framing_score`, `virality_reason`);
  the working tree's `BrollPlacement` enum + `broll_placement` column
  (separate, already-approved B-roll story) were left staged out.
- `backend/app/schemas/clip.py` -- only the 5 score fields on `ClipResponse`;
  `broll_placement` (on both `ClipResponse` and `ClipUpdateRequest`) and its
  import left out.
- `backend/app/services/clip_service.py` -- committed in full (100% this
  story).
- `backend/app/services/video_render.py` -- only the scoring-related hunks:
  the new `clip_service` import, `_render_and_persist`'s
  `framing_mode_str`/`speaker_framing_result` capture and the scoring
  try/except block, and `_frame_9x16`/`_run_ffmpeg`'s return-type change to
  surface the computed `SpeakerFraming` for reuse. B-roll's `_apply_broll`
  placement rewrite, the `broll_placement` parameter threaded through
  `_run_ffmpeg`/`_render_and_persist`, and the module docstring's
  `RENDER_BROLL_MODE` → `broll_placement` rewording were left staged out --
  `_apply_broll`'s call site and signature in this commit are byte-identical
  to `HEAD` (4 args, no `placement`).
- `backend/tests/test_clips.py` -- committed in full (100% this story).
- `backend/tests/test_video_render.py` -- only the new
  `TestViralityScoreRefinement` class (5 tests) plus the one-line
  `stream, _ = video_render_module._frame_9x16(...)` unpack fix in
  `TestSplitScreenFraming._graph` required by `_frame_9x16`'s new tuple
  return (a mechanical adaptation to this story's signature change, not a
  Split Screen feature change -- left the rest of that class/test
  untouched, per "Split screen is off-limits"). B-roll's new
  `test_render_composites_broll_at_every_placement` (4 parametrized cases)
  and the `BrollPlacement` import left out.
- `backend/alembic/versions/9f3c1a7d5e2b_clip_virality_scores.py` (new).
- `frontend/src/lib/virality.ts`, `frontend/src/lib/__tests__/virality.test.ts`
  (new), `frontend/src/components/clips/ViralityScoreBadge.tsx`,
  `frontend/src/components/clips/__tests__/ViralityScoreBadge.test.tsx`
  (new), `frontend/src/components/clips/ClipCard.tsx` -- committed in full
  (100% this story).
- `frontend/src/components/clips/__tests__/ClipCard.test.tsx` -- only the 5
  score fields added to `baseClip` and the two new virality-band tests;
  B-roll's `broll_placement: 'bottom_right'` fixture field left out.
- `frontend/src/pages/ClipEditorPage.tsx` -- only the
  `computeViralityInsights` → `clipToViralityInsights(clip)` import + call-site
  fix; B-roll's `brollPlacement` state, `handleBrollPlacementChange`, and the
  `BrollPanel` placement props left out.
- `frontend/src/types/index.ts` -- only the `Clip` interface's score-field
  block (old optional `virality_score?`/`virality_reason?`/`hook_score?`/
  `engagement_score?` replaced with the 5 nullable, server-authoritative
  fields); B-roll's `broll_placement` field and the exported
  `BrollPlacement` type left out.
- `team/backlog.md` (this file -- documentation only).

**Not touched, not staged, left exactly as they were in the working tree:**
`backend/app/config.py`, `backend/app/models/broll_asset.py`,
`backend/app/services/broll_sourcing.py`, `backend/app/services/reframe.py`,
`backend/tests/test_broll.py`, `backend/tests/test_reframe.py`,
`frontend/src/components/clips/BrollPanel.tsx`,
`frontend/src/components/clips/__tests__/BrollPanel.test.tsx`,
`frontend/src/services/clipService.ts`, the two untracked B-roll Alembic
revisions (`2c98d61a2ef4`, `e276d71b9110` -- already applied to the dev DB
from earlier this session, per the task's own note, but not committed to
git), and `frontend/src/components/clips/TextBasedTrimmer.tsx` (the
unrelated Start/End-button + AI-pick-badge enhancement, not part of any
backlog story). Confirmed identical before/after via `git status
--porcelain` and `git diff` on each -- zero delta.

**How the mixed files were split:** `git diff -U0` on each of the 7 files
sharing hunks with the B-roll working-tree diff to identify exact
line-level boundaries, then (since several hunks sat within 3-6 lines of a
B-roll hunk and would have merged under `git add -p`'s default context) built
each file's target "story-only" content directly -- `git show HEAD:<path>`
as the base, this story's hunks applied on top via scripted string
replacement, diffed both against `HEAD` (confirms exactly this story's
content, nothing missing) and against the working tree (confirms the
remainder is exactly B-roll's content, nothing bundled) -- then staged via
`git hash-object -w` + `git update-index --cacheinfo`, which writes a blob
directly into the index without touching the working-tree file. This
leaves the actual working-tree files (and both other in-flight stories)
completely unmodified and unstaged throughout -- verified with `git diff`
(index-to-worktree) both before and after. No file required a bail-out:
every mixed hunk had a clean line-level boundary between the two stories,
including the `_run_ffmpeg` call in `video_render.py` where a `speaker_framing_result =`
capture (this story) and a `broll_placement=clip.broll_placement,` argument
(B-roll) sit a few lines apart in the same call -- confirmed as genuinely
separate `git diff -U0` hunks, not a same-line conflict.

**Verified before commit, against the isolated staged content (not the
mixed working tree):** built a temporary commit object directly from the
index (`git write-tree` + `git commit-tree`, parented on `HEAD`, never
touching `main`/HEAD/the working tree/the index), checked it out into a
throwaway `git worktree add --detach`, and ran the full suite there:
- `pytest tests -v` (backend, isolated worktree) → **266 passed**, 0
  failed. (Fewer than the 277 the Fix/QA-re-verification subsections
  reported against the full mixed working tree -- expected, since this
  isolated tree excludes B-roll's own new tests, e.g. the 4-case
  `test_render_composites_broll_at_every_placement` parametrize.)
- `ruff check` on the story's touched backend files → clean except one
  pre-existing `I001` (import-sort) finding in `app/schemas/clip.py` that
  reproduces identically against `git show HEAD:backend/app/schemas/clip.py`
  -- confirmed pre-existing, not introduced by this commit, out of this
  story's scope to fix.
- `npx vitest run` (frontend, isolated worktree, `node_modules` symlinked
  in rather than reinstalled) → **97 passed** across 18 test files.
- `npx tsc -b --noEmit` (frontend, isolated worktree) → clean, no type
  errors.
- Worktree removed after verification (`git worktree remove --force`);
  confirmed via `git status` immediately before and after that the main
  working tree/index were unaffected by any of this.

**Migration:** `9f3c1a7d5e2b_clip_virality_scores.py` adds the 5 nullable
score columns, no data backfill (existing rows correctly stay `NULL` per
the story's own design). Confirmed via `alembic current`/`alembic heads`
against the dev Postgres DB that this revision is already the applied head
-- it was run earlier this session (per the Backend subsection's own
validation notes) and needs no further action here. It sits linearly on top
of the two uncommitted B-roll revisions (`e276d71b9110`, `2c98d61a2ef4`),
which are also already applied to this same dev DB (a separate, prior
action, not part of this deploy) but intentionally not committed to git
yet, per that story's own DevOps note.

**Deploy mechanism (this project's actual current state):** no CD/build-push
job exists -- `.github/workflows/ci.yml` only lints and tests on push to
`main`/PRs; nothing builds or pushes a Docker image or applies anything to a
host. At this project's stage, **the deploy artifact is the commit to
`main` itself** (same finding as the two prior DevOps notes above). This
sandbox still has no `docker`/`docker-compose` binary, so no container was
built or restarted from here. Nothing about this change needs anything
beyond the deploy host's normal `git pull` + `alembic upgrade head` (a
no-op there too, once that host's DB is on the same revision) +
`docker compose build api worker web` + `docker compose up -d` for the
`backend`/worker/frontend images -- both backend and frontend files changed,
so all three services need a rebuild this time (unlike the previous
clip-boundary-fix deploy, which was backend-only).
**Not pushed to the remote** -- this task did not request a push, so `main`
on the remote is unchanged and CI has not run against this commit.

**Rollback steps:**
1. `git log --oneline -3` to confirm this commit's SHA is at `HEAD` (this
   commit's message starts with `feat(clips):`).
2. Not a full `git revert <this-commit-SHA>` -- this commit's
   `team/backlog.md` hunk carries this story's own full Design/Database/
   Backend/Frontend/QA/Fix/QA-re-verification/Deployment history (and rides
   along with whatever else was in `backlog.md` at commit time) that a
   revert would delete. Instead, revert only the code paths: restore each
   of the 13 non-`backlog.md` files listed above to its state from the
   commit immediately before this one (`git checkout <parent-SHA> --
   <path>...` for each), then commit that. Since several of those files
   were only partially staged this round, restoring the whole file to the
   parent SHA is safe and exact -- the parent SHA predates all of this
   story's changes to every one of those files.
3. `alembic downgrade -1` against the dev DB drops the 5 score columns if a
   full rollback is truly needed -- but since they're all nullable with no
   `NOT NULL`/default constraint and no other migration depends on them,
   leaving the column added (even after reverting the code that populates
   it) is also a safe, less disruptive partial rollback; note the two
   uncommitted B-roll migrations sit on top of this one in the chain, so a
   downgrade here would need coordinating with that story's own (still
   pending) deploy.
4. No feature flag exists for this change (unconditional logic in
   `create_clips_from_highlights()`'s clip-creation path and the render
   pipeline) -- revert is the only toggle.
5. On the actual deploy host: rebuild/redeploy `backend`/`worker`/`web`
   images from the commit immediately before this one and restart via
   `docker compose up -d` (same pattern as the two prior DevOps notes).

**Handing off to `seo-geo` + `marketer`** -- this is a trust/credibility fix
to an existing, already-shipped feature (the virality score badge itself
isn't new, only its honesty is), not a new user-facing page or surface. May
still be worth a short "your clip scores are now real, server-verified
signals -- not a placeholder" changelog/trust note for existing users who've
seen the badge before; flagging for their own call on whether it's worth
publishing.

---

## Active



_(Approved stories move here as they move through Designer → Developer →
Tester → DevOps → SEO/GEO/AEO → Marketer, each appending a subsection below the
story.)_

---

### Generated Shorts must start/end on a complete thought, not mid-sentence

**Status:** deployed (2026-09-06)

**Priority:** P0 — this is a defect in the core output of the product (every
generated Short is affected, not an edge case), not a new capability.

**Module:** Clip Library. Does not touch Highlight Detection (scoring/anchor
selection in `highlight_detection.py` already works correctly — out of
scope) or B-roll Sourcing (unrelated, separate in-flight story awaiting
release approval — not bundled here).

As a creator reviewing auto-generated Shorts, I want each clip to begin and
end on a complete sentence instead of cutting off mid-word or mid-thought,
so that the Shorts are watchable and shareable without manual re-trimming.

**Context (root cause, already investigated — do not re-derive):** Clip
boundaries are computed in `backend/app/services/clip_service.py`.
`_pad_clusters()` expands a highlighted cluster toward a fixed
target/maximum duration (`CLIP_LENGTH_TARGETS`, e.g. `auto` = 40s target /
50s max) purely on duration/spacing math, with no awareness of sentence
boundaries — this can even discard the well-scored anchor opening that
`highlight_detection.hook_score`/`_continuation_penalty` picked, if the
backward pad reaches past it. `_snap_to_speech()` then nudges edges to the
nearest Whisper *segment* boundary within `_SNAP_TOLERANCE_SECONDS` (2.5s),
but a Whisper segment breaks on pauses, not grammar — per `_sentences_in()`'s
own docstring, a segment is "usually half a sentence." Snapping to a segment
edge only avoids cutting mid-word; it does not guarantee landing on a
sentence-final boundary. If snapping would shrink the clip below
`_MIN_SNAPPED_DURATION` (8.0s), the code discards snapping entirely and
falls back to the unsnapped, duration-only edges. Net effect: duration
budget currently outranks completeness, and nothing in the current logic
filters candidate edges down to ones ending in `. ! ?` for the actual
`start_time`/`end_time` chosen (that check exists in `_completeness_score`/
`_sentences_in`, but only for scoring/titling, never applied to the cut
itself).

**Assumption to verify, not to treat as certain:** Whisper's stored
`segment.text` (per `transcription.py`) generally includes terminal
punctuation, so a sentence-boundary signal should exist in the data.
Tester should confirm this holds against real transcripts (not only
synthetic/test fixtures) before this is considered proven in production.

**What this is:**
- Sentence-completeness becomes the primary signal for a clip's
  `start_time`/`end_time`, ahead of hitting the exact target duration.
- Bounded, not unlimited: extending a clip to reach a sentence boundary is
  allowed but capped (see bounds below) — this is a duration *trade-off*,
  not a removal of duration limits.

**What this is not (non-goals):**
- No change to `highlight_detection.py` — scoring, `hook_score`,
  `_continuation_penalty`, and which segment anchors a cluster are
  untouched.
- No frontend or API surface change; no new `Clip`/`VideoProject` status
  values.
- Not bundled with the in-flight B-roll story (commit `6bb3bef`, awaiting
  release approval) — unrelated, do not touch its files.

**Bounds (the one real decision this story makes, so it isn't left to the
developer to improvise):**
- Extending a clip's edges to reach a sentence boundary may exceed that
  video's requested `ClipLength` maximum (`CLIP_LENGTH_TARGETS[...][1]` —
  30s for `fast`, 50s for `auto`, 60s for `in_depth`) by at most a small,
  bounded allowance (new named constant in `clip_service.py`; the exact
  seconds value is an implementation choice, but it must exist and be
  derived from — not replace — the per-`ClipLength` maximum). A `fast`
  clip must not balloon to the `in_depth` ceiling just because a sentence
  ends late.
- Regardless of `ClipLength`, `end_time` must never exceed 60.0s duration
  outright, and must never exceed the video project's own ceiling
  (`max(TranscriptSegment.end_time)` for that project) — per `CLAUDE.md`'s
  Clip Library rule that `start_time`/`end_time` must fall within the
  parent video's duration.
- Must not regress the non-overlap invariant `_cluster_raw_segments`'s
  docstring documents (a prior incident where padding-before-merging
  cascaded scattered highlights into one multi-minute clip): any extension
  for completeness is still bounded by the neighboring cluster's boundary,
  the same way `_pad_clusters` already bounds padding.
- When no sentence-terminal boundary is reachable within the bounds above
  (e.g. a transcript with no terminal punctuation at all), behavior must be
  *defined*, not undefined: fall back to today's `_snap_to_speech`
  segment-edge result, then to the unsnapped duration-based edges — never
  produce an empty, zero-length, or overlapping clip.

**Acceptance criteria:**
- Given a candidate cut point where a sentence-terminal segment (text
  ending `.`, `!`, or `?`) exists within the bounded search window, the
  clip's `end_time` lands at that segment's end, not at the raw
  duration-budget edge.
- Given a candidate start point, `start_time` lands at the start of a
  segment whose immediately preceding segment ended with terminal
  punctuation, or at `0.0` for the video's first segment — not mid-sentence.
- No generated clip's `end_time` exceeds its `ClipLength`'s own maximum by
  more than the new bounded allowance, and no clip exceeds 60.0s duration
  or the video project's own transcript ceiling, under any circumstance.
- For consecutive generated clips, the non-overlap invariant still holds:
  `clips[i].end_time <= clips[i+1].start_time`.
- When no reachable sentence boundary exists in a transcript, clip
  generation still produces valid, non-overlapping, non-empty clips (via
  the defined fallback chain above) rather than erroring or degenerating.
- All existing tests in `backend/tests/test_clips.py` covering
  `_pad_clusters`, `_snap_to_speech`, and `_cluster_raw_segments` continue
  to pass unmodified in intent (existing behavior for already-complete
  sentences is unaffected).
- Full backend suite (`pytest backend/tests -v`) passes, with new tests
  added for the sentence-boundary and bounded-allowance behavior.

**Scope note:** Backend-only, scoped to `backend/app/services/clip_service.py`
and `backend/tests/test_clips.py`. No UI surface changes — **Designer step
is skipped for this story**; on approval this goes straight to
`backend-agent`.

---

#### Implementation (backend-agent, 2026-09-06)

**Files touched:**
- `backend/app/services/clip_service.py` — added `_extend_to_sentence_boundary()`
  and two new constants; wired into `create_clips_from_highlights()`.
- `backend/tests/test_clips.py` — new `TestExtendToSentenceBoundary` unit
  tests (4) plus 3 new integration tests under `TestGenerate`.

**Endpoints:** none added or changed, no schema changes. This is entirely
internal to `create_clips_from_highlights()` — same request/response shape
as before.

**What changed:**
- New function `_extend_to_sentence_boundary(start, end, segments, floor,
  ceiling, allowed_duration)`, run after `_snap_to_speech()` in the
  generation loop. It moves `end_time` *forward only* to the nearest
  segment-end whose text terminates in `.`/`!`/`?`, and `start_time`
  *backward only* to the nearest such boundary (or the transcript's very
  first segment), each re-checked against `allowed_duration` so the final
  window's duration is bounded exactly. `floor`/`ceiling` reuse the same
  `previous_end`/`next_start` bounds `_pad_clusters`/`_snap_to_speech`
  already enforce, so the non-overlap invariant
  (`clips[i].end_time <= clips[i+1].start_time`) is unchanged.
- **Deliberate ceiling, not a miss:** extension is one-directional (extend
  to complete a sentence, never trim to reach an earlier one). If a
  sentence's terminal punctuation lands beyond `allowed_duration`, the edge
  is left wherever `_snap_to_speech`/the raw duration edge put it —
  mid-sentence. Marked with a `ponytail:` comment in the source naming the
  upgrade path (bounded trim-back toward `target`) if this shows up in
  practice.
- New constants in `clip_service.py`:
  - `_SENTENCE_BOUNDARY_ALLOWANCE_SECONDS = 5.0` — how far past a
    `ClipLength`'s own maximum (`CLIP_LENGTH_TARGETS[...][1]`) a clip may
    stretch to finish a sentence. Sized to one trailing spoken sentence
    (~15 words at ~3 words/sec) — enough to catch a sentence that runs a
    beat over budget, not enough for `fast` (30s max) to creep toward
    `auto` territory (40s target). Chosen deliberately small: a larger
    value (10.0 was tried first) let a `fast` clip reach 37.5s in testing,
    eroding the fast/auto/in_depth distinction the existing
    `test_fast_shorts_are_cut_shorter_than_in_depth_ones` test guards —
    5.0 keeps that test's assertions passing unmodified.
  - `_HARD_MAX_CLIP_DURATION = 60.0` — absolute duration cap regardless of
    `ClipLength`. `allowed_duration = min(maximum + allowance,
    _HARD_MAX_CLIP_DURATION)`.
  - A one-line clamp after the extend call handles the case where
    `_snap_to_speech` alone (independent of any sentence-boundary
    extension) widens a window by up to `2 * _SNAP_TOLERANCE_SECONDS`
    (5.0s): for `in_depth` clips the allowance is already fully absorbed
    by the hard cap (`min(60+5, 60) = 60`), so if snap pushes duration
    over 60s, `start_time` is pulled forward to `end_time -
    allowed_duration` (never touches the sentence-terminal `end_time` just
    earned, and only moves `start_time` later, so it can't cross `floor`).
    Covered by
    `test_generate_never_exceeds_the_hard_60s_cap_even_after_snap_widens_it`.

**Top item for Tester:** the story's own "Assumption to verify" — that
Whisper's stored `segment.text` (per `transcription.py`) generally includes
terminal punctuation. Every test here uses synthetic fixtures with
punctuation supplied by hand; the mechanism's real-world effectiveness
depends on this holding against actual transcribed audio, not just test
data. Please confirm against real transcripts before this is considered
proven in production, per the story's own callout.

**Validation commands run:**
- `pytest backend/tests/test_clips.py -v` → 27 passed (4 new unit tests for
  `_extend_to_sentence_boundary`, 3 new integration tests: sentence-boundary
  extension within the bounded allowance, the hard-60s-cap-after-snap-widen
  edge case, and the no-terminal-punctuation-anywhere fallback chain with
  explicit non-overlap assertions). All pre-existing tests in this file
  pass unmodified, including `_pad_clusters`/`_snap_to_speech`/
  `_cluster_raw_segments` coverage and
  `test_fast_shorts_are_cut_shorter_than_in_depth_ones`.
- `pytest backend/tests -v` → 264 passed (full suite, no regressions).
- `ruff check backend/app/services/clip_service.py backend/tests/test_clips.py`
  → all checks passed. (Note: `ruff check backend/app` as a whole reports
  pre-existing, unrelated issues in `broll_sourcing.py`,
  `highlight_detection.py`, and `storage.py` — none touched by this story.)

Not cleared for QA/deploy yet — handing off to `tester` for a formal test
plan and the second founder approval gate before `devops`.


#### QA (tester, 2026-09-06)

**Test plan (against this story's acceptance criteria):**
1. Re-run full backend suite, confirm no regressions.
2. Unit-check `_extend_to_sentence_boundary` directly for: forward end-extension when reachable, backward start-extension when reachable, bounded-allowance non-extension, floor/ceiling never crossed, no-punctuation-anywhere fallback.
3. Trace `allowed_duration` math end-to-end (both edges, plus the post-hoc snap-widen clamp) to confirm final clip duration can never exceed `allowed_duration` regardless of which edge(s) actually moved — and, separately, confirm the *edges themselves* stay on defined boundaries even when that clamp fires.
4. Stress-test the non-overlap invariant with a dense, closely-spaced-highlight scenario.
5. Probe the literal "0.0" wording in AC2 against the code's actual first-segment behavior.
6. Empirically test the story's flagged assumption (Whisper segments generally end in terminal punctuation) against real synthesized speech run through the actual local Whisper backend (`transcription.py`'s `local` path) — not just synthetic fixtures.
7. Sanity-check the one-directional (extend-only, never-trim) design doesn't silently violate an AC.

**Results per acceptance criterion:**

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | `end_time` lands at a reachable sentence-terminal segment end, not the raw duration edge | PASS — `test_extends_past_the_raw_duration_edge_to_finish_the_sentence`, `test_generate_extends_fast_clip_to_sentence_end_within_bounded_allowance`, and my own trace of `_extend_to_sentence_boundary`'s `end_candidates` filter (`end <= e <= ceiling and e - start <= allowed_duration`, `min(...)` picks nearest) confirm this. |
| 2 | `start_time` lands at a segment whose preceding segment ended in terminal punctuation, or the video's first segment | **FAIL** in one reproducible scenario (`in_depth` clips where `_snap_to_speech` widens the window past `allowed_duration`) — see bug below. Separately, code backs up to `ordered[0].start_time` for the very first segment rather than the literal value `0.0`; that part is a defensible reading of the AC (excludes leading silence) and not the reason for the FAIL. |
| 3 | No clip exceeds its `ClipLength` max by more than the 5.0s allowance; never exceeds 60.0s or the project's transcript ceiling | PASS on duration — traced the arithmetic: `end_candidates`/`start_candidates` each re-check `allowed_duration` using the other edge's already-fixed value, and the post-extend clamp (lines 408-414) caps duration at exactly `allowed_duration`. Confirmed via `test_generate_extends_fast_clip_to_sentence_end_within_bounded_allowance` and `test_generate_never_exceeds_the_hard_60s_cap_even_after_snap_widens_it`. Duration is bounded correctly; see AC2 for the problem with *where* that clamp puts the edge. |
| 4 | Non-overlap invariant (`clips[i].end_time <= clips[i+1].start_time`) holds for consecutive clips | PASS — traced algebraically: clip `i`'s end is bounded above by `ceiling = windows[i+1][0]`, and clip `i+1`'s start is bounded below by `floor = previous_end`, which the main loop sets to clip `i`'s actual final `end_time`. Holds regardless of any staleness in the precomputed `ceiling`. Correction to my own initial stress test: my first attempt (8 clusters, 25s apart) produced zero extension at all — padding consumed the whole inter-cluster gap before extension ever ran, so it only re-confirmed the existing dense-padding regression test, not extension-under-pressure. Re-ran `test_generate_scattered_highlights_do_not_cascade_into_one_clip` (10 scattered highlights) — still passes. The invariant holds by the algebraic argument above; I was not able to construct a case that breaks it. |
| 5 | Defined, non-empty, non-overlapping fallback when no terminal punctuation is reachable anywhere | PASS — `test_generate_with_no_terminal_punctuation_still_produces_valid_clips` and `test_no_terminal_punctuation_reachable_leaves_edges_unchanged` both pass; traced the fallback chain and confirmed it can't produce an empty/inverted window. Note: this AC's own condition ("no reachable sentence boundary exists") isn't what triggers the AC2 bug below — in that repro, boundaries exist everywhere and `end_time` correctly lands on one; the bug is scoped to AC2, not this one. |
| 6 | Existing `_pad_clusters`/`_snap_to_speech`/`_cluster_raw_segments` tests pass unmodified in intent | PASS — confirmed via full suite run; `test_fast_shorts_are_cut_shorter_than_in_depth_ones` specifically still passes. |
| 7 | Full backend suite passes, with new tests added | PASS — `pytest backend/tests -v` → **264 passed**, matches backend-agent's report (re-run independently). `ruff check` on touched files → clean. |

**Overall verdict: FAIL.** One reproducible bug (below) violates AC2's "lands on a boundary" guarantee, scoped to `in_depth` clips. AC5 is unaffected (its own trigger condition — no reachable boundary anywhere — isn't present in the repro; boundaries exist and `end_time` correctly lands on one). Everything else passes. This is a governance call for the founder, not something QA can wave through as a risk note.

**Bug (flagging to backend-agent, `backend/app/services/clip_service.py`, not fixing myself):**

The post-extend clamp at lines 408-414 —
```python
if end_time - start_time > allowed_duration:
    start_time = end_time - allowed_duration
```
— computes a new `start_time` by raw subtraction, with no check that the result lands on a segment boundary, a sentence boundary, or anything meaningful. It fires whenever `_snap_to_speech` widens a window past `allowed_duration`, which the story itself notes can happen by up to `2 * _SNAP_TOLERANCE_SECONDS` (5.0s) — and for `in_depth` clips there is no allowance left to absorb it (`min(60+5, 60) = 60`), so this is the realistic case where it fires.

**Repro steps:**
1. Create a `ready` `VideoProject` with `target_clip_length=ClipLength.in_depth`.
2. Add 10 highlighted `TranscriptSegment`s, 8 seconds each, contiguous from `0.0` to `80.0`, text `"Highlight segment {i}."` (ends in `.`), plus one non-highlighted tail segment `80.0-88.0`.
3. `POST /api/v1/clips/generate`.
4. Observe the single generated clip: `start_time = 12.0`, `end_time = 72.0` (duration exactly `60.0`, the hard cap).
5. `12.0` is not a segment boundary at all (segments start/end on multiples of `8.0`: `0, 8, 16, 24, ...`) — it falls in the middle of the `[8.0, 16.0]` segment. This is worse than "mid-sentence," it's mid-word.
6. This is exactly `test_generate_never_exceeds_the_hard_60s_cap_even_after_snap_widens_it`'s own fixture — that test only asserts `duration <= 60.0` and doesn't check where the edge landed, so it passes today without catching this. Adding `assert clip["start_time"] in {i * 8.0 for i in range(11)}` to that test reproduces the failure (verified locally; fails with `start_time 12.0 is not on any segment boundary`).

**This is new code from this story, not a pre-existing issue**: before this story, `in_depth` had no clamp at all, so a padded-then-snap-widened window simply stayed at whatever `_snap_to_speech` produced — in this fixture that would have been a boundary-aligned `(8.0, 72.0)`, a `64.0s` clip exceeding the (then-nonexistent) hard cap. This story added both the hard cap (correctly, satisfying AC3) *and* this clamp to enforce it, and the clamp is what introduces the boundary violation — so simply reverting/removing the clamp is not a valid fix, it would just break AC3 again (`64.0s > 60.0s`). The one fix that satisfies both AC2 and AC3 together is the one already stated: search for the nearest reachable boundary at or after `end_time - allowed_duration` instead of a raw subtraction. In this exact fixture that search would land on `16.0` (segment 2's start, whose preceding segment ends in `.`), giving `(16.0, 72.0)` = `56.0s` — under the cap *and* on a sentence boundary. This is also the fourth, undocumented value in what the story specifies as a three-step fallback chain ("sentence boundary → `_snap_to_speech` edge → unsnapped duration edge") — the clamp's raw subtraction is a value none of those three steps would ever produce.

**Severity note — this isn't just cosmetic**: in this repro the clip's own anchor highlight (`TranscriptSegment` `[0.0, 8.0]`, `"Highlight segment 0."`, the segment `is_highlight=True` that seeded this cluster) falls entirely *outside* the final `(12.0, 72.0)` window. The generated clip no longer contains the moment it was generated from. Worse, `_title_from_window` falls back to the anchor segment's raw text when no in-window sentence matches its word-count filter (both true here, since every synthetic segment is only 3 words) — so the clip is titled `"Highlight segment 0."` while not containing that segment at all. Confirmed by direct reproduction (same fixture, printing `clip["title"]`).

**Blast radius**: only `in_depth` clips (`fast`: 30+5=35=`allowed_duration`, can't be exceeded by snap; `auto`: 50+5=55=`allowed_duration`, same). `in_depth` is the one `ClipLength` where the allowance is fully absorbed by the hard 60s cap, so a `>60s` continuous highlighted stretch plus a widening snap triggers it. Not an exotic input — a single long, keeps-talking highlighted moment in an `in_depth` video is a plausible real case, not a crafted edge case.

---

#### Fix (backend-agent, 2026-09-06)

**Files touched:**
- `backend/app/services/clip_service.py` — replaced the raw-subtraction
  clamp with a new `_clamp_start_to_boundary()` function; added
  `_fallback_title_source()` and wired both into
  `create_clips_from_highlights()`.
- `backend/tests/test_clips.py` — new `TestClampStartToBoundary` (3 unit
  tests), plus tightened assertions on the existing
  `test_generate_never_exceeds_the_hard_60s_cap_even_after_snap_widens_it`
  integration test (tester's exact repro fixture).

**Root cause confirmed:** exactly as tester traced — the post-extend
clamp at the old lines 408-414 did `start_time = end_time -
allowed_duration` with no boundary check at all, whenever
`_extend_to_sentence_boundary` itself couldn't find a boundary satisfying
`allowed_duration` (which happens whenever `_snap_to_speech` alone already
overshot the cap before extension got a chance — the realistic case for
`in_depth` clips, where the allowance is fully absorbed by the hard 60s
cap).

**What changed:**
- `_clamp_start_to_boundary(start_time, end_time, segments, floor,
  allowed_duration)` replaces the raw subtraction. It searches forward
  from `min_start = end_time - allowed_duration` for the nearest
  reachable boundary, in two tiers: (1) a sentence-terminal boundary (a
  segment start whose immediately preceding segment ends in `.`/`!`/`?`,
  or the transcript's first segment) — preferred; (2) if none is
  reachable, any plain segment start — still better than mid-word.
  `end_time` (the sentence-terminal edge `_extend_to_sentence_boundary`
  already earned) is never moved. Both tiers exclude candidates within
  `_MIN_SNAPPED_DURATION` of `end_time`, so the clamp can never select a
  boundary that would produce a zero-length or near-empty clip (a gap the
  first draft of this fix had — caught before handoff, now covered by
  `test_never_returns_a_boundary_that_produces_a_near_empty_clip`). If
  neither tier finds anything (no boundary at all inside the search
  window — a single segment spanning the whole clip), it falls back to
  `min_start` itself: a defined, cap-respecting last resort, explicitly
  marked with a `ponytail:` comment naming the upgrade path (bounded
  trim-back of `end_time` instead), not a silent reintroduction of the
  bug. `floor` is threaded through for consistency with the rest of the
  file's boundary functions, but is never actually the binding constraint
  here: because the clamp only fires when `end - start > allowed_duration`
  and `start >= floor` already held going in, `min_start > start >= floor`
  always, so every candidate this function can return already satisfies
  `floor` — non-overlap is preserved without needing new reasoning.
- For tester's exact repro fixture (10 contiguous 8s highlighted segments,
  `in_depth`), this produces `start_time=16.0`, `end_time=72.0` — a `56.0s`
  clip, on a real sentence boundary, under the 60s cap. Verified via the
  updated `test_generate_never_exceeds_the_hard_60s_cap_even_after_snap_widens_it`
  and directly via new unit test
  `test_lands_on_nearest_reachable_sentence_boundary_not_raw_subtraction`.
- `_fallback_title_source(segments, start, end, anchor)` fixes the
  title-derivation bug tester flagged as a severity note: it returns the
  anchor highlight's text only when the anchor is fully contained in the
  final `(start, end)` window; otherwise it falls back to the first
  segment fully inside the window, or `""` (→ "Untitled clip" via
  `_auto_title`) if nothing is fully inside either. `_title_from_window`
  itself needed no change — `_sentences_in` already restricts its
  candidate search to segments inside the window; the leaky fallback
  parameter (the anchor's raw text, unconditionally) was the entire bug.
  For the repro fixture this now titles the clip `"Highlight segment
  2."` (the first segment inside `(16.0, 72.0)`) instead of `"Highlight
  segment 0."` (a segment entirely outside the final window). Verified via
  the tightened assertion in
  `test_generate_never_exceeds_the_hard_60s_cap_even_after_snap_widens_it`.

**New/updated tests:**
- `TestClampStartToBoundary::test_lands_on_nearest_reachable_sentence_boundary_not_raw_subtraction`
  — tester's exact repro at the unit level.
- `TestClampStartToBoundary::test_falls_back_to_a_plain_segment_start_when_no_sentence_boundary_in_range`
  — tier-2 fallback when no sentence boundary exists in range.
- `TestClampStartToBoundary::test_never_returns_a_boundary_that_produces_a_near_empty_clip`
  — a boundary sitting at `end_time` itself is excluded in favour of an
  earlier one (or the `min_start` fallback), never a zero-length clip.
- `test_generate_never_exceeds_the_hard_60s_cap_even_after_snap_widens_it`
  (extended, same test) — now also asserts `start_time == 16.0`,
  `end_time == 72.0`, `duration == 56.0`, and the exact new title
  `"Highlight segment 2."`, pinning the corrected end-to-end behavior
  instead of only checking `duration <= 60.0`.

**Validation commands run:**
- `pytest backend/tests/test_clips.py -v` → 30 passed (27 previous + 3
  new; the pre-existing 27 unaffected in intent, the widened test now
  asserts the corrected values).
- `pytest backend/tests -v` → 267 passed (full suite, no regressions from
  264 baseline).
- `ruff check backend/app/services/clip_service.py backend/tests/test_clips.py`
  → all checks passed.

**Not touched:** `highlight_detection.py`, B-roll files — out of scope,
per the story and this fix's own constraints.

Handing back to `tester` for a second pass against this fix, per the
original QA note — not cleared for founder release approval yet.

**Design sanity-check (one-directional extend, never trim):** Read `_extend_to_sentence_boundary` fully. Aside from the clamp bug above (which lives outside this function, in the caller), the function itself only leaves `start_time`/`end_time` off a boundary in the already-disclosed case where no reachable boundary exists within `allowed_duration`/`floor` — which the story's bounds section defines as acceptable. No other hidden violation found in the function itself.

**Real-transcript check on the flagged assumption (Whisper segments generally end in terminal punctuation):** No real transcript fixtures existed in the repo to check this against, so I generated one: synthesized ~14s of speech via macOS `say` (5 sentences, deliberately including one with **no** period in the source text, to simulate a trailed-off/interrupted thought), converted to 16kHz mono WAV, and ran it through the actual `local` Whisper backend path (`faster_whisper`, same `base` model class `transcription.py` uses) — not a mock.

Result: **all 5 segments came back ending in `.`/`?`**, including the deliberately-unpunctuated one (Whisper's language model added a period even though the source utterance did not grammatically finish). This is a genuine, real-transcript data point (not synthetic-fixture-only), and it:
- **Confirms** the story's core assumption holds in practice — a sentence-boundary signal will almost always exist for `_extend_to_sentence_boundary` to find.
- **Surfaces a new, different risk worth flagging to the founder**: Whisper tends to *add* punctuation predictively, even to speech that was actually cut off or trails off arbitrarily (e.g. by a VAD silence cut). "Segment ends in `.`/`!`/`?`" is a strong *availability* signal but an imperfect *correctness* signal — occasionally a clip could stop extending at a Whisper-punctuated boundary that isn't actually where the speaker's thought ended. Inherent to Whisper, not a bug in `clip_service.py`, out of scope to fix under this story — flagging for awareness only.

**Risks/gaps for the founder before approving release (in addition to the bug above):**
- First-segment start lands at the segment's actual `start_time`, not literal `0.0`, when there's leading silence — cosmetic/wording mismatch vs. AC2's phrasing, not itself a functional issue.
- Whisper's terminal punctuation is a reliable *availability* signal but not a perfect *completeness* signal (see real-audio test above) — pre-existing characteristic of Whisper, not introduced by this change, no current test/fixture covers this nuance.
- One-directional design (extend-only) is a deliberate, disclosed trade-off (`ponytail:` comment names the upgrade path) — not a defect on its own.

**Sign-off:** One bug found (above) that fails AC2 in a reproducible `in_depth`-only scenario (and, per the severity note, drops the clip's own anchor highlight from its window); all other acceptance criteria pass. Not fixing it myself — flagging back to backend-agent (owns `clip_service.py`) per QA's scope. Per governance, release sign-off requires the founder's explicit go-ahead regardless of test-plan outcome; recommending the bug be fixed (or the founder explicitly accept the risk) before founder approval, given it's a direct regression against this story's own AC2, introduced by this story's own new clamp code, not a pre-existing/out-of-scope issue.

#### QA re-verification (tester, 2026-09-06)

**Scope:** re-verifying `backend-agent`'s "Fix" subsection above against
the AC2/title bug this QA pass originally found, per the story's second
QA round.

**1. Independent test run (not trusting the report):**
- `./.venv/bin/python -m pytest backend/tests -v` → **267 passed**, 0
  failed. Matches backend-agent's claim exactly.
- `./.venv/bin/python -m pytest backend/tests/test_clips.py -v` → **30
  passed** (confirmed `TestClampStartToBoundary` × 3 present and passing,
  plus the extended `test_generate_never_exceeds_the_hard_60s_cap_even_after_snap_widens_it`).
- `ruff check backend/app/services/clip_service.py backend/tests/test_clips.py`
  → all checks passed.
- `git status`/`git log` confirm only `clip_service.py` and
  `test_clips.py` are touched by this fix (working-tree modifications,
  not yet committed) — no drift into `highlight_detection.py` or B-roll
  files, per the story's own scope constraint.

**2. Read the actual new code (not just the tests):** Read
`_clamp_start_to_boundary()` and `_fallback_title_source()` and their call
sites in `create_clips_from_highlights()` directly (lines 248-326,
495-506). Confirmed the fix is real, not tests-fitted-to-behavior:
- `_clamp_start_to_boundary` searches forward from `min_start = end_time -
  allowed_duration`, tier 1 = sentence-terminal starts, tier 2 = any
  segment start, both restricted to
  `min_start <= s <= end_time - _MIN_SNAPPED_DURATION` (excludes
  near-`end_time` candidates), `min(...)` of whichever tier is non-empty.
  `end_time` is never touched.
- `_fallback_title_source` returns the anchor's text only if
  `start <= anchor.start_time and anchor.end_time <= end`; otherwise the
  first in-window segment; otherwise `""`.
- Call site (lines 488-497): the clamp only fires when
  `end_time - start_time > allowed_duration`, i.e. exactly the case this
  QA round's bug was scoped to.

**3. Exact repro re-verified:** the extended
`test_generate_never_exceeds_the_hard_60s_cap_even_after_snap_widens_it`
uses my exact original fixture (10 contiguous 8s highlighted segments,
`in_depth`) and now asserts `start_time == 16.0`, `end_time == 72.0`,
`duration == 56.0`, `title == "Highlight segment 2."` — all four passed.
Traced the arithmetic independently (`min_start = 72 - 60 = 12`,
`latest_start = 72 - 8 = 64`; sentence-terminal starts in `[12, 64]` are
`16, 24, ..., 64`; `min(...) = 16.0`) — matches the code and the test. The
original bug (mid-segment `start_time=12.0`, title from an out-of-window
anchor) is gone at this exact repro.

**4. Does the new fallback (`return min_start` when neither tier finds a
boundary) reopen the bug at a rarer trigger, or is it an acceptable
defined last resort?** Acceptable — genuinely narrower, not a relocation
of the same bug:
- The clamp only ever fires for `in_depth` clips (`fast`: `30+5=35`,
  `auto`: `50+5=55` — neither exceedable by a `≤2*2.5s=5s` snap-widen;
  only `in_depth`'s `min(60+5,60)=60` has zero slack). Blast radius
  unchanged from the original bug report.
- The search window for a reachable boundary is `[end-60, end-8]` — **52
  seconds wide**. For the final `min_start` fallback to be reached, a real
  transcript needs *zero* segment starts anywhere across a 52s span.
  Whisper emits segments every few seconds (confirmed independently this
  session via the real-audio Whisper test already in the Fix notes above)
  — this is not a realistic transcript shape, unlike the original bug
  which fired unconditionally on the common `in_depth`-plus-snap-widen
  path.
- Algebraic check on the fallback's own safety: the clamp only fires when
  `start_time >= floor` already held and `end_time - start_time >
  allowed_duration`, so `min_start = end_time - allowed_duration >
  start_time >= floor` always — the fallback can't cross `floor` (no
  non-overlap regression) and duration is always exactly
  `allowed_duration` (>= 8.0), so never near-empty. It is bounded on every
  dimension except "on a boundary."
- **Caveat worth flagging, not blocking:** `test_never_returns_a_boundary_
  that_produces_a_near_empty_clip` is the only test that reaches this
  final fallback, and it does so by passing `allowed_duration=15.0`
  directly to the unit function — a value the production call site can
  never actually produce (`allowed_duration` is always 35, 55, or 60).
  The fallback path itself has no test at a realistic `allowed_duration`,
  and — as that same test incidentally demonstrates — when it is reached,
  `start_time` (65.0 in that test, inside segment `[60.0, 80.0]`) is
  **not** on any boundary, i.e. the same category of violation as the
  original bug, just behind a condition that real Whisper transcripts
  won't realistically hit. This is consistent with the story's own bounds
  clause ("fall back to... the unsnapped duration-based edges" when no
  boundary is reachable), so I'm not treating it as a new blocking bug —
  but it should be named explicitly to the founder as a residual,
  effectively-untested edge rather than silently assumed impossible.
- Minor accuracy nit for backend-agent (non-blocking): the source comment
  on this fallback says "a single segment spanning the whole window" —
  the actual condition is "no segment start falls in
  `[min_start, latest_start]`," which can happen with multiple short
  segments too, not only one long one. Same for
  `test_never_returns_a_boundary_that_produces_a_near_empty_clip`'s name/
  framing — it's actually pinning the raw-subtraction-fallback value, not
  just the near-empty exclusion. Doesn't affect correctness, just future
  readability.

**5. Does the title fix's `""` fallback produce a sensible title, or
something worse?** Confirmed by reading (not just trusting the claim):
`_title_from_window(..., fallback=_fallback_title_source(...))` calls
`_auto_title(fallback)` when no in-window sentence passes the length
filter; `_auto_title("")` returns `"Untitled clip"` (line 81-82). This
path has no dedicated test (the repro fixture always has an in-window
segment to fall back to), but the two-line path is simple enough that
read-verification is sufficient — flagging as read-verified, not
test-covered, for the record.

**Carried forward, not newly introduced by this fix:** the anchor-loss
behavior from my original severity note (the generated clip can still not
contain the highlighted segment that seeded it, in this exact repro
`[0.0, 8.0]` is outside the final `(16.0, 72.0)` window) is unchanged by
this fix — the fix only stopped it from being *mislabeled* (title now
correctly reflects what's actually in the clip). No AC requires a clip to
contain its own anchor, so this isn't an AC failure, but it's a real
behavior the founder should knowingly accept, alongside the
already-disclosed one-directional-extend trade-off and the
Whisper-punctuation-as-availability-not-correctness-signal risk.

**6. Full AC re-check:** Re-ran the full suite (267 passed) and re-read
the non-overlap argument (point 4 above) and `_extend_to_sentence_
boundary`/`_pad_clusters`/`_snap_to_speech` — none of these were touched
by this fix, and their existing tests all still pass. No regression found
in AC1, AC3 (duration bound — the clamp still caps at exactly
`allowed_duration`), AC4 (non-overlap — re-derived algebraically above),
AC5 (no-punctuation fallback — untouched code path, its own tests still
pass), AC6, AC7.

**Verdict on the fix: PASS.** The reproducible AC2 violation from the
prior QA round (mid-segment `start_time`, anchor-outside-window
mistitling) is fixed at the exact repro, confirmed independently via
fresh test run + direct code trace, not just by trusting the report. One
residual, narrow, disclosed risk remains (point 4's fallback path, real-
world-unreachable given normal Whisper segment cadence but untested at a
realistic `allowed_duration`) — recommend backend-agent add one test at a
production `allowed_duration` (35/55/60) covering that branch before/along
with a future change, but this does not block release on its own.

**Overall recommendation:** Ready for founder release-approval review.
This is a governance gate — QA does not approve release. Recommending the
founder proceed, with the following disclosed, accepted-not-fixed items
in view: (a) the fallback-path residual above, (b) one-directional
extend-only design (deliberate trade-off, `ponytail:`-documented), (c)
Whisper's terminal punctuation as an availability-not-correctness signal
(pre-existing Whisper characteristic, not introduced by this change), (d)
anchor-highlight-outside-final-window can still occur (no AC violation,
carried forward from the original repro, now correctly titled instead of
mistitled).


#### Deployment (devops, 2026-09-06)

**Shipped:** the sentence-boundary clip-boundary fix, exactly as described
in the Implementation/Fix subsections above — `_extend_to_sentence_boundary`,
`_clamp_start_to_boundary`, `_fallback_title_source`, and the two new
constants (`_SENTENCE_BOUNDARY_ALLOWANCE_SECONDS`, `_HARD_MAX_CLIP_DURATION`)
wired into `create_clips_from_highlights()`. No B-roll code shipped as part
of this deploy — confirmed below.

**Files committed:**
- `backend/app/services/clip_service.py`
- `backend/tests/test_clips.py`
- `team/backlog.md` (this file — documentation only)

**Verified before deploy (independently re-run, not just trusted from the
Fix/QA-re-verification notes above):**
- `pytest backend/tests -v` → **267 passed**, 0 failed.
- `ruff check backend/app/services/clip_service.py backend/tests/test_clips.py`
  → clean.
- `ruff check backend/app/ backend/tests/` (matches
  `.github/workflows/ci.yml`'s actual Lint step) → **10 pre-existing
  findings, 0 in the two files this story touches** — same count the prior
  B-roll DevOps note (2026-09-05) already recorded, confirmed via `git
  blame` there to predate this release. Not introduced by, or fixed by,
  this deploy; CI's Lint step is red on `main` independent of this change.
- `git status`/`git diff` isolated the change to exactly the two backend
  files above before committing; the pre-existing B-roll working-tree
  changes (`backend/app/models/broll_asset.py`, `backend/app/models/clip.py`,
  `backend/app/schemas/clip.py`, `backend/app/services/broll_sourcing.py`,
  `backend/app/services/video_render.py`, `backend/app/config.py`,
  `backend/app/services/reframe.py`, both new Alembic revisions, the
  `test_broll.py`/`test_reframe.py`/`test_video_render.py` test changes, and
  the frontend B-roll files) were confirmed present before this task began
  and are **not part of this commit** — committed via a path-scoped `git
  commit -- <path>...` (not `git add -A`/`git commit -a`), which commits
  only the named paths' content and leaves everything else in the index
  exactly as it was. Verified `git status --porcelain` before and after the
  commit shows those B-roll entries byte-identical (still staged/modified,
  untouched, not committed).
- Note on `team/backlog.md` itself: the working copy of this file also
  carries other already-staged, pre-existing backlog entries from before
  this task (new stories: "Source Rights Declaration & Copyright-Risk
  Guidance", "Split-screen: detect overlapping speakers...", and "B-roll:
  fix duplicate auto-insert, add placement options, full-clip coverage") —
  these are documentation-only backlog prose, not runtime code, and were
  already present in the working tree/index prior to this session; they
  ride along in this commit because `backlog.md` is committed as a whole
  file, but no B-roll (or other) *code* is included. Flagging for
  transparency rather than treating the file as untouched.

**Migration:** none. This story adds no model/schema change — `alembic
heads` is still `e276d71b9110` (the B-roll story's own pending revision,
uncommitted, untouched by this deploy).

**Deploy mechanism (this project's actual current state, not invented):**
No CD/build-push job exists — `.github/workflows/ci.yml` only lints and
tests backend + frontend on push to `main`/PRs; there is no job that builds
a Docker image, pushes it, or applies it to any host. At this project's
stage, **the deploy artifact is the commit to `main` itself**: this backend
service has no separate staging/prod target beyond what
`docker-compose.yml` describes for whichever host runs it (per the prior
B-roll DevOps note, 2026-09-05) — that host pulls `main` and rebuilds. This
sandbox has no `docker`/`docker-compose` binary (confirmed), so no
container was built or restarted from here, same constraint the prior
B-roll deploy note hit. Nothing about this change (code-only, no new env
var, no migration) requires anything beyond that host doing its normal
`git pull` + `docker compose build api worker` + `docker compose up -d api
worker` for the `backend`/worker image(s) — no `web`/frontend rebuild
needed since no frontend file changed.
**Not pushed to the remote** — this task did not request a push, so `main`
on the remote is unchanged and CI has not run against this commit.

**Rollback steps:**
1. `git log --oneline -3` to confirm this fix's commit SHA is at `HEAD`
   (reported below).
2. Not a full `git revert <this-commit-SHA>` -- this commit's
   `team/backlog.md` hunk also carries pre-existing, unrelated backlog
   prose (other BA-drafted stories, plus this story's own
   Implementation/QA/Fix/QA-re-verification history) that a revert would
   delete along with the fix -- the same trap the prior B-roll DevOps note
   flagged for 6bb3bef. Instead, revert only the code paths: restore
   backend/app/services/clip_service.py and backend/tests/test_clips.py to
   their state from the commit immediately before this fix, then commit
   that (leaves team/backlog.md history intact).
3. No `alembic downgrade` needed — no migration shipped.
4. No feature flag exists for this change (none was added; it's unconditional
   logic inside `create_clips_from_highlights()`) — revert is the only
   toggle.
5. On the actual deploy host: rebuild/redeploy the `backend`/worker image
   from the commit immediately before this fix (parent SHA) and restart via
   `docker compose up -d --no-deps api worker` (same pattern as the prior
   B-roll rollback note) — no data backfill or schema concern either way.

**Handing off to `seo-geo` + `marketer`** — this is an internal quality fix
to existing output (no new user-facing surface, no new page/feature to
announce), so likely low/no marketing action; flagging for their own call
on whether it's worth a changelog/quality-improvement note.

---

### Source Rights Declaration & Copyright-Risk Guidance

**Status:** in-design

**Founder approval (2026-09-05):** Approved for scope — Designer to start.

**Priority:** P1

**Module:** Video Upload & Processing (primary); non-blocking risk indicator
also surfaces in Clip Library and Export & Publish. Does not touch B-roll
Sourcing — that module already sources copyright-safe cutaway footage from
Pexels/Pixabay and is unrelated to the main source video a user submits.

As a creator submitting a video (upload or URL) to turn into Shorts, I want
to declare what rights I have to the source footage and get plain-language
guidance on the copyright risk of my choice, so that I make an informed
decision before publishing instead of assuming any clip is automatically
safe.

**Context:** Today `VideoProject` (upload or URL submission) captures no
rights/licensing information at all. The founder wants a workflow, not a
guarantee: this feature cannot determine fair use (only a court can) and
must not claim to prevent copyright strikes or Content ID claims. It also
must not help evade detection — that was explicitly considered and
rejected.

**What this is:**
- A required rights-status declaration captured at video submission time,
  alongside optional free-text attribution/license notes.
- Rights-status options: `own_footage`, `licensed`, `public_domain_or_cc`,
  `fair_use_claim`, `other_broadcast_content`.
- Static, per-option educational guidance shown at the point of choice.
- A later non-blocking risk indicator surfaced in the Clip Library and
  Export & Publish flows, reflecting the declared status only.

**What this is not (non-goals):**
- Not a legal-advice engine and not an automated fair-use determination —
  no analysis of the actual footage, no scoring, no AI judgment call.
- Not a guarantee of zero copyright strikes or zero Content ID claims for
  any choice, including `own_footage` or `public_domain_or_cc`.
- Not a tool to help clip broadcast/TV/news/sports content while evading
  Content ID or otherwise avoiding detection — this was explicitly
  requested by the founder as a separate option and rejected; do not build
  it under this or any other story.
- Does not block, gate, delay, or auto-reject upload, processing, editing,
  or export/download based on the declared rights status. `VideoProject`
  and `Clip` `status` enums (per `CLAUDE.md`) are unchanged — this is a
  new, separate field, not a new pipeline state.

**Data captured on submission:**
- `rights_status` (one of the five values above) — required, no default
  that lets a submission silently skip the choice. Editable after creation
  (a user can correct/update their declaration later), following the same
  "editable, never locked in" principle `CLAUDE.md` already applies to
  B-roll auto-insertion.
- `rights_notes` (optional free text, e.g. license terms, attribution, or
  fair-use rationale) — stored, never validated for accuracy.
- Existing `VideoProject` submissions created before this ships must
  continue to work without error (backfilled to a default status, e.g.
  `other_broadcast_content`, so nothing silently claims a rights basis the
  user never asserted).

**Guidance copy requirements (content, not layout — Designer owns
presentation):**
- `own_footage` / `licensed`: low-risk framing; a reminder that licensed
  content must be used within the license's actual terms.
- `public_domain_or_cc`: reminder to verify the specific archive/work is
  actually public domain or CC-licensed, and that this app does not verify
  the claim on the user's behalf.
- `fair_use_claim`: must explicitly state, in plain language, that there
  is no safe clip-length threshold — short duration (e.g. "under 30
  seconds") is not a legal defense — and that fair use is a case-by-case
  balancing test where transformative use (commentary, criticism,
  teaching, added editorial value) matters, not length. Must state that
  Content ID matching is automated and cannot evaluate fair use, so even a
  legitimately fair-use clip can still get a claim.
- `other_broadcast_content` (e.g. TV/news/sports the user has no rights or
  fair-use basis for): highest-risk framing; state plainly that broadcast
  content is heavily fingerprinted and most likely to trigger a claim, and
  that repeated re-clipping without substantial original commentary can
  also trigger YouTube's separate reused-content policy independent of any
  copyright claim.
- All guidance copy must distinguish, at least once, a Content ID claim
  (automated, non-punitive: block/mute/monetize/track) from a copyright
  strike (manual takedown by the rights holder; 3 in 90 days terminates
  the channel) — these are not the same thing and founder/designer should
  not conflate them.

**Risk indicator (later, non-blocking):**
- Clip Library and Export & Publish surface a simple indicator reflecting
  the project's declared `rights_status` (e.g. low/medium/high risk
  framing tied to the five statuses above) — informational only, never
  disables edit, render, or download.

**Acceptance criteria:**
- Submitting a video (upload or URL) without selecting a `rights_status`
  is rejected by the API with a validation error.
- Each of the five `rights_status` values, when selected, surfaces its own
  distinct guidance copy per the content requirements above.
- The `fair_use_claim` guidance text contains an explicit statement that
  clip duration alone is not a legal defense.
- Guidance copy anywhere in the flow does not state or imply that any
  rights-status choice guarantees no copyright strike or no Content ID
  claim.
- `rights_status` and `rights_notes` are editable on an existing
  `VideoProject` after creation, without affecting its processing
  `status`.
- Existing `VideoProject` rows created before this feature ships load and
  operate without error after the migration (default-backfilled).
- Export/download completes successfully regardless of declared
  `rights_status` — the risk indicator never blocks, delays, or disables
  render or download.
- No new value is added to the existing `VideoProjectStatus` or `Clip`
  `status` enums as part of this feature.

---

#### Designer

Reused existing patterns throughout — no new primitive components. Checked
`frontend/src/components/videos/VideoSubmitForm.tsx`, `pages/VideoDetailPage.tsx`,
`pages/ProfilePage.tsx`, `components/clips/ClipCard.tsx`, `ClipGrid.tsx`,
`ExportPanel.tsx`, and `types/index.ts` before writing this. Two corrections
to the role brief: `AnimatedInput` does not exist in this codebase (use a
plain styled `<textarea>`/`<input>` per the classes `VideoSubmitForm` already
uses); `MeshBackground` lives in `components/layout/`, not `components/ui/`
— neither is needed here anyway, this feature adds form fields and a badge,
not a new page background.

**1. Video submission — `VideoSubmitForm.tsx` (add a required section)**

Add a new top-level section between the "Ingestion Source" block and the
existing collapsed "AI Clip Customization Options" disclosure. **Do not**
put it inside `showAiSettings` — that panel defaults collapsed, and a
required field with no default cannot live somewhere the user might never
open.

- Section label (same uppercase-tracking style as other field labels):
  "Source Rights — What footage is this?"
- Markup: `<fieldset>` + `<legend>` with `role="radiogroup"`, five buttons
  styled exactly like the existing `clipLength`/`framingMode` option grids
  in this file (`border-primary bg-primary/15 text-primary` selected /
  `border-glass-border bg-background/50 text-muted-foreground`
  unselected), each with `role="radio"` and `aria-checked`. Single column
  on mobile, 2-col grid at `sm:` — five options don't divide evenly into 3,
  so don't force the existing `grid-cols-3` pattern here.
- Option labels (plain language, not the raw enum):
  - "My own footage" (`own_footage`)
  - "Licensed content" (`licensed`)
  - "Public domain / Creative Commons" (`public_domain_or_cc`)
  - "Fair use claim" (`fair_use_claim`)
  - "Other broadcast content (TV/news/sports, no rights claimed)"
    (`other_broadcast_content`)
- **No option is pre-selected.** `canSubmit` gains
  `rightsStatus !== null` alongside the existing title/file/url checks, so
  the `GradientButton` stays disabled until a choice is made — this is the
  UI-side backstop for the API's required-field validation, not a
  replacement for it.
- Below the radiogroup, one guidance panel (a `GlassCard`-style inset box:
  `rounded-xl border border-glass-border bg-background/50 p-3.5 text-xs`)
  that swaps its content based on the selected option — inline, appearing
  the moment a radio is chosen, never a hover tooltip (this must work on
  touch). See "Guidance copy placement" below for content per option.
- Optional `rights_notes` textarea directly under the guidance panel,
  visible regardless of which option is selected (not gated behind
  `fair_use_claim`, since e.g. `licensed` also benefits from attribution
  notes): label "Notes (optional) — license terms, attribution, or your
  fair-use rationale", `<textarea rows={2}>` using the same input classes
  as the existing `#video-title` field, placeholder text kept generic.
- Validation error path: reuse the existing `error` block at the bottom of
  the form (the `rounded-xl bg-destructive/15 p-3 text-xs text-destructive`
  paragraph) — an API 422 for a missing `rights_status` surfaces there
  exactly like any other submit error today. No separate error UI needed.

**Guidance copy placement (content owned by BA/story; this is presentation
only):**

- The panel always shows one persistent line, regardless of selection,
  distinguishing a **Content ID claim** (automated match — block, mute,
  monetize, or track; not a strike) from a **copyright strike** (a manual
  takedown by the rights holder; 3 in 90 days terminates the channel). Put
  this as a small fixed footer inside the guidance panel (a `border-t
  border-glass-border pt-2 mt-2 text-[11px] text-muted-foreground` row)
  so it's visible under every option, not only `fair_use_claim`'s text —
  the AC requires it stated "at least once," and a user who never touches
  `fair_use_claim` should still see it.
- `own_footage` / `licensed`: calm/neutral framing (muted-foreground text,
  no color accent) — low-risk language, plus the license-terms reminder
  for `licensed`.
- `public_domain_or_cc`: same neutral framing, plus the
  "verify it yourself — we don't check the claim" reminder.
- `fair_use_claim`: amber accent (`border-amber-500/30 bg-amber-500/10
  text-amber-400`, matching the `rendering`/in-progress tone already used
  in `StatusBadge`/`ClipCard`), containing verbatim the "no safe
  duration/length is not a defense," case-by-case balancing test, and
  "Content ID can't evaluate fair use" language from the story.
- `other_broadcast_content`: red accent (`border-destructive/30
  bg-destructive/10 text-destructive`), containing the "heavily
  fingerprinted, most likely to trigger a claim" and separate
  reused-content-policy language from the story.
- Never use the words "safe," "guaranteed," "protected," or a percentage/
  score anywhere in this panel, on any option — matches the AC and keeps
  it visually distinct from `ViralityScoreBadge`'s percentage treatment
  elsewhere in the app, which this is explicitly not.

**2. Edit surface — post-creation update of `rights_status`/`rights_notes`**

Lives on `VideoDetailPage.tsx`, inside the existing "Project Overview"
`GlassCard`, as a new sub-block below the source/duration/highlights/output
stat grid and above the action buttons row. Not a separate page/route —
this is a project-level attribute, same surface as everything else about
the project.

- Follow the `ProfilePage.tsx` pattern exactly: a child component (e.g.
  `RightsDeclarationEditor`) mounted only once `video` is loaded, that
  initializes its local `rightsStatus`/`rightsNotes` state from props once.
  This is required, not optional — `VideoDetailPage` polls `getVideo` every
  3 seconds (`POLL_INTERVAL_MS`), and a form whose state is wired directly
  to the polled `video` object will clobber in-progress typing every poll
  tick.
  - Default collapsed view: a compact row showing the current
    `rights_status` as a label (reuse the risk-badge styling from section
    3) plus an "Edit" text-button (same treatment as the "Re-export with
    new edits" link in `ExportPanel.tsx` — small underlined muted text).
  - Expanded view: the same radiogroup + guidance panel + notes textarea
    from the submission form, pre-populated, with "Save" (`GradientButton`,
    small) and "Cancel" (text button) actions. Save calls the update
    endpoint and re-collapses on success; failure shows an inline error the
    same way `ProfileEditForm` does (`border-destructive/30 bg-destructive/10
    text-destructive` banner above the form).
  - Editing/saving this must never touch `video.status` or trigger the
    processing poll/reprocess flow — it's a sibling field, not a pipeline
    step.
- **Legacy/backfilled projects:** a project whose `rights_status` was
  silently backfilled to `other_broadcast_content` (pre-feature rows, per
  the story's migration note) must not render as if the user actively
  declared it. Show a distinct "Not yet declared" state instead of the
  normal collapsed badge — an amber-outlined pill reading "Rights not
  declared — please confirm" that opens directly into the expanded editor
  with nothing pre-selected, same as a first-time submission. This needs a
  way to distinguish "user picked `other_broadcast_content`" from
  "system backfilled it" — flag for Backend/Database: a boolean (e.g.
  `rights_confirmed_by_user`) or a nullable `rights_status` that the API
  coerces to a default only for *display*, whichever is simpler on your
  side; Designer has no preference on the mechanism, only that the UI can
  tell the two apart.

**3. Non-blocking risk indicator — Clip Library and Export & Publish**

A single new small badge component, `RightsRiskBadge`, styled like
`StatusBadge.tsx` (`Record<RightsStatus, { label, className }>` → a pill),
not like `ViralityScoreBadge` (no score, no percentage — informational
label only, e.g. "Rights: Lower risk" / "Rights: Fair use claim" /
"Rights: High risk"). Always prefix with "Rights:" — never a bare
"High risk" pill, which next to `ClipCard`'s existing
`bg-destructive/15 text-destructive` `failed`-status pill would read as
"this clip failed."

Risk-tier mapping (labels only — no score, matches the story's
"low/medium/high risk framing"):
- `own_footage`, `licensed` → "Rights: Lower risk" (muted/neutral or
  emerald-tinted, low visual alarm)
- `public_domain_or_cc` → "Rights: Verify source" (muted/neutral —
  distinct wording from "lower risk" since the user hasn't verified
  anything, we're just not flagging it as elevated)
- `fair_use_claim` → "Rights: Fair use claim" (amber, matches the
  submission-flow accent)
- `other_broadcast_content` → "Rights: High risk" (red/destructive accent)

Placement:
- **Clip Library (`ClipCard.tsx`, used by both `ClipGrid.tsx` on
  `ClipsPage` and inline on `VideoDetailPage`):** add `RightsRiskBadge`
  into the existing card-body footer row (`pt-2 border-t border-glass-border
  flex items-center justify-between gap-2`), alongside `ViralityScoreBadge`
  — not as a fourth absolute-positioned overlay on the already-crowded
  `aspect-[9/16]` thumbnail (which already carries a status pill and a
  duration badge). On narrow cards, if both badges don't fit on one line,
  wrap to a second line rather than truncating either.
- **Export & Publish (`ExportPanel.tsx`):** add the same badge into the
  header row (next to the existing "1080 × 1920 HD" pill), or immediately
  under the panel title if horizontal space is tight at the `ClipEditorPage`
  studio's 7-column layout width. It must render in every export state
  (`idle`/`rendering`/`ready`/`failed`) unchanged — it reflects the
  project's declared rights, not the export's own state, and per the
  acceptance criteria must never disable, delay, or gate the Export/Download
  button in any state.

**Data-dependency flag for Backend/Frontend build (not a design decision,
just surfacing it before build starts):** `rights_status` lives on
`VideoProject`; `Clip` (frontend `types/index.ts`) has no rights field, and
`ClipCard` currently receives only `clip: Clip`, `ExportPanel` only
`clipId`. Rendering `RightsRiskBadge` in either place needs the parent
project's `rights_status` available where the badge renders — either
denormalized onto the `Clip`/clip-list and clip-detail API payloads, or the
parent `VideoProject` passed down as an additional prop from
`VideoDetailPage`/`ClipEditorPage` (which already fetch it or could).
Designer has no preference on which; flagging so it isn't discovered
mid-implementation.

**Responsive behavior (all three surfaces):** every new element reuses
existing responsive breakpoints already in these files — `sm:` 2-column
grids for the rights radiogroup and stat grids, single column below that,
`lg:` 12-column split unaffected on `ClipEditorPage`. No new breakpoints
introduced.

**States covered:** required-but-unselected (submit disabled, no default
guidance shown), five selected states (distinct guidance + notes visible),
API validation error (existing error banner), edit-surface
collapsed/expanded/saving/save-failed, legacy-backfilled "not declared"
state, and the risk badge's four label variants rendered identically across
loading/rendering/ready/failed export states.

---

### B-roll sourcing & auto-insertion (Pexels/Pixabay)

**Status:** approved-for-release (deploy blocked — see DevOps note below)

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

**Founder approval (2026-09-05):** Approved for release. DevOps to deploy.

#### DevOps (2026-09-05)

**Change scope confirmed:** commit `6bb3bef` touches
`app/schemas/broll.py`, `app/services/broll_sourcing.py`,
`app/services/video_render.py`, and two frontend components
(`BrollPanel.tsx`, `BrollSearchModal.tsx`) + `brollService.ts`. No new
Alembic revision — `alembic heads` is still `d4a92c17e6b3`
(`video_project_defaults`), unchanged by this commit — so this is a
**code-only deploy**, no schema migration to run or roll back. No new env
vars: `PEXELS_API_KEY`/`PIXABAY_API_KEY` were already declared in
`docker-compose.yml` (`api` and `worker` services) before this story.

**Pre-flight check performed:** confirmed (presence-only, values not read
or printed) that both the repo-root `.env` (the file `docker-compose.yml`
reads, since it lives next to that compose file) and `backend/.env` (used
by local `uvicorn --reload`) have non-empty `PEXELS_API_KEY` and
`PIXABAY_API_KEY` — a stack that comes up with these blank would run green
with the entire B-roll feature silently dead (search returns nothing).
Also checked the root `.env` against `docker-compose.yml`'s Postgres block,
which hard-fails (`${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD in .env}`) if
unset: the root `.env` on this machine does **not** define `POSTGRES_USER`
/ `POSTGRES_PASSWORD` / `POSTGRES_DB` (it's shaped for local `uvicorn
--reload` dev instead, with `DATABASE_URL` set directly), so `docker
compose up` would abort immediately on this host with the current `.env`.
**This is the one blocking gap for an actual deploy on this host** —
flagging it as pre-existing and unrelated to the B-roll diff, not fixed
here (out of scope for this story, and `.env` contents aren't touched per
policy). Founder/whoever owns the deploy host needs to add those three
values before `docker compose up` will work at all.

**Executed in this environment (sandbox has no Docker — see below):**
- `pytest tests/ -q` → **248 passed**, run against the working tree, which
  is `6bb3bef` plus the still-uncommitted split-screen fix
  (`app/services/reframe.py` / `tests/test_reframe.py` — `git status`
  shows both modified). The B-roll code paths themselves are identical to
  `6bb3bef`; the 246 the Tester recorded was measured before the
  split-screen fix landed on top, so both numbers are consistent (246 + 2
  new split-screen tests = 248), but the exact artifact this command ran
  against is not byte-identical to what the runbook below deploys
  (`6bb3bef` alone).
- `ruff check app/ tests/` → 10 pre-existing findings (line-length/import-
  order/style, none introduced by this commit — verified via `git blame`
  that the 3 hits inside `broll_sourcing.py` predate this release, from
  `cb120968`). None are new to this release, but worth stating plainly:
  this means `.github/workflows/ci.yml`'s `Lint` step is currently red on
  `main` independent of the B-roll story — a push to main today fails CI
  before reaching the test step. Not fixed here (app-code lint fixes are
  out of this role's scope); flagging so it's visible.
- Frontend: `npm run type-check` (tsc -b --noEmit) → clean. `npm run
  build` → succeeds, `dist/` produced.

**Could not execute from this sandbox (no `docker`/`docker compose`
binary available — Docker Desktop isn't installed here):**
- `docker compose build api worker web`
- `docker compose up -d` (the `api` container's entrypoint runs
  `alembic upgrade head` automatically on start, per
  `backend/docker-entrypoint.sh` — a no-op here since head is unchanged)
- Post-deploy smoke check: `GET /ready` on `api` (verified route in
  `app/main.py` — checks DB connectivity, returns 503 if degraded; `GET
  /health` is liveness-only), then one manual B-roll search request
  against `GET /api/v1/broll/search` (verified route in
  `app/routers/broll.py`) to confirm Pexels/Pixabay results return
  (validates the API keys are live, not just present)

**Runbook for the actual deploy host:**
1. `git pull` (or deploy image built from `6bb3bef`) on the host that runs
   `docker-compose.yml`.
2. Add `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` to that host's
   root `.env` (missing on this sandbox's checkout — see above) and
   confirm `SECRET_KEY`, `PEXELS_API_KEY`, `PIXABAY_API_KEY` are non-blank
   there too.
3. `docker compose build api worker web`
4. `docker compose up -d` — `api` runs migrations (no-op this release)
   then serves; `worker` and `web` restart against the new image.
5. Smoke-test: `curl` the `api` container's `/ready` endpoint for a 200,
   then exercise one B-roll auto-insert and one manual search from the
   clip editor UI end to end.

**Rollback plan:**
- No `alembic downgrade` needed — this release added no migration.
- Redeploy the previous image, built from `7fc172e` (the commit
  immediately before `6bb3bef`): `docker compose up -d --no-deps api
  worker web` after rebuilding/pulling that revision's image.
- Deliberately **not** `git revert 6bb3bef` — that commit also bundles the
  `.claude/agents/` roster restructure and `CLAUDE.md`/`backlog.md`
  updates unrelated to the B-roll code; a revert would drag those back
  too. Prefer redeploying the prior image over reverting the commit.
- Since the schema is untouched, rollback is code-only and reversible in
  either direction without data loss or backfill concerns.

---

### Split-screen: detect overlapping speakers averaged away by a dominant talker

**Status:** done (2026-09-05)

Founder reported split-screen wasn't triggering for simultaneous speakers.
Root cause: `_conversation()` in `app/services/reframe.py` decided
split-screen from one whole-shot mouth-activity average per face; a real
but brief overlap inside a shot where one person otherwise talks more
overall got averaged into "monologue with a listener" and never split.

**Fix:** where the whole-shot average rules one candidate dominant, a
second pass (`_overlap_in_a_window`) now checks rolling
`_SPEAKER_SEGMENT_SECONDS` (2s) windows for a stretch where both
candidates are active and close together, and splits if one is found.
Backward compatible — omitting the new `sample_interval` argument (as the
existing unit tests do) reproduces the old whole-shot-only check exactly.

**Tests:** added `test_overlap_inside_a_longer_take_is_not_averaged_away`
and `test_overlap_check_needs_a_sample_interval` to
`tests/test_reframe.py::TestSplitScreen`. Full backend suite: 248 passed
(246 baseline + 2 new).

**Note:** verified against synthetic motion data only — no real footage
reproduction was available. Recommend testing against an actual clip with
cross-talk before relying on it in production.

---

### B-roll: fix duplicate auto-insert, add placement options, full-clip coverage

**Status:** done (2026-09-06)

Founder reported three issues with B-roll after screenshots showed 3x
duplicated tiles from repeated "Auto-insert B-roll" clicks, and asked for
(1) a placement option (top/bottom/bottom-right/split-screen) and (2)
B-roll covering the whole Short instead of a few seconds near the start.

**Duplicate fix:** `auto_source_broll()`/`POST /clips/{id}/broll/auto` had
no guard against re-running on a clip that already had auto-sourced
B-roll — every click appended a full batch on top of whatever was there.
Added `BrollAsset.auto_generated` (migration `2c98d61a2ef4`, server
default `false` so existing rows are never touched); a re-click now
deletes only its own previous `auto_generated=True` batch before
inserting the new one, leaving anything added manually via search alone.

**Placement options:** added `Clip.broll_placement` (migration
`e276d71b9110`, enum `bottom_right`/`top`/`bottom`/`split`, default
`bottom_right` — the old hardcoded top-right PIP corner, closest match so
existing clips render unchanged). One choice per clip, same as
`framing_mode`. `_apply_broll()` in `video_render.py` branches on it:
`bottom_right` keeps the small bordered PIP card (now anchored
bottom-right via an ffmpeg runtime expression, `main_h-overlay_h-margin`,
since the card's height depends on each asset's own aspect ratio);
`top`/`bottom` are a full-width band across that third of the frame;
`split` scales the main video into a fixed top half (padded, since
ffmpeg's scale can't change mid-render) with B-roll filling the bottom
half only during its own window. Frontend: `BrollPanel.tsx` gained a
placement pill-selector (mirrors `ClipEditorPage`'s framing-mode toggle),
wired through `ClipEditorPage`'s existing `saveRenderChoice` path.

**Full-clip coverage:** `_extract_keywords_with_timing()` used to cap at
3 keywords and skip any transcript segment whose extracted phrase
repeated an earlier one — together these left everything past the first
~8 seconds with no B-roll at all. Now every spoken segment overlapping
the clip gets a window (capped at 20 as a safety bound on concurrent
provider searches and filter-graph size, not a target), snapped edge to
edge so windows cover `[0, clip_duration]` back to back with no gaps
before the first, between, or after the last.

**Tests:** 2 new (`test_auto_source_replaces_previous_batch_instead_of_duplicating`,
`test_auto_source_does_not_remove_manually_inserted_broll`); 3 new for
full-duration coverage (`TestExtractKeywordsWithTiming`); 1 new
parametrized real-ffmpeg render test across all four placements
(`test_render_composites_broll_at_every_placement`); 1 new frontend test
for the placement toggle. Backend: 257 passed. Frontend: 85 passed,
`tsc --noEmit` clean, `npm run build` clean, `oxlint` 0 new warnings.

**Note:** not yet QA-signed-off or founder-approved for release — this
entry documents dev-complete work, same governance gate as any other
story before DevOps deploys it.

---

## Done

_(Fully shipped stories move here, complete with every role's subsection, as
a record of what was built and why.)_
