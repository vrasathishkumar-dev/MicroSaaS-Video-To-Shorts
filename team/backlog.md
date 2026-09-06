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
