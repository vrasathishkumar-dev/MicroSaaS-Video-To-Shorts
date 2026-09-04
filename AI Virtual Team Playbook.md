# AI Virtual Team Playbook

Running a one\-person company on a single project, with Claude filling every functional role

**Status: implemented.** The roster lives in `.claude/agents/*.md`, dispatched
via the Agent tool by the main Claude Code session (which acts as
orchestrator/founder liaison — see `CLAUDE.md` → Agent Coordination), with
`team/backlog.md` as the shared handoff file. This document is the reference
for *why* it's built that way and how to extend it — read `CLAUDE.md` for the
live, authoritative version of the pipeline and gates.

## Concept

You are the founder and the only human. Instead of hiring a Business Analyst, Designer, Developer, Tester, SEO/GEO/AEO specialist, and Marketer, each role is a **Claude persona** with a defined scope, defined inputs/outputs, and a defined handoff to the next role. You supervise and approve; Claude does the work of the team.

This only works well if the roles are kept separate — one role's context should not leak into another's. The mechanism for that separation is the next section.

## Three ways to run this in Claude

Pick one path — don't mix all three for the same project, it fragments your context.

| Approach | What it is | Best when |
| --- | --- | --- |
| Claude Projects | One Claude Project (which you already have) with a **custom project instruction per role**, switched by starting a chat with "Acting as \[Role\]..." | You want everything in one place, low setup, mostly manual switching |
| Claude Code subagents | Each role becomes a **subagent type** invoked via the Agent tool, with its own system prompt and tool access | You want automated hand\-offs — one role's output triggers the next automatically |
| Custom skills | Each role becomes a **skill** (a checklist \+ template) invoked by name inside any conversation | You want a repeatable checklist per role but don't need full automation |

Chosen for this project: **Claude Code subagents** for the roles, with a
plain file — `team/backlog.md` — as the shared knowledge base instead of a
Claude Project. This is a Claude Code (CLI) project, not a claude.ai
workspace, so a Claude Project isn't in the loop; a git-tracked markdown file
does the same job (every role reads/appends the same source of truth) and
stays versioned alongside the code it describes.

## The team

| Role | Owns | Key inputs | Key outputs |
| --- | --- | --- | --- |
| Business Analyst (BA) | Requirements, scope, priorities | Founder's idea, market notes | User stories, acceptance criteria, prioritized backlog |
| Designer | UX/UI | User stories, brand guidelines | Wireframes, UI specs, design system notes |
| Developer — split into `database-agent` \+ `backend-agent` \+ `frontend-agent` | Implementation | Design specs, backlog | Working code, technical docs |
| Tester (QA) | Quality | Code, acceptance criteria | Test plans, bug reports, sign\-off |
| DevOps | Infrastructure, CI/CD, releases | Code from Developer, test sign\-off | Build pipelines, deployments, monitoring, rollback plans |
| SEO, GEO & AEO Specialist | Organic search \+ AI\-generated\-answer visibility \+ direct question\-answer surfaces | Site content, target keywords, target questions | On\-page SEO fixes, schema markup, AI\-citation content, FAQ/Q\&A schema |
| Marketer | Positioning, growth | Product, target audience | Copy, campaigns, launch plan |

## Workflow / pipeline

```
Idea → BA (backlog + stories) → Designer (specs) → Developer (build)
       → Tester (QA sign-off) → DevOps (deploy) → SEO/GEO/AEO + Marketer (launch & visibility)
                ↑________________________ feedback loop ________________________|
```

Each arrow is a **handoff document** — the BA's backlog is the Designer's input, the Designer's spec is the Developer's input, and so on. In practice, each handoff is a subsection appended to the same story entry in `team/backlog.md`, so the next role reads it before starting instead of re-asking.

## How you actually trigger it

You don't invoke roles by name. Talk to the main session normally:

- A **new idea, requirement, or piece of feedback** ("it should also let users...", "the export is too slow") is treated as the start of the pipeline — the session dispatches `ba` first.
- **Everything else** — questions, "fix this", "run the tests," follow-ups on work already in flight — is handled directly, same as any ordinary Claude Code request. Not every message is a new story.

If that line is ever misjudged (something you meant as a throwaway comment turns into a backlog entry, or a real requirement gets treated as a one-off), say so — it's a judgment call the orchestrator makes each time, not a hard trigger word.

## Setting each role up as a Claude Code subagent

For each role, define:

