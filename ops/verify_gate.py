#!/usr/bin/env python3
"""Verification gate - catch cards that CLAIM done but whose code fails.

The problem this solves: agents have repeatedly marked cards done with work
that did not exist, or made a check pass by deleting features. The board went
green and only a human reading logs caught it.

This runs as a `hermes cron --no-agent` job (ZERO LLM calls). For each card
marked done that it has not checked yet, it:
  1. resolves the card's branch from its task id
  2. skips it if the branch changed no code (doc-only cards)
  3. checks out that branch in a temp worktree and runs the real test suite
  4. if tests fail, BLOCKS the card and attaches the actual failure output
  5. records the result so each card is only ever tested once

Silent when everything checks out (empty stdout = no notification).
"""

import json
import subprocess
import time
from pathlib import Path

BOARD = "microsaas"
REPO = Path("/srv/microsaas-video-to-shorts")
VENV_PYTEST = "/srv/microsaas-video-to-shorts/backend/.venv/bin/pytest"
HERMES = "/usr/local/bin/hermes"
STATE = Path("/root/.hermes/verify-gate-state.json")

# Bound the runtime: 281 tests take ~3 min, so don't test everything at once.
MAX_PER_RUN = 2
TEST_TIMEOUT = 600
# Only these paths mean "code changed" and therefore need a test run.
CODE_PREFIXES = ("backend/", "frontend/")


def run(cmd, cwd=None, timeout=120):
    return subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
    )


def load_state():
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}


def save_state(state):
    try:
        STATE.write_text(json.dumps(state, indent=2))
    except Exception:
        pass


def done_cards():
    try:
        out = run([HERMES, "kanban", "--board", BOARD, "list",
                   "--status", "done", "--json"]).stdout
        data = json.loads(out) if out.strip() else []
        items = data.get("tasks", []) if isinstance(data, dict) else data
        return [(t.get("id"), t.get("title", "")) for t in items if t.get("id")]
    except Exception:
        return []


def branch_for(task_id):
    out = run(["git", "branch", "--list", f"*{task_id}*",
               "--format=%(refname:short)"], cwd=REPO).stdout.strip()
    return out.splitlines()[0] if out else None


def changed_code(branch):
    """True if this branch touches real code vs main (not a doc-only card)."""
    out = run(["git", "diff", "--name-only", f"main...{branch}"], cwd=REPO).stdout
    return any(p.startswith(CODE_PREFIXES) for p in out.splitlines())


def verify(task_id, branch):
    """Run the suite against branch in a throwaway worktree. -> (ok, output)"""
    wt = Path(f"/tmp/verify-{task_id}")
    run(["git", "worktree", "remove", str(wt), "--force"], cwd=REPO)
    add = run(["git", "worktree", "add", str(wt), branch, "--detach"], cwd=REPO)
    if add.returncode != 0:
        return None, f"could not create worktree: {add.stderr.strip()[:200]}"
    try:
        res = run([VENV_PYTEST, "-q"], cwd=str(wt / "backend"), timeout=TEST_TIMEOUT)
        tail = "\n".join((res.stdout + res.stderr).strip().splitlines()[-12:])
        return res.returncode == 0, tail
    except subprocess.TimeoutExpired:
        return False, f"test suite exceeded {TEST_TIMEOUT}s"
    finally:
        run(["git", "worktree", "remove", str(wt), "--force"], cwd=REPO)


def main():
    if not Path(VENV_PYTEST).exists():
        return  # env not set up; stay silent rather than spam
    state = load_state()
    failures, checked = [], 0

    for task_id, title in done_cards():
        if task_id in state or checked >= MAX_PER_RUN:
            continue
        branch = branch_for(task_id)
        if not branch:
            state[task_id] = "no-branch"
            continue
        if not changed_code(branch):
            state[task_id] = "skipped-no-code"
            continue

        checked += 1
        ok, output = verify(task_id, branch)
        if ok is None:
            continue  # transient worktree problem; retry next run
        if ok:
            state[task_id] = "pass"
            continue

        state[task_id] = "FAIL"
        failures.append((task_id, title, output))
        # A card that claimed done but fails its tests goes back to blocked,
        # with the real output attached so nobody has to guess.
        run([HERMES, "kanban", "--board", BOARD, "comment", task_id,
             "VERIFICATION GATE FAILED - this card was marked done but the "
             "test suite fails on its branch. Real output:\n\n" + output,
             "--author", "verify-gate"])
        run([HERMES, "kanban", "--board", BOARD, "block", task_id])

    save_state(state)

    if failures:
        print(f"VERIFICATION GATE: {len(failures)} card(s) claimed done but FAIL their tests")
        print("")
        for task_id, title, output in failures:
            print(f"{task_id}  {title}")
            print(output)
            print("")
        print("These cards have been blocked and commented with the real output.")


if __name__ == "__main__":
    main()
