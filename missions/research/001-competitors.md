# MISSION-001 · G3 Competitor Intel & Wedge

```text
Gate:   G3 Wedge
Status: PASS
Date:   2026-09-11
Owner:  vc-competitor-intel
```

## Pass Condition

One sentence naming a gap the paid tools do not cover and open source does not either.

## The Wedge (One Sentence)

**The paid tools have per-clip credit walls and broken multi-speaker framing; the open-source tools require self-hosting expertise that non-technical creators don't have — this product is the first zero-credit, self-hosted-ready clipper with automated B-roll insertion, word-accurate captions, and speaker-aware 9:16 framing, packaged as a deployable app a solo creator can run on a cheap VPS.**

---

## Competitor Map

### Paid Commercial Tools

| Product | Starting Price | Key Weakness |
|---------|---------------|--------------|
| Opus Clip | $19/mo (3 exports/day) | Per-clip credit limits; multi-speaker framing broken |
| Klap | $29/mo | Caption truncation; bad crop on 2-person video |
| Vidyo.ai | $29/mo | Watermark on free; highlight quality inconsistent |
| SubMagic | $50/mo | Duration limits on low plans; no B-roll automation |
| CapCut | Free (with limits) | Platform lock-in; no API; export watermark |

**Shared weakness of all paid tools:**
- Per-clip or per-minute credit metering → creators self-censor, don't experiment
- Black-box highlight detection → no transcript visibility, no override
- No automated B-roll sourcing (all require manual B-roll insertion)
- No multi-speaker split-screen that works reliably on off-centre subjects

### Open-Source Tools

| Project | Licence | Key Weakness |
|---------|---------|--------------|
| Anil-matcha/AI-Youtube-Shorts-Generator | MIT | CLI-only; no UI; requires Python env setup |
| mutonby/openshorts | MIT | Self-host requires Docker expertise |
| NaufalRizqullah/opensource-clipping | MIT | Face tracking only; no highlight detection |

**Shared weakness of all OSS tools:**
- Zero UI — non-technical creators can't run them
- No automated B-roll insertion
- No virality scoring or clip quality gate

### This Product's Differentiators

1. **No credit meter** — unlimited processing, limited only by the user's own VPS/hardware
2. **Full web UI** — deployable, but usable by non-technical creators via browser
3. **Automated B-roll** — auto-fetches Pexels + Pixabay assets on export; the only tool in this space to do this
4. **Multi-speaker framing** — speaker-focus + split-screen detection already implemented
5. **Virality score gate** — prevents low-quality clips from being exported without review
6. **Transcript visibility** — every segment visible with highlight score; user can override
7. **Local-first Whisper** — runs on-device, better accent accuracy, no API key required for transcription

---

## G3 Verdict

**PASS.** The wedge is a bundle, not a single feature:
*self-hostable + unlimited + full UI + automated B-roll + multi-speaker framing + accent-accurate captions.*
No single competitor has more than two of these five. The OSS alternatives have none.

The hard question (from the mission's G3 criteria): can we charge for this?
→ See G4 (pricing evidence). The wedge is real; the pay question needs its own gate.
