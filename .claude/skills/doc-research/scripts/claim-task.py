#!/usr/bin/env python3
"""Atomic task claim for doc-research workers.

Usage:
    python3 claim-task.py [--release T-XXX]

Claim mode (default):
    Acquires a global file lock, reads the task queue, picks the highest
    priority claimable task, writes a per-task lock file, updates the YAML,
    and prints the claimed task ID to stdout. Exit code 0 = claimed,
    exit code 1 = nothing to claim.

Release mode (--release T-XXX):
    Removes the per-task lock file for the given task ID.

All queue mutations are serialized through a single flock on
_meta/claims/.queue-lock, so concurrent workers cannot race.
"""

import fcntl
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# -- Paths -----------------------------------------------------------------

# Project root: walk up from this script to find _meta/
def _find_root() -> Path:
    p = Path(__file__).resolve().parent
    for _ in range(10):
        if (p / "_meta" / "task-queue.yaml").exists():
            return p
        p = p.parent
    # Fallback: cwd
    return Path.cwd()

SCRIPT_DIR = _find_root()
META = SCRIPT_DIR / "_meta"
QUEUE_FILE = META / "task-queue.yaml"
ARCHIVE_FILE = META / "task-archive.yaml"
CLAIMS_DIR = META / "claims"
GLOBAL_LOCK = CLAIMS_DIR / ".queue-lock"

TZ = timezone(timedelta(hours=8))

# -- Minimal YAML helpers (no pyyaml dependency) ---------------------------
# The queue YAML is simple enough to parse/write with regex.


