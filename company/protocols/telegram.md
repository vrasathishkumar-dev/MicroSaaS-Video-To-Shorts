# Protocol · Telegram (the owner's boardroom)

Telegram is where the company talks to Sathish. Everything else is internal.

**Design rule:** he should be able to run the company from his phone in under 5
minutes a day. Every message is therefore short, decidable, and has a default.

## Message budget

```text
Daily:   1 standup (07:45 IST) + at most 2 approvals
Weekly:  1 board review (Mon) + 1 growth review (Fri)
Never:   progress narration, "just letting you know", agent chatter
```

If the company needs more than 3 messages in a day, the escalation rules are
wrong. The CEO agent must fix the rules — not send more messages.

## 1. Daily standup

```text
🏢 VC-1 · Tue 09 Sep · MISSION-001
Done: competitor pass complete — 9 direct, 4 indirect
Today: pricing + keyword sets
Blocked: nothing
Waiting on you: 1 approval (below)
Gate G1 (problem evidence) due 12 Sep — on track
Money: ₹0 spent · $0 MRR
```

## 2. Approval request (A2)

```text
🟠 APPROVAL · MISSION-001 · A2
What: publish landing page at <url>
Why: needed to run the demand test (gate G2)
Cost: ₹0
If yes: page is public under your brand
If no: G2 slips ~1 week
Recommend: YES
Reply: YES / NO / ASK <question>
```

Rules: one decision per message · always a recommendation · always the cost of
saying no · never bundle two unrelated approvals.

## 3. Owner-only action (A3)

The company cannot do it. Give exact steps, not a request.

```text
🔴 YOU ONLY · 3 min
Need: Groq API key added to n8n credentials
Steps:
 1. console.groq.com → API Keys → Create
 2. n8n → Credentials → New → Groq → paste
 3. Reply DONE
Blocks: content drafting automation
```

## 4. Verdict summary (after a research run)

```text
📊 RESEARCH COMPLETE · <product>
Market: <one line>
Demand HIGH · Competition HIGH · Pay MEDIUM
SEO MEDIUM · Digital HIGH · Offline NOT RELEVANT
Top competitors: 1. … 2. … 3. …
Main gap: <one line>
Positioning: <one line>
VERDICT: MODIFY
Why: <one line>
Report: <path>
Reply: YES to proceed / NO to stop / ASK <question>
```

## 5. Incident

```text
🚨 <severity> · <what is broken> · <since when>
Impact: <who cannot do what>
Doing: <the fix in progress>
Need from you: <nothing / this one thing>
```

## Replies the company understands

```text
YES            approve, proceed
NO             rejected, park it and log why
ASK <q>        answer, then re-send the approval
HOLD           park until he says otherwise
STOP           halt the whole mission immediately
```

An unanswered approval is **not** a yes. After 24h the task becomes
`BLOCKED-APPROVAL`; it is re-raised once in the next standup, then dropped.

## n8n wiring (spec for the workflow to build)

```text
[Schedule 07:45 IST] → [Read state files] → [Compose standup] → [Telegram send]

[Webhook /vc/approval]  ← posted by the company session
        → [Telegram send with inline buttons YES / NO / ASK]
        → [Telegram trigger: button pressed]
        → [Append to state/decisions.md via VPS file node]
        → [Optional: wake the Cowork session]

[Telegram trigger: free text] → [Route: is it a company command?]
        → yes: append to state/inbox.md
        → no:  hand to Hermes (personal assistant, separate workflow)
```

Keep VC-1 and Hermes as **separate workflows** sharing one Telegram bot, or use
two bots. Do not mix personal and company state in one data table.

## Security

Never send through Telegram: API keys, passwords, tokens, `.env` contents,
customer personal data, full error logs, database dumps. Send a path or a
reference instead. Telegram is not a secure channel and the chat history is
long-lived.