1. **Name** — e.g. `ba`, `designer`, `developer` (or `backend-agent`/`frontend-agent`/`database-agent`), `tester`, `devops`, `seo-geo` (covers SEO + GEO + AEO), `marketer`
2. **System prompt** — scope of responsibility, what "done" looks like, what NOT to do (e.g. the Designer should not write code, the Tester should not fix bugs, only report them)
3. **Tool access** — e.g. Developer/DevOps get file/shell tools; Marketer/SEO-GEO-AEO get web search and document tools; BA gets none beyond reading/writing docs
4. **Handoff contract** — the exact file or format it must produce so the next role can consume it without re\-asking questions

### Suggested role prompts (starting point — refine per project)

- **BA** — "Given the founder's idea and any existing notes, produce a prioritized backlog of user stories in `As a [user], I want [goal], so that [benefit]` format, each with acceptance criteria. Ask only if the goal itself is unclear; don't design or estimate effort."
- **Designer** — "Given the backlog, produce wireframe descriptions and a UI spec (screens, states, components, responsive behavior for web \+ mobile) for each story. Do not write code."
- **Developer** — "Given the UI spec and backlog, implement the feature, following the existing codebase's conventions. Write tests are the Tester's job, not yours — hand off working code \+ a short technical note."
- **Tester** — "Given the code and acceptance criteria, write a test plan, execute it, and report pass/fail with reproduction steps for anything failing. Do not fix bugs — flag them back to Developer."
- **DevOps** — "Given code that has passed Tester sign\-off, set up or update the CI/CD pipeline, provision/update infrastructure, and deploy to the target environment (web \+ mobile release channels). Report what was deployed, where, and the rollback steps if something goes wrong. Do not write feature code or change test criteria."
- **SEO, GEO & AEO Specialist** — "Given the shipped feature/page, optimize: (1) SEO — on\-page basics (titles, meta, headings, schema markup); (2) GEO — how it would be described/paraphrased/cited by an AI answer engine that synthesizes multiple sources (AI Overviews, Perplexity, ChatGPT search); (3) AEO — whether it states a direct one\-sentence/short\-list answer to the specific question a user would ask, with matching FAQ/Q\&A schema. Report before/after for each."
- **Marketer** — "Given the shipped feature and target audience, produce launch copy, a short campaign plan, and channel recommendations."

## When a role gets stuck (escalation)

Left implicit before, worth stating: if `tester` kicks a story back to a
Developer role and that same acceptance criterion fails **again** after the
fix, stop the loop and bring it to you rather than retrying indefinitely —
a repeated failure usually means the acceptance criterion itself is wrong or
underspecified, which is a BA problem, not a Developer one. Same logic for
any two roles that produce conflicting output (e.g. Designer's spec assumes
a component Developer says doesn't exist): surface the conflict and the
proposed resolution, don't silently pick one side.

## Automating the pipeline

**Current state: manual dispatch, automatic content.** Each role's output
format and handoff are fully specified, but the main session dispatches each
stage itself, in the same conversation — there's no standing trigger that
fires `tester` the moment `backend-agent` finishes, or `devops` the moment
you approve sign-off. That's a deliberate simplification, not a gap to
apologize for: a founder-in-the-loop pipeline doesn't need to survive
between sessions.

If/when that stops being enough (multiple stories genuinely running
unattended), the pieces to add are:

- **Scheduled tasks**\: recurring SEO/GEO/AEO audits (e.g. weekly), recurring marketing content drafts, recurring test runs after each Developer handoff, recurring deployment health checks after each DevOps release.
- **Trigger chaining**\: a scheduled task or cron job that checks `team/backlog.md` for a story that just moved to `in-qa`/`qa-signoff-needed`/etc. and dispatches the next role automatically, instead of you (or this session) doing it by hand.

## Governance (you, the founder)

Even as "one person," keep a lightweight approval gate at two points: after the BA's backlog (you approve scope) and after the Tester's sign\-off (you approve release). Everything else can run autonomously.

## Next steps

1. Run one real idea through the full pipeline end to end — the fastest way to find a role prompt that's wrong is to watch it produce a bad handoff, not to review it in the abstract.
2. VideoToShorts is web-only for the MVP (no native mobile app in `CLAUDE.md`'s stack) — no Mobile Developer role needed unless that changes.
3. Once a few stories have shipped, revisit whether the two approval gates are the right amount of friction — tighten to a gate per handoff if releases are moving faster than you can review, loosen toward full autonomy if the gates are rubber-stamped every time.