def read_text(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def get_archived_ids(text: str) -> set:
    """Extract task IDs from archive YAML."""
    import re
    return set(re.findall(r'id:\s*"?(T-\d+)"?', text))


def parse_tasks(text: str) -> list[dict]:
    """Parse task-queue.yaml into list of task dicts (minimal parser)."""
    import re
    tasks = []
    # Find all "- id: T-XXX" blocks
    # Each block starts at "- id:" and runs until the next "- id:" or EOF
    starts = [m.start() for m in re.finditer(r'^- id: (T-\d+)', text, re.MULTILINE)]
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(text)
        block = text[start:end]

        # Extract id from first line
        id_match = re.match(r'- id: (T-\d+)', block)
        if not id_match:
            continue
        task = {'id': id_match.group(1), 'depends_on': []}

        in_depends = False
        for line in block.split('\n')[1:]:  # skip first line (id)
            stripped = line.strip()
            # End multi-line list when we hit a non-list field
            if not stripped.startswith('- ') and ':' in stripped:
                in_depends = False

            if stripped.startswith('status:'):
                task['status'] = stripped.split(':', 1)[1].strip()
            elif stripped.startswith('score:'):
                try:
                    task['score'] = int(stripped.split(':', 1)[1].strip())
                except ValueError:
                    task['score'] = 0
            elif stripped.startswith('type:'):
                task['type'] = stripped.split(':', 1)[1].strip()
            elif stripped.startswith('depends_on:'):
                rest = stripped.split(':', 1)[1].strip()
                in_depends = True
                if rest == '[]':
                    task['depends_on'] = []
                    in_depends = False
            elif in_depends and stripped.startswith('- T-'):
                task['depends_on'].append(stripped[2:].strip())

        tasks.append(task)
    return tasks


def type_priority(t: str) -> int:
    """verify > improve > create for tiebreaking."""
    return {'verify': 2, 'improve': 1, 'create': 0}.get(t, 0)


def task_sort_key(task: dict) -> tuple:
    return (
        -task.get('score', 0),
        -type_priority(task.get('type', '')),
        task.get('id', 'T-999'),
    )


# -- Lock helpers ----------------------------------------------------------


def is_process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def clean_stale_locks():
    """Remove lock files for dead processes and return cleaned task IDs."""
    cleaned = []
    if not CLAIMS_DIR.exists():
        return cleaned
    for lock_file in CLAIMS_DIR.glob("T-*.lock"):
        try:
            data = json.loads(lock_file.read_text())
            pid = data.get("pid", 0)
            if pid and not is_process_alive(pid):
                lock_file.unlink()
                task_id = lock_file.stem  # "T-XXX"
                cleaned.append(task_id)
        except (json.JSONDecodeError, OSError):
            # Corrupt lock file, remove it
            try:
                lock_file.unlink()
                cleaned.append(lock_file.stem)
            except OSError:
                pass
    return cleaned


def existing_locks() -> set:
    """Return set of task IDs that currently have lock files."""
    if not CLAIMS_DIR.exists():
        return set()
    return {f.stem for f in CLAIMS_DIR.glob("T-*.lock")}


# -- YAML update -----------------------------------------------------------


def update_task_status(task_id: str, new_status: str, claimed_at: str | None):
    """Update a task's status and claimed_at in task-queue.yaml."""
    import re
    text = QUEUE_FILE.read_text()

    # Find the task block and update status
    # Match "- id: T-XXX" and subsequent lines until next "- id:" or end
    pattern = rf'(- id: {re.escape(task_id)}\n)(.*?)(?=\n- id:|\Z)'
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return

    block = match.group(2)
    block = re.sub(r'status: \S+', f'status: {new_status}', block)
    if claimed_at:
        block = re.sub(r"claimed_at: .*", f"claimed_at: '{claimed_at}'", block)
    else:
        block = re.sub(r"claimed_at: .*", "claimed_at: null", block)

    text = text[:match.start(2)] + block + text[match.end(2):]

    # Update meta.updated_at
    now_iso = datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00")
    text = re.sub(r"updated_at: .*", f"updated_at: '{now_iso}'", text, count=1)

    QUEUE_FILE.write_text(text)


# -- Main ------------------------------------------------------------------


def claim():
    CLAIMS_DIR.mkdir(parents=True, exist_ok=True)

    # Acquire global lock (blocks until available)
    lock_fh = open(GLOBAL_LOCK, 'w')
    try:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)

        # Clean stale locks
        cleaned = clean_stale_locks()
        if cleaned:
            # Reset cleaned tasks to pending
            for tid in cleaned:
                update_task_status(tid, 'pending', None)
            print(f"Cleaned stale locks: {', '.join(cleaned)}", file=sys.stderr)

        # Parse queue and archive
        queue_text = read_text(QUEUE_FILE)
        archive_text = read_text(ARCHIVE_FILE)
        archived_ids = get_archived_ids(archive_text)
        tasks = parse_tasks(queue_text)
        locked = existing_locks()

        # Build candidate list
        candidates = []
        for t in tasks:
            status = t.get('status', '')
            if status not in ('pending', 'improve'):
                continue
            # Skip if already locked by another worker
            if t['id'] in locked:
                continue
            # Check dependencies
            deps = t.get('depends_on', [])
            if deps and not all(d in archived_ids for d in deps):
                continue
            candidates.append(t)

        # Sort by priority
        candidates.sort(key=task_sort_key)

        if not candidates:
            print("", end="")  # empty stdout = nothing to claim
            return 1

        # Claim the best candidate
        task = candidates[0]
        task_id = task['id']
        pid = os.getppid()  # PID of the calling claude process
        now_iso = datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00")

        # Write lock file
        lock_path = CLAIMS_DIR / f"{task_id}.lock"
        lock_data = json.dumps({"pid": pid, "claimedAt": now_iso})
        lock_path.write_text(lock_data)

        # Update YAML
        update_task_status(task_id, 'in_progress', now_iso)

        # Output claimed task ID
        print(task_id, end="")
        return 0

    finally:
        fcntl.flock(lock_fh, fcntl.LOCK_UN)
        lock_fh.close()


def release(task_id: str):
    """Remove lock file for a task."""
    lock_path = CLAIMS_DIR / f"{task_id}.lock"
    try:
        lock_path.unlink(missing_ok=True)
    except OSError:
        pass


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == '--release':
        release(sys.argv[2])
        return 0

    return claim()


if __name__ == "__main__":
    sys.exit(main())
