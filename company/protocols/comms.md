# Protocol · Agent Communication

Agents have no shared memory. The envelope **is** the shared memory.
No agent may act on a vague hand-off. If a message arrives without an envelope,
the receiver replies `MALFORMED` and asks for one.

## 1. REQUEST — asking another agent to do work

```text
────────────────────────────────────────────
TO:        vc-competitor-intel
FROM:      vc-researcher
TYPE:      REQUEST
MISSION:   MISSION-001
TASK:      T-004
DEADLINE:  this cycle
AUTONOMY:  A0
────────────────────────────────────────────
CONTEXT:
  Idea: turn long videos into short vertical clips automatically.
  Hypothesised audience: solo creators and small agencies, US/UK/UAE.
  Already known: <2 lines max of established facts>

ASK:
  Direct, indirect and emerging competitors, with the gap analysis and one
  named wedge.

OUTPUT CONTRACT:
  agents/07 dossier format per competitor + gap table + wedge statement.
  Every price and quote OBSERVED with URL and date.

CONSTRAINTS:
  ₹0 budget. No scraping that breaches ToS. Overseas market focus.

CONFIDENCE NEEDED:
  MEDIUM or better on the top 5 competitors.
────────────────────────────────────────────
```

**Rules for the sender**

- One ASK per request. Two asks = two requests.
- Give context, not your conclusions — you will bias the answer.
- Always state the output contract. "Research competitors" is not a brief.
- Always state the budget and legal constraints.

## 2. REPORT — returning work

```text
TO / FROM / TYPE: REPORT / MISSION / TASK
────────────────────────────────────────────
HEADLINE:      <the answer in one sentence>
CONFIDENCE:    HIGH | MEDIUM | LOW
BODY:          <the output contract, exactly as asked>
EVIDENCE:      <sources, with dates>
UNAVAILABLE:   <what you could not find, and why>
CONTRADICTS:   <anything here that conflicts with an earlier finding>
NEXT:          <what you recommend happens now>
────────────────────────────────────────────
```

`UNAVAILABLE` and `CONTRADICTS` are mandatory fields. Empty is fine; missing is not.

## 3. DECISION — recording a call

Goes to `state/decisions.md`, append-only.

```text
D-012 | 2026-09-14 | decided by: vc-pm | mission: MISSION-001
Decision:  Ship without team accounts in v1
Options:   A) team accounts now  B) single user only  C) invite-only sharing
Because:   wedge is solo creators; team accounts add auth complexity (ADR-005)
Cost:      loses the small-agency segment until v2
Reversible: yes
Revisit:   after 20 users
```

## 4. ESCALATION — when you are stuck

```text
TYPE: ESCALATION → vc-ceo
BLOCKED ON:   <the exact thing>
TRIED:        <what you already attempted — at least two things>
NEED:         <decision / information / access / approval>
OPTIONS:      A) ...  B) ...  C) ...
RECOMMEND:    <one>
COST OF WAITING: <what slips>
```

Never escalate without having tried twice and without a recommendation. An
escalation with no recommendation is just a complaint.

## 5. APPROVAL-REQUEST — going to the owner

Format lives in `telegram.md`. Only the CEO sends these to the owner; other
agents send them **to the CEO**, who batches them.

## Handoff chain of custody

Every output names its inputs. The BA's requirements cite the research
findings; the architect's plan cites the requirements; the engineer's PR cites
the task. If a claim cannot be traced back to evidence, it gets dropped, not
carried forward.

## Disagreement

If two agents disagree:
1. State both positions with their evidence in one message.
2. If it is a **fact** dispute → whoever can retrieve the source wins. Go get it.
3. If it is a **judgement** dispute → PM decides for delivery matters,
   CEO for strategy matters, `05-legal-risk` has veto on risk matters.
4. Log it as a DECISION with both positions. Future sessions need to know that
   the alternative was considered.

Never resolve a disagreement by averaging the two answers.
