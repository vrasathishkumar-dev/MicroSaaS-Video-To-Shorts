#!/usr/bin/env python3
"""Rescue uncommitted work left behind in kanban task worktrees.

Workers are told (in AGENTS.md) to commit before completing a card, but that
is an instruction to a weak model, not a guarantee - it has silently failed
more than once, leaving real output uncommitted where a worktree GC would
destroy it.

This runs as a `hermes cron --no-agent` job (zero LLM calls), commits any
stray work to the task's own branch, and pushes it. It never touches main,
so nothing merges without review - the worst case is an extra safety commit
on a feature branch.

Silent when there is nothing to do (empty stdout = no notification).
"""

import json
import subprocess
import time
from pathlib import Path

BOARD = "video-shorts"
REPO = Path("/srv/video-to-shorts")
HERMES = "/usr/local/bin/hermes"
# Give an in-flight worker time to commit on its own before we step in.
MIN_IDLE_SECONDS = 900


def run(cmd, cwd=None, timeout=120):
    return subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
    )


def task_status_by_id():
    """Map task id -> status, so we skip worktrees still being worked on."""
    try:
        out = run([HERMES, "kanban", "--board", BOARD, "list", "--json"]).stdout
        data = json.loads(out) if out.strip() else []
        items = data.get("tasks", []) if isinstance(data, dict) else data
        return {t.get("id"): t.get("status") for t in items}
    except Exception:
        return {}


def main():
    wt_root = REPO / ".worktrees"
    if not wt_root.is_dir():
        return

    statuses = task_status_by_id()
    rescued = []
    now = time.time()

    for wt in sorted(wt_root.iterdir()):
        if not (wt / ".git").exists():
            continue

        task_id = wt.name
        status = statuses.get(task_id)

        # Leave actively-running cards alone - the worker may still be mid-edit.
        if status == "running":
            continue

        porcelain = run(["git", "-C", str(wt), "status", "--porcelain"]).stdout.strip()
        if not porcelain:
            continue

        # Don't race a worker that just wrote a file seconds ago.
        try:
            newest = max(
                p.stat().st_mtime
                for p in wt.rglob("*")
                if p.is_file() and ".git" not in p.parts
            )
        except ValueError:
            continue
        if now - newest < MIN_IDLE_SECONDS:
            continue

        n_files = len(porcelain.splitlines())
        branch = run(["git", "-C", str(wt), "branch", "--show-current"]).stdout.strip()
        if not branch:
            continue  # detached HEAD - don't guess where this belongs

        add = run(["git", "-C", str(wt), "add", "-A"])
        if add.returncode != 0:
            rescued.append(f"  ! {task_id}: git add failed - {add.stderr.strip()[:120]}")
            continue

        msg = f"Rescue uncommitted work from {task_id} (auto-sweep)"
        commit = run(["git", "-C", str(wt), "commit", "-m", msg])
        if commit.returncode != 0:
            rescued.append(f"  ! {task_id}: commit failed - {commit.stderr.strip()[:120]}")
            continue

        push = run(["git", "-C", str(wt), "push", "-u", "origin", branch], timeout=180)
        pushed = "pushed" if push.returncode == 0 else "commit only (push failed)"
        rescued.append(
            f"  + {task_id} [{status or 'unknown'}]: {n_files} file(s) rescued on {branch} ({pushed})"
        )

    # Second pass: branches committed but never pushed.
    # The worker user has no GitHub credentials by design (only root does), so
    # workers can commit but their push fails. Root pushes for them here.
    pushed = []
    for wt in sorted(wt_root.iterdir()):
        if not (wt / ".git").exists():
            continue
        if statuses.get(wt.name) == "running":
            continue
        branch = run(["git", "-C", str(wt), "branch", "--show-current"]).stdout.strip()
        if not branch:
            continue
        # Any local commits not on the remote?
        ahead = run(
            ["git", "-C", str(wt), "log", "--oneline", f"origin/{branch}..{branch}"]
        )
        unpushed = ahead.stdout.strip()
        if ahead.returncode != 0:
            # No upstream yet - treat as needing a first push.
            has_commits = run(["git", "-C", str(wt), "log", "--oneline", "-1"]).stdout.strip()
            if not has_commits:
                continue
        elif not unpushed:
            continue
        p = run(["git", "-C", str(wt), "push", "-u", "origin", branch], timeout=180)
        if p.returncode == 0:
            pushed.append(f"  > {wt.name}: pushed {branch}")

    if rescued or pushed:
        if rescued:
            print("Commit sweep rescued uncommitted agent work:")
            print("\n".join(rescued))
            print("")
        if pushed:
            print("Pushed branches the worker could not push (no GitHub creds by design):")
            print("\n".join(pushed))
            print("")
        print("Review the branches before merging to main.")


if __name__ == "__main__":
    main()
