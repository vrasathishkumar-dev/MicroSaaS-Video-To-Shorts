#!/usr/bin/env python3
"""Daily digest for the video-to-shorts AI team.

Runs as a `hermes cron --no-agent` job: stdout is delivered verbatim to
Telegram, so this costs ZERO LLM calls (important - the OpenRouter free tier
is 50 requests/day and Hermes needs those for actual work).

Also serves as the reliability sweep: it flags cards marked done whose work
was never committed, which has silently happened before.
"""

import json
import subprocess
import time
from pathlib import Path

BOARD = "video-shorts"
REPO = Path("/srv/video-to-shorts")
HERMES = "/usr/local/bin/hermes"


def kanban(*args):
    """Run a kanban subcommand, return parsed JSON (or None)."""
    try:
        out = subprocess.run(
            [HERMES, "kanban", "--board", BOARD, *args, "--json"],
            capture_output=True, text=True, timeout=60,
        ).stdout
        return json.loads(out) if out.strip() else None
    except Exception:
        return None


def tasks():
    data = kanban("list")
    if isinstance(data, dict):
        return data.get("tasks", [])
    return data or []


def dirty_worktrees():
    """Worktrees with uncommitted changes -> work that would be silently lost."""
    found = []
    wt_root = REPO / ".worktrees"
    if not wt_root.is_dir():
        return found
    for wt in sorted(wt_root.iterdir()):
        if not (wt / ".git").exists():
            continue
        try:
            out = subprocess.run(
                ["git", "-C", str(wt), "status", "--porcelain"],
                capture_output=True, text=True, timeout=30,
            ).stdout.strip()
        except Exception:
            continue
        if out:
            found.append((wt.name, len(out.splitlines())))
    return found


def main():
    now = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    all_tasks = tasks()

    by_status = {}
    for t in all_tasks:
        by_status.setdefault(t.get("status", "?"), []).append(t)

    lines = [f"AI Team Digest - {now}", ""]

    # Board summary
    if all_tasks:
        summary = "  ".join(
            f"{s}:{len(v)}" for s, v in sorted(by_status.items())
        )
        lines.append(f"Board: {summary}")
    else:
        lines.append("Board: (no tasks - nothing queued)")
    lines.append("")

    # Finished in the last 24h
    cutoff = time.time() - 86400
    recent = [
        t for t in by_status.get("done", [])
        if (t.get("completed_at") or 0) >= cutoff
    ]
    if recent:
        lines.append(f"Completed (24h): {len(recent)}")
        for t in recent[:8]:
            lines.append(f"  + [{t.get('assignee','-')}] {t.get('title','')}")
        lines.append("")

    # Blocked - needs a human
    blocked = by_status.get("blocked", [])
    if blocked:
        lines.append(f"BLOCKED: {len(blocked)} - needs you")
        for t in blocked:
            lines.append(f"  ! {t.get('id')} [{t.get('assignee','-')}] {t.get('title','')}")
        lines.append("")

    # Awaiting founder approval (the Playbook's two gates)
    review = by_status.get("review", [])
    if review:
        lines.append(f"AWAITING YOUR APPROVAL: {len(review)}")
        for t in review:
            lines.append(f"  ? {t.get('id')} {t.get('title','')}")
        lines.append("")

    # Reliability sweep: done cards whose work was never committed
    dirty = dirty_worktrees()
    if dirty:
        lines.append("UNCOMMITTED WORK - may be lost:")
        for name, count in dirty:
            lines.append(f"  * {name}: {count} uncommitted file(s)")
        lines.append("")

    # Idle -> top the backlog up so the team does not sit doing nothing.
    active = len(by_status.get("ready", [])) + len(by_status.get("running", [])) \
        + len(by_status.get("todo", []))
    if active == 0:
        lines.append("Team was IDLE - no queued work.")
        queued = top_up()
        lines.append(f"  {queued}")

    print("\n".join(lines))


def top_up():
    """Queue one BA card when the board runs dry.

    Deliberately conservative: at most one card per day (idempotency key is
    date-based), and only when nothing at all is queued. The OpenRouter free
    tier is 50 requests/day, so generating work aggressively would starve the
    team of the quota it needs to actually do that work.

    To disable: `hermes cron pause ai-team-digest`, or delete this function's
    call above.
    """
    key = "ba-topup-" + time.strftime("%Y-%m-%d", time.gmtime())
    try:
        res = subprocess.run(
            [
                HERMES, "kanban", "--board", BOARD, "create",
                "[ba] Propose the next slice of work",
                "--project", BOARD,
                "--assignee", "coder",
                "--created-by", "auto-topup",
                "--idempotency-key", key,
            ],
            capture_output=True, text=True, timeout=60,
        )
        if res.returncode == 0:
            return "Queued a BA card to propose the next slice."
        return f"Could not queue BA card: {res.stderr.strip()[:100]}"
    except Exception as exc:
        return f"Could not queue BA card: {exc}"


if __name__ == "__main__":
    main()
