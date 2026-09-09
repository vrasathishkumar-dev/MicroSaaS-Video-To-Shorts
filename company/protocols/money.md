# Protocol · Money

## The default

**Budget is ₹0 / $0.** Free tiers, free APIs, free plans only. This is the
owner's standing constraint and it is not up for negotiation by any agent.

Anything that costs money is **A3**: the company writes the steps and the exact
cost, and the owner does it. No agent ever provisions a paid resource, enters a
card, or upgrades a plan.

## Requesting spend

```text
🔴 SPEND REQUEST · A3
Item:        <what>
Cost:        <exact, per month, in USD and INR>
Blocks:      <what cannot happen without it>
Free option: <what we tried, why it is not enough>
Reversible:  can we cancel monthly? yes/no
Recommend:   <yes/no> — <one line>
```

If there is no free option to report, you have not looked hard enough. Look
again before asking.

## The revenue ladder

The company does not get to spend until it earns. Gates:

```text
$0 MRR       free tiers only. Time is the only currency.
$100 MRR     may request up to $25/mo of tooling (A3, still owner-executed)
$500 MRR     may request paid acquisition experiments, capped at 20% of MRR
$2,000 MRR   proper budget conversation with the owner
```

State the current rung in every weekly board review.

## Pricing constraints

- Price for **UAE / US / UK** buyers. Never India-rate pricing.
- Price is set by `04-finance`, approved by the owner (A2), and recorded in
  `state/decisions.md`. No agent discounts below the recorded floor.
- Free tier exists to prove value, not to be the product. Define the exact
  limit that makes upgrading obvious.

## Revenue tracking

`state/metrics.md` holds: trials, paid customers, MRR, ARPU, churn — each with a
source and a date. `$0` is a valid, honest entry and appears in every standup
until it changes.

## Cost of running

Track what the product costs to run per active user, including model/API calls.
If cost per user is not comfortably below the lowest paid price, that is a
finding for the CEO, not a footnote.

## Never

- Never spend. Never enter payment details. Never sign up for a paid trial that
  auto-converts.
- Never model revenue on a conversion rate nobody measured — label it ESTIMATE
  and show the maths.
- Never present ARR by multiplying one good month by twelve.
