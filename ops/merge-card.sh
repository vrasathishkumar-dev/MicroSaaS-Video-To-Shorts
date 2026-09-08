#!/bin/bash
# Merge another kanban card's work into the current worktree, BY TASK ID.
#
# Why this exists: Hermes truncates branch names (~60 chars), so cards that
# referenced each other by branch name kept failing with "ambiguous revision"
# and burned whole cycles. Task IDs (t_xxxxxxxx) are short and stable, so
# resolve the branch from the ID instead of ever typing a branch name.
#
# Usage:  ops/merge-card.sh t_48202e39
#
# No git fetch is needed or possible - all worktrees share one .git object
# store, and the worker user has no GitHub credentials by design.

set -uo pipefail

TASK="${1:-}"
if [ -z "$TASK" ]; then
    echo "usage: ops/merge-card.sh <task_id>   e.g. ops/merge-card.sh t_48202e39" >&2
    exit 2
fi

# Resolve branch from the task id. --format avoids the '*'/'+' prefix markers
# that plain `git branch --list` prints for checked-out branches.
mapfile -t MATCHES < <(git branch --list "*${TASK}*" --format='%(refname:short)')

if [ "${#MATCHES[@]}" -eq 0 ]; then
    echo "ERROR: no local branch found for task ${TASK}." >&2
    echo "Check the id with: hermes kanban --board video-shorts list" >&2
    exit 1
fi

if [ "${#MATCHES[@]}" -gt 1 ]; then
    echo "NOTE: ${#MATCHES[@]} branches matched ${TASK}; using the first:" >&2
    printf '  %s\n' "${MATCHES[@]}" >&2
fi

BRANCH="${MATCHES[0]}"
echo "Merging ${BRANCH} (task ${TASK}) ..."

if git merge "$BRANCH" --no-edit; then
    echo "OK: merged ${BRANCH}"
    exit 0
fi

echo "ERROR: merge of ${BRANCH} failed (likely a conflict)." >&2
echo "Resolve the conflict, or kanban_block and report this output verbatim." >&2
exit 1
