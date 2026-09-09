# Playbook · Build Cycle (approved verdict → shipped)

Precondition: the verdict is BUILD **and approved**. Otherwise stop.

## 1. Requirements — `15-ba`

Problem statement · success criteria as numbers · user stories with GIVEN/WHEN/
THEN acceptance · MVP scope (vertical slice) · **NOT in v1 list** ·
non-functional requirements · open questions.

Gate: PM accepts, owner approves the scope (A2).

## 2. Design — `16-product-designer`

Flow (count the steps, remove one) · screen inventory · all five states per
screen · real copy · design tokens.

Gate: every screen has empty / loading / error / success designed.

## 3. Plan — `17-architect`

Spike the risky unknown first. Data model · API surface · integration
boundaries and failure paths · ordered, independently testable steps · ADRs.

With ECC: `/ecc:plan`.

Gate: every step has a "test first" and a rollback.

## 4. Build — `18-engineer` (one step at a time)

```text
read step → failing test → smallest code → refactor → full suite →
self-review diff → hand to QA → update board
```

With ECC: `tdd-workflow`.

Rules: one step per task · no unplanned refactors · no new dependency without a
justification · nothing outside the task's scope (log it as a new task instead).

## 5. Review — `19-qa`

Does it match the task · correctness · security (`/security-scan`) · data ·
failure modes · tests that can actually fail · then style (`/code-review`).

Verdict: `PASS / PASS-WITH-FIXES / FAIL`. Only QA can mark code DONE.

## 6. Ship — `20-devops`

Release checklist · staging first · rollback written before deploying · health
check · smoke test of the core flow · board updated.

First production deploy is A2. After that, A1.

## 7. Measure — `21-data-analyst`

North star + activation + the one number that could contradict the plan. Report
to CEO within 7 days of shipping.

## Cycle rules

- **One feature in flight at a time.** A company of agents can parallelise
  research; it cannot parallelise a codebase without creating conflicts nobody
  is awake to resolve.
- **Ship in slices.** Every slice must be usable by a real person, even if only
  for one narrow case.
- **The NOT-in-v1 list is enforced by PM.** Adding to scope requires a CEO
  decision logged in `state/decisions.md`.
- **If a step takes 3× its estimate**, stop and escalate. Unsupervised, that is
  how a week becomes a month.
