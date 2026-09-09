#!/bin/bash
# VC-1 ritual runner. Usage: vc-ritual.sh standup | board-review
# Runs vc-ceo via Claude Code (Pro subscription - no OpenRouter quota), then
# delivers to Telegram and appends to the company board.
# Kanban state is read HERE and injected, because the agent's own shell calls
# are permission-gated and cannot be relied on.
set -uo pipefail

MODE="${1:-standup}"
REPO=/srv/microsaas-video-to-shorts
CO=$REPO/company
OUT=$(mktemp /tmp/vc-ritual-XXXX.txt)
KB=$(mktemp /tmp/vc-kanban-XXXX.txt)

/usr/local/bin/hermes kanban --board microsaas list > "$KB" 2>&1 || echo "(kanban read failed)" > "$KB"
KANBAN=$(cat "$KB")

case "$MODE" in
  standup)
    SUBJ="VC-1 standup"
    ASK="Run the VC-1 daily standup per company/agents/01-ceo.md. Read company/state/board.md, company/state/company.md and the active mission in company/missions/. LIVE KANBAN STATE (authoritative, already read for you - do not try to run hermes yourself): ---START--- $KANBAN ---END--- Output UNDER 12 LINES in exactly this shape and nothing else: line1 '🏢 VC-1 · <date> · <mission>', then 'Done:', 'Today:', 'Blocked:', 'Waiting on you:', 'Gate:', 'Money: 0 spent'. Report only what actually completed per the kanban state above, never what was attempted. If nothing completed, say so plainly."
    ;;
  board-review)
    SUBJ="VC-1 Monday board review"
    ASK="Run the VC-1 weekly board review per company/playbooks/weekly-board-review.md. Read company/state/*.md and the active mission. LIVE KANBAN STATE (authoritative, already read for you): ---START--- $KANBAN ---END--- Follow the agenda order: numbers first, gates, what actually shipped (not worked on), what is stuck, risks, money, then exactly ONE decision proposal. Under 25 lines. Label every claim FACT/OBSERVATION/ESTIMATE/ASSUMPTION."
    ;;
  *) echo "usage: vc-ritual.sh standup|board-review" >&2; exit 2;;
esac

su - worker -c "set -a; source ~/.claude_token.env; set +a; cd $REPO; claude -p \"$ASK\" --agent vc-ceo" > "$OUT" 2>&1

if [ ! -s "$OUT" ]; then
  echo "VC-1 $MODE FAILED: vc-ceo produced no output" > "$OUT"
fi

/usr/local/bin/hermes send -t telegram -s "$SUBJ" -f "$OUT" >/dev/null 2>&1 \
  || echo "(telegram delivery failed - output kept at $OUT)"

{
  echo ""
  echo "### $SUBJ — $(date -u '+%Y-%m-%d %H:%M UTC')"
  echo '```text'
  cat "$OUT"
  echo '```'
} >> "$CO/state/board.md" 2>/dev/null

rm -f "$KB"
cat "$OUT"