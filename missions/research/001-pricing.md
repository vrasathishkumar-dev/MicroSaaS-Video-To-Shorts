# MISSION-001 · G4 Pricing & Willingness to Pay

```text
Gate:   G4 Pay
Status: PASS (conditional — see note on personal-use scope)
Date:   2026-09-11
Owner:  vc-finance
```

## Pass Condition

Evidence the target segment pays for this class of tool at our price band.

---

## Current Project Context

The owner has stated (2026-09-11 conversation): **"it's my personal use website."**
This means:
- The product is not being priced for external customers in v1
- G4 is evaluated as: would the owner's target segment pay, *if* a commercial tier were added?
- Budget is ₹0 — no paid tier in MVP; this gate documents commercial viability for a future pivot

---

## Willingness to Pay Evidence

### What creators currently pay (market data)

| Tool | Price | What they pay for |
|------|-------|-------------------|
| Opus Clip Standard | $19–$79/mo | 50–250 clips/mo + AI highlights |
| Klap | $29/mo | Unlimited clips (within quota) |
| SubMagic | $29–$79/mo | Subtitle + clip generation |
| Vidyo.ai | $29/mo | Auto-clip + caption |

**Median observed spend:** $29–$49/mo for a dedicated short-form clipping tool.

### Price Sensitivity Signals

- 5 PAID-PAIN complaints in G1 named specific price frustration (per-credit, export limits)
- Creators *do* pay — they just object to credit walls and output quality, not the category price
- The ₹2,400/mo (~$29/mo) band is the established market-clearing price

### Compute Cost Estimate (unit economics for future paid tier)

Based on the owner's existing VPS stack:

| Resource | Estimate |
|----------|----------|
| Whisper (local) | ~₹0 per minute (runs on CPU) |
| Pexels/Pixabay API | Free tier: 200 req/hr per key |
| Storage per 1h video processed | ~3–8 GB clips + source |
| VPS cost per 1h video processed | ~₹5–15 at current hosting costs |

**Gross margin at ₹2,400/mo:** if a user processes ≤10 hours of video/month, compute cost is ~₹50–150 → ~90–95% gross margin. Compute is not the unit-economics risk.

**Real risk:** customer acquisition cost — not compute.

---

## G4 Verdict

**PASS (conditional).** Creators demonstrably pay ₹2,400–₹6,000/mo for this category. Compute margins are favorable. The only gate this doesn't satisfy is the owner's current personal-use scope — which is a scope decision, not a market failure. If/when a commercial tier is added, the pricing data supports $19–$29/mo for a personal license.
