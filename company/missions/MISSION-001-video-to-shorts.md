# MISSION-001 · Video → Shorts

```text
Status:      ACTIVE — research not started
Opened:      2026-09-09 by the owner
Owner agent: vc-ceo
Verdict:     PENDING (vc-researcher, gate G-verdict)
Budget:      ₹0
Markets:     UAE / US / UK
```

> **Blocking question (T-001).** The owner said "use video to shorts github
> project". That could mean two different missions:
>
> **A.** He has an existing repo of his own to finish and commercialise →
> the mission starts from a code audit, and G1-G5 still apply before any more
> code is written.
> **B.** He means an open-source project as the *starting point* for a new
> product → the mission starts from the licence and the wedge.
>
> The CEO agent must get this answered before spending a research cycle.
> Everything below is written to work for both.

---

## 1. The idea in one sentence

Turn long-form video (podcasts, webinars, streams, talks) into short vertical
clips automatically, so the person who made the long video gets short-form
distribution without editing.

## 2. What we already know — dated and labelled

```text
OBSERVED 2026-09-09 | The category has multiple funded commercial products.
  Named repeatedly in tool round-ups and in open-source project descriptions:
  Opus Clip, Vizard, Klap, Vidyo.ai, SubMagic, CapCut.
  Sources: vizard.ai/blog/best-ai-video-clipping-tools-2026 ;
           capcut.com/resource/top-8-tools-for-turning-long-videos-to-shorts

OBSERVED 2026-09-09 | Credible open-source alternatives exist on GitHub, and
  they position explicitly against the paid tools:
  - Anil-matcha/AI-Youtube-Shorts-Generator — "Open-source alternative to Opus
    Clip, Vidyo.ai, Klap & SubMagic … free, no watermarks, no per-clip credits"
  - mutonby/openshorts — MIT self-host free, cloud from $12/mo, MCP server + API
  - NaufalRizqullah/opensource-clipping — face tracking, karaoke subs, B-roll
  GitHub topics `video-to-shorts`, `ai-clip-generator`, `shorts-maker` are active.

ASSUMPTION | The technical build (Whisper transcription + LLM highlight
  detection + vertical crop + subtitles) is largely a solved, commoditised
  pipeline. Confirm by reading one open-source repo end to end.
  → If true, the product cannot win on the core feature. The wedge must be
    somewhere else: a workflow, a segment, a distribution channel, or a price.

ASSUMPTION | Compute cost per video is the real unit-economics risk (R-003).
```

**What this early evidence implies (not a verdict):** the danger here is not
"can we build it" — it is "why would anyone pay us, when there are funded
products above us and free open-source below us". That question is what G3
exists to answer. If the research cannot answer it in one sentence, the honest
verdict is MODIFY or DO NOT BUILD, and finding that out in 3 weeks for ₹0 is a
good outcome.

## 3. Gates and kill criteria

| Gate | By | Pass condition | Owner |
|---|---|---|---|
| **G0 Scope** | day 1 | Owner answers A or B; repo/licence identified | vc-ceo |
| **G1 Problem** | day 4 | ≥ 10 dated, linked complaints from real creators; ≥ 3 tagged PAID-PAIN | vc-customer-research |
| **G2 Demand** | day 10 | Keyword + community evidence people actively look for this; AEO baseline recorded | vc-search-visibility |
| **G3 Wedge** | day 14 | **One sentence** naming a gap the paid tools do not cover and open source does not either | vc-competitor-intel |
| **G4 Pay** | day 18 | Evidence the target segment pays for this class of tool at our price band | vc-finance |
| **G5 Reach** | day 21 | One channel we can run at ₹0 that reaches that segment | vc-digital-marketing |
| **Verdict** | day 21 | Full report + BUILD/MODIFY/VALIDATE/DO NOT BUILD (A2) | vc-researcher |
| **G6 Value** | day 60 | Working MVP used by ≥ 5 people who are not friends | vc-pm |
| **G7 Money** | day 120 | ≥ 1 paying customer at target price | vc-finance |

**Kill rule:** miss any two gates → the CEO proposes KILL at the next board
review. **G3 is the hard one.** No wedge means no mission, regardless of how
good the technology is.

## 4. Questions the research must answer

1. Who exactly is under-served today — podcasters? course creators? agencies
   clipping for clients? B2B marketing teams? sales teams clipping webinars?
   local businesses? Each has a different willingness to pay and a different
   channel.
2. What do people actually complain about in the existing tools? (per-clip
   credits, watermarks, bad crops on multi-speaker video, wrong highlight
   picks, subtitle accuracy on accents, price, export limits, no brand kit)
3. What does the open-source option fail to give a *non-technical* buyer?
   Hosting, reliability, support, and a UI are products in themselves.
4. Is there a non-English or regional-language angle the incumbents handle
   badly? (the owner speaks Tamil, Telugu, Marathi — and accent/language
   accuracy is a recurring complaint theme worth testing)
5. Is there a *workflow* wedge rather than a *clipping* wedge — e.g. clip →
   approve → schedule → post → report, for a team that must review before
   posting?
6. What does one processed hour of video actually cost us, on the owner's own
   VPS versus a paid API? This decides whether any price works.
7. What is the platform-terms position for pulling source video (R-001)?

## 5. Constraints for this mission

- ₹0 budget. Any GPU or paid model spend is A3 and must be modelled first.
- Direct upload is the default source. Any platform-pull feature requires a
  GREEN from `vc-legal-risk` before it is designed (R-001).
- Rights to the source video are the user's. The product says so in the UI.
- If the mission uses an open-source project, the licence must be read and
  recorded in `state/decisions.md` before a single line is written. MIT is not
  the same as AGPL, and this decides whether a commercial product is possible.
- No code before the verdict is approved.

## 6. If the verdict is BUILD — the shape of v1

To be written by `vc-ba` after approval. Provisional guardrails:

```text
IN v1     the single wedge workflow, end to end, for one named segment
NOT v1    team accounts, brand kits, multi-language, scheduling, analytics,
          mobile app, API — unless one of them IS the wedge
```

## 7. North star (set at G0)

```text
<to be set — likely "clips published by a user", not "clips generated">
```
Generated clips are a vanity metric. A clip that never gets posted delivered no
value.

## 8. Research artefacts

```text
missions/research/001-problem-validation.md   G1
missions/research/001-competitors.md          G3
missions/research/001-search.md               G2
missions/research/001-pricing.md              G4
missions/research/001-channels.md             G5
missions/research/001-REPORT.md               the full 20-section report
```

## 9. Log

```text
2026-09-09 | mission opened by the owner
2026-09-09 | T-001 raised: confirm existing repo vs new build (BLOCKED-APPROVAL)
2026-09-09 | early landscape scan recorded above (OBSERVED)
```
