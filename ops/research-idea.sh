#!/bin/bash
# Kick off a full validation pass on a new project idea.
#
# Standing rule: NOTHING gets built until the founder approves the verdict.
# This creates a 3-phase research chain, each phase depending on the last, and
# the final phase sends the full report to Telegram and blocks for approval.
#
# Usage:
#   ops/research-idea.sh "AI receipt scanner for freelancers"
#   ops/research-idea.sh "Idea name" /path/to/project-brief.md
#
# The optional second argument is a brief/spec file whose contents are copied
# into the research folder so every phase can read it.

set -uo pipefail

BOARD="video-shorts"
HERMES="/usr/local/bin/hermes"
ROOT="/srv/artifacts/research"

IDEA="${1:-}"
BRIEF="${2:-}"

if [ -z "$IDEA" ]; then
    echo 'usage: ops/research-idea.sh "<idea>" [brief.md]' >&2
    exit 2
fi

# slug: lowercase, non-alphanumerics to dashes, trimmed
SLUG=$(printf '%s' "$IDEA" | tr '[:upper:]' '[:lower:]' \
     | sed 's/[^a-z0-9]\+/-/g; s/^-//; s/-$//' | cut -c1-40)
DIR="${ROOT}/${SLUG}"

mkdir -p "$DIR"
printf '# Idea: %s\n\nSubmitted: %s\n' "$IDEA" "$(date -u '+%Y-%m-%d %H:%M UTC')" > "$DIR/idea.md"

if [ -n "$BRIEF" ] && [ -f "$BRIEF" ]; then
    cp "$BRIEF" "$DIR/brief.md"
    echo "Copied brief -> $DIR/brief.md"
fi

# Make sure the worker can read/write the new folder.
setfacl -R -m u:worker:rwx "$DIR" 2>/dev/null
setfacl -R -d -m u:worker:rwx "$DIR" 2>/dev/null

new_card() {   # title, extra-args...  -> prints task id
    "$HERMES" kanban --board "$BOARD" create "$1" \
        --project "$BOARD" --assignee marketing --created-by research-kickoff \
        "${@:2}" 2>/dev/null | grep -oE 't_[0-9a-f]{8}' | head -1
}

note() { "$HERMES" kanban --board "$BOARD" comment "$1" "$2" --author research-kickoff >/dev/null 2>&1; }

P1=$(new_card "[researcher] ${IDEA}: market + real-problem validation")
note "$P1" "Phase 1 of 3. Read ${DIR}/idea.md (and brief.md if present). Delegate to claude -p --agent researcher per AGENTS.md. Answer: does a real problem exist (evidence of people suffering it today), and is there real market demand? Search the web - cite competitors, pricing, complaints, community threads. Report disconfirming evidence too. Write ${DIR}/01-market.md."

P2=$(new_card "[researcher] ${IDEA}: money + audience" --parent "$P1")
note "$P2" "Phase 2 of 3. Read ${DIR}/01-market.md first. Delegate to claude -p --agent researcher. Answer: what is the concrete monetization mechanism and realistic time-to-revenue, and which NAMED acquisition channels could reach an audience (specific queries, subreddits, creator niches - not 'SEO'). Write ${DIR}/02-money-audience.md."

P3=$(new_card "[researcher] ${IDEA}: verdict + report to founder" --parent "$P2")
note "$P3" "Phase 3 of 3. Read ${DIR}/01-market.md and ${DIR}/02-money-audience.md. Delegate to claude -p --agent researcher. Write ${DIR}/research-report.md covering all four questions (buildable solo in a few hrs/week? can we make money? can we get an audience? does it fix a real problem?) and END with the house format: Market / Blocker / Path to Money / Verdict BUILD-FIX-PARK, plus scores for Market proof, Time-to-revenue, Effort, Risk, Fit. Then send it to the founder: /usr/local/bin/hermes send -t telegram -s 'RESEARCH VERDICT: ${IDEA}' -f ${DIR}/research-report.md . Then call kanban_block with reason 'awaiting founder approval' - do NOT create any ba/designer/developer card. Building starts only after the founder approves."

echo "Research chain created for: ${IDEA}"
echo "  folder : ${DIR}"
echo "  phase 1: ${P1}  market + real problem"
echo "  phase 2: ${P2}  money + audience"
echo "  phase 3: ${P3}  verdict -> Telegram -> BLOCKS for your approval"
echo
echo "Nothing will be built until you approve phase 3."
