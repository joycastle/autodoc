#!/usr/bin/env python3
"""autodoc -- Documentation automation orchestrator with TUI.

Run: .venv/bin/python autodoc.py [--max-workers N] [--once] [--dry-run]
"""

import argparse
import json
import os
import re
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Label, Log, Static, TabbedContent, TabPane

# -- Config ---------------------------------------------------------------

MAX_WORKERS = 3
POLL_INTERVAL = 10
DISCOVER_INTERVAL = 30 * 60
DISCOVER_COOLDOWN = 10 * 60
EXPERT_INTERVAL = 2 * 3600
EXPERT_COOLDOWN = 30 * 60
EXPERT_TASK_THRESHOLD = 10
REVIEW_CATCHUP_DELAY = 600
WORKER_STAGGER = 10
TAB_LINGER_SECS = 8  # seconds to keep finished worker tab before closing
LOG_RETAIN_DAYS = 7

SCRIPT_DIR = Path(__file__).resolve().parent
QUEUE_FILE = SCRIPT_DIR / "_meta" / "task-queue.yaml"
ARCHIVE_FILE = SCRIPT_DIR / "_meta" / "task-archive.yaml"
LOG_DIR = SCRIPT_DIR / "_meta" / "autodoc-logs"

# -- Data ------------------------------------------------------------------


@dataclass
class FinishedRecord:
    wid: int
    exit_code: int
    duration: str
    finished_at: float = field(default_factory=time.time)


@dataclass
class Worker:
    wid: int
    proc: subprocess.Popen
    log_path: Path
    started: float = field(default_factory=time.time)
    log_fh: object = None
    output_lines: list = field(default_factory=list)
    _stop_reader: bool = False


@dataclass
class AuxProcess:
    name: str
    label: str
    proc: subprocess.Popen | None = None
    last_trigger: float = 0.0
    log_path: Path | None = None
    log_fh: object = None
    output_lines: list = field(default_factory=list)
    _stop_reader: bool = False

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def reap(self) -> int | None:
        if self.proc is not None and self.proc.poll() is not None:
            rc = self.proc.returncode
            self._stop_reader = True
            self.proc = None
            if self.log_fh and hasattr(self.log_fh, "close"):
                self.log_fh.close()
                self.log_fh = None
            return rc
        return None


@dataclass
class QueueState:
    pending: int = 0
    improve: int = 0
    in_progress: int = 0
    review_pending: int = 0
    archive: int = 0

    @property
    def claimable(self) -> int:
        return self.pending + self.improve


# -- Helpers ---------------------------------------------------------------


def count_matches(path: Path, pattern: str) -> int:
    if not path.exists():
        return 0
    try:
        return len(re.findall(pattern, path.read_text()))
    except OSError:
        return 0


def parse_queue() -> QueueState:
    return QueueState(
        pending=count_matches(QUEUE_FILE, r"status: pending"),
        improve=count_matches(QUEUE_FILE, r"status: improve"),
        in_progress=count_matches(QUEUE_FILE, r"status: in_progress"),
        review_pending=count_matches(QUEUE_FILE, r"status: review_pending"),
        archive=count_matches(ARCHIVE_FILE, r"  - \{id:"),
    )


def fmt_dur(secs: float) -> str:
    s = int(secs)
    if s < 60:
        return f"{s}s"
    h, rem = divmod(s, 3600)
    m = rem // 60
    return f"{h}h{m:02d}m" if h > 0 else f"{m}m"


def fmt_cd(interval: float, last_ts: float) -> str:
    remaining = interval - (time.time() - last_ts)
    return "due" if remaining <= 0 else fmt_dur(remaining)


def stream_reader(proc, lines, log_fh, stop_fn):
    """Read stream-json from proc.stdout, extract text, append to lines."""
    try:
        for raw in proc.stdout:
            if stop_fn():
                break
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
                t = obj.get("type", "")
                text = ""
                if t == "assistant":
                    for blk in obj.get("message", {}).get("content", []):
                        if blk.get("type") == "text":
                            text += blk.get("text", "")
                elif t == "content_block_delta":
                    d = obj.get("delta", {})
                    if d.get("type") == "text_delta":
                        text = d.get("text", "")
                elif t == "result":
                    text = obj.get("result", "")
                if text:
                    for ln in text.splitlines():
                        lines.append(ln)
                        if log_fh:
                            log_fh.write(ln + "\n")
                            log_fh.flush()
            except json.JSONDecodeError:
                lines.append(raw)
                if log_fh:
                    log_fh.write(raw + "\n")
                    log_fh.flush()
    except (OSError, ValueError):
        pass


# -- CSS -------------------------------------------------------------------

APP_CSS = """
Screen {
    layout: horizontal;
}

#sidebar {
    width: 38;
    border-right: thick $primary;
    padding: 1 1 0 1;
}

#sidebar-title {
    text-style: bold;
    color: $success;
    text-align: center;
    width: 100%;
}

#summary-line {
    height: 1;
    margin: 1 0;
    color: $text;
    text-style: bold;
}

.section-title {
    text-style: bold;
    color: $primary-lighten-2;
    margin-top: 1;
    margin-bottom: 0;
}

.kv {
    height: 1;
}

.kv-key {
    width: 20;
    color: $text-muted;
}

.kv-val {
    text-style: bold;
}

#worker-list {
    margin-top: 0;
    height: auto;
    max-height: 14;
}

.wk-line {
    height: 1;
}

.wk-running {
    color: $success;
}

.wk-done {
    color: $text-muted;
    text-style: italic;
}

.wk-fail {
    color: $error;
    text-style: bold;
}

#main {
    width: 1fr;
}

#status-bar {
    dock: top;
    height: 1;
    background: $primary-darken-3;
    color: $text;
    text-style: bold;
    padding: 0 2;
}

#tabs {
    height: 1fr;
}

Log {
    height: 1fr;
}

#empty-hint {
    width: 100%;
    height: 100%;
    content-align: center middle;
    color: $text-muted;
    text-style: italic;
}
"""


# -- App -------------------------------------------------------------------


class AutodocApp(App):
    CSS = APP_CSS
    TITLE = "autodoc"
    BINDINGS = [
        ("q", "quit_app", "Quit"),
        ("d", "trigger_discover", "Discover"),
        ("e", "trigger_expert", "Expert"),
        ("r", "trigger_review", "Review"),
        ("p", "pause_toggle", "Pause"),
        ("right_square_bracket", "add_worker", "] +Worker"),
        ("left_square_bracket", "remove_worker", "[ -Worker"),
    ]

    def __init__(self, max_workers: int, once: bool, dry_run: bool):
        super().__init__()
        self.max_workers = max_workers
        self.run_once = once
        self.dry_run = dry_run
        self.shutting_down = False
        self.draining = False
        self.paused = False
        self._sigint_count = 0
        self._spawning = False

        self.pool: list[Worker] = []
        self.finished: list[FinishedRecord] = []
        self.next_wid = 1
        self.total_spawned = 0
        self.total_completed = 0
        self.total_failed = 0
        self.start_ts = time.time()
        self.archive_at_start = 0
        self.queue = QueueState()

        now = time.time()
        self.discover = AuxProcess("doc-discover", "discover", last_trigger=now)
        self.expert = AuxProcess("doc-expert", "expert", last_trigger=now)
        self.review_aux = AuxProcess("doc-review", "review", last_trigger=now)

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.main_log_path = LOG_DIR / f"autodoc-{time.strftime('%Y%m%d-%H%M%S')}.log"
        self.main_log_fh = open(self.main_log_path, "a")

        self._active_tabs: set[str] = set()
        # tabs pending removal: tab_id -> removal_time
        self._lingering_tabs: dict[str, float] = {}
        # Pre-create stable worker list labels to avoid DOM rebuild
        self._wk_labels: list[Label] = []

    # -- Compose -----------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(id="sidebar"):
                yield Static("autodoc", id="sidebar-title")
                yield Label("", id="summary-line")
                yield Label("Triggers", classes="section-title")
                yield self._kv("Discover [d]", "v-disc")
                yield self._kv("Expert   [e]", "v-expert")
                yield self._kv("Review   [r]", "v-review")
                yield Label("Workers", classes="section-title")
                yield Vertical(id="worker-list")
            with Vertical(id="main"):
                yield Static("", id="status-bar")
                with TabbedContent(id="tabs"):
                    with TabPane("Events", id="tab-events"):
                        yield Log(id="event-log", auto_scroll=True)
                    with TabPane("History", id="tab-history"):
                        yield Log(id="history-log", auto_scroll=True)
        yield Footer()

    def _kv(self, key: str, val_id: str) -> Horizontal:
        return Horizontal(
            Label(key, classes="kv-key"),
            Label("--", id=val_id, classes="kv-val"),
            classes="kv",
        )

    # -- Lifecycle ---------------------------------------------------------

    def on_mount(self) -> None:
        self._clean_old_logs()
        self.queue = parse_queue()
        self.archive_at_start = self.queue.archive
        self._refresh_ui()
        q = self.queue
        self.emit_log(f"Started: max_workers={self.max_workers}")
        self.emit_log(
            f"Queue: {q.claimable} waiting, {q.in_progress} running, "
            f"{q.review_pending} review | Archive: {q.archive}"
        )

        if self.dry_run:
            self.emit_log("Dry run -- no workers spawned. Press d to discover gaps.")
            return

        self.set_interval(POLL_INTERVAL, self._tick)
        self.set_interval(2, self._flush_output)
        self.call_later(self._tick)

    # -- Logging -----------------------------------------------------------

    def emit_log(self, msg: str):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        try:
            self.query_one("#event-log", Log).write_line(line)
        except Exception:
            pass
        self.main_log_fh.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
        self.main_log_fh.flush()

    # -- UI refresh --------------------------------------------------------

    def _refresh_ui(self):
        q = self.queue
        s = q.archive - self.archive_at_start

        # Compact summary line: the 3 numbers that matter
        self._sv("summary-line",
                 f" {q.claimable} waiting | {len(self.pool)} running | +{s} done")

        # Trigger countdowns with inline hints
        d = "running..." if self.discover.running else fmt_cd(DISCOVER_INTERVAL, self.discover.last_trigger)
        e = "running..." if self.expert.running else fmt_cd(EXPERT_INTERVAL, self.expert.last_trigger)
        r = "running..." if self.review_aux.running else (
            f"{q.review_pending} pending" if q.review_pending > 0 else "idle")
        self._sv("v-disc", d)
        self._sv("v-expert", e)
        self._sv("v-review", r)

        # Status bar: only show state + alerts
        if self.draining:
            n = len(self._all_procs())
            bar = f" DRAINING ({n} remaining) -- press q to force"
        elif self.paused:
            bar = " PAUSED -- press p to resume"
        elif self.total_failed > 0:
            bar = (f" RUNNING | {len(self.pool)}/{self.max_workers} workers | "
                   f"{self.total_failed} failed | +{s} archived | "
                   f"{fmt_dur(time.time() - self.start_ts)}")
        elif self.dry_run:
            bar = " DRY RUN -- press d to discover, q to quit"
        else:
            bar = (f" RUNNING | {len(self.pool)}/{self.max_workers} workers | "
                   f"+{s} archived | {fmt_dur(time.time() - self.start_ts)}")
        try:
            self.query_one("#status-bar", Static).update(bar)
        except Exception:
            pass

        # Worker list (incremental update)
        self._refresh_worker_list()

        # Clean up lingering tabs
        self._clean_lingering_tabs()

    def _sv(self, vid: str, text: str):
        try:
            self.query_one(f"#{vid}", Label).update(text)
        except Exception:
            pass

    def _refresh_worker_list(self):
        """Update worker list incrementally -- no DOM rebuild."""
        try:
            container = self.query_one("#worker-list", Vertical)
        except Exception:
            return

        # Build desired entries
        entries: list[tuple[str, str]] = []
        for w in self.pool:
            dur = fmt_dur(time.time() - w.started)
            entries.append(("wk-running", f"  #{w.wid:<3} ...  {dur}"))
        for rec in reversed(self.finished[-5:]):
            tag = "wk-done" if rec.exit_code == 0 else "wk-fail"
            st = "ok" if rec.exit_code == 0 else "FAIL"
            entries.append((tag, f"  #{rec.wid:<3} {st:<4} {rec.duration}"))

        # Grow/shrink label pool as needed
        while len(self._wk_labels) < len(entries):
            lbl = Label("", classes="wk-line")
            self._wk_labels.append(lbl)
            container.mount(lbl)
        while len(self._wk_labels) > len(entries):
            lbl = self._wk_labels.pop()
            lbl.remove()

        # Update text and classes
        for i, (css, text) in enumerate(entries):
            lbl = self._wk_labels[i]
            lbl.update(text)
            for c in ("wk-running", "wk-done", "wk-fail"):
                if c == css:
                    lbl.add_class(c)
                else:
                    lbl.remove_class(c)

    # -- Tabs --------------------------------------------------------------

    def _add_tab(self, tab_id: str, title: str):
        if tab_id in self._active_tabs:
            # If it was lingering, cancel removal
            self._lingering_tabs.pop(tab_id, None)
            return
        tabs = self.query_one("#tabs", TabbedContent)
        pane = TabPane(title, id=tab_id)
        tabs.add_pane(pane)
        self._active_tabs.add(tab_id)
        self.call_later(lambda: self._mount_log_in_pane(tab_id))

    def _schedule_tab_removal(self, tab_id: str):
        """Mark tab for delayed removal. User can still read it."""
        if tab_id in self._active_tabs:
            self._lingering_tabs[tab_id] = time.time() + TAB_LINGER_SECS
            # Update tab title to show it's done
            try:
                pane = self.query_one(f"#{tab_id}", TabPane)
                old = str(pane._title)  # type: ignore[attr-defined]
                if "..." in old:
                    pane._title = old.replace("...", "done")  # type: ignore[attr-defined]
                    pane.refresh()
            except Exception:
                pass

    def _remove_tab_now(self, tab_id: str):
        if tab_id not in self._active_tabs:
            return
        try:
            tabs = self.query_one("#tabs", TabbedContent)
            # Don't remove if user is currently viewing it
            if hasattr(tabs, 'active') and tabs.active == tab_id:
                # Extend linger
                self._lingering_tabs[tab_id] = time.time() + TAB_LINGER_SECS
                return
            tabs.remove_pane(tab_id)
        except Exception:
            pass
        self._active_tabs.discard(tab_id)
        self._lingering_tabs.pop(tab_id, None)

    def _clean_lingering_tabs(self):
        now = time.time()
        expired = [tid for tid, deadline in self._lingering_tabs.items() if now >= deadline]
        for tid in expired:
            self._remove_tab_now(tid)

    def _mount_log_in_pane(self, tab_id: str):
        try:
            pane = self.query_one(f"#{tab_id}", TabPane)
            log_id = tab_id.replace("tab-", "log-")
            pane.mount(Log(id=log_id, auto_scroll=True))
        except Exception:
            pass

    def _write_to_history(self, wid: int, exit_code: int, duration: str, output_lines: list):
        rec = FinishedRecord(wid=wid, exit_code=exit_code, duration=duration)
        self.finished.append(rec)
        try:
            hist = self.query_one("#history-log", Log)
            st = "ok" if exit_code == 0 else f"FAIL exit={exit_code}"
            hist.write_line(f"--- W#{wid} ({st}, {duration}) ---")
            tail = output_lines[-20:] if output_lines else ["(no output)"]
            for ln in tail:
                hist.write_line(f"  {ln}")
            hist.write_line("")
        except Exception:
            pass

    def _flush_output(self):
        for w in self.pool:
            self._drain(f"log-w{w.wid}", w.output_lines)
        for aux in (self.discover, self.expert, self.review_aux):
            self._drain(f"log-{aux.label}", aux.output_lines)

    def _drain(self, log_id: str, lines: list):
        if not lines:
            return
        try:
            w = self.query_one(f"#{log_id}", Log)
            batch = list(lines)
            lines.clear()
            for ln in batch:
                w.write_line(ln)
        except Exception:
            pass

    # -- Tick --------------------------------------------------------------

    def _tick(self):
        if self.paused and not self.draining:
            self._refresh_ui()
            return

        self._reap_workers()
        self._reap_aux()
        self.queue = parse_queue()

        if self.draining:
            if not self._all_procs():
                self.emit_log("All processes finished.")
                self._finalize_and_exit()
                return
            self._refresh_ui()
            return

        self._maybe_trigger_discover()
        self._maybe_trigger_expert()
        self._maybe_trigger_review()
        self.queue = parse_queue()

        self._do_spawn()
        self._refresh_ui()

        if self.run_once and len(self.pool) == 0 and self.total_spawned > 0:
            self.emit_log("--once: done")
            self._finalize_and_exit()

    # -- Workers -----------------------------------------------------------

    def _reap_workers(self):
        alive = []
        any_succeeded = False
        for w in self.pool:
            if w.proc.poll() is None:
                alive.append(w)
            else:
                w._stop_reader = True
                rc = w.proc.returncode
                self.total_completed += 1
                dur = fmt_dur(time.time() - w.started)
                if rc == 0:
                    self.emit_log(f"W#{w.wid} done ({dur})")
                    any_succeeded = True
                else:
                    self.total_failed += 1
                    self.emit_log(f"W#{w.wid} FAILED exit={rc} ({dur})")
                    self._show_error_in_events(f"W#{w.wid}", w.output_lines, w.log_path)
                self._write_to_history(w.wid, rc, dur, list(w.output_lines))
                self._save_to_main_log(w)
                # Delayed tab removal -- user can still read output
                self._schedule_tab_removal(f"tab-w{w.wid}")
                if w.log_fh and hasattr(w.log_fh, "close"):
                    w.log_fh.close()
        self.pool = alive
        if any_succeeded and not self.draining:
            self._trigger_review_for_completed()

    def _show_error_in_events(self, label, lines: list, log_path: Path | None):
        error_lines = lines[-15:] if lines else []
        if not error_lines and log_path and log_path.exists():
            try:
                content = log_path.read_text().strip()
                if content:
                    error_lines = content.splitlines()[-15:]
            except OSError:
                pass
        if error_lines:
            self.emit_log(f"--- Error from {label} ---")
            for ln in error_lines:
                self.emit_log(f"  {ln}")
            self.emit_log("---")
        else:
            self.emit_log(f"  {label}: no output captured")

    def _trigger_review_for_completed(self):
        if not self.review_aux.running:
            self.emit_log("Auto-review: triggering /doc-review")
            self._spawn_aux(self.review_aux)

    def _save_to_main_log(self, w: Worker):
        try:
            if w.log_path.exists():
                content = w.log_path.read_text().strip()
                if content:
                    sep = "-" * 54
                    self.main_log_fh.write(
                        f"\n{sep}\nW#{w.wid} ({w.log_path.name}):\n{sep}\n{content}\n{sep}\n\n"
                    )
                    self.main_log_fh.flush()
        except OSError:
            pass

    def _claim_task(self) -> str | None:
        """Call claim-task.py to atomically claim a task. Returns task ID or None."""
        script = SCRIPT_DIR / ".claude" / "skills" / "doc-research" / "scripts" / "claim-task.py"
        try:
            result = subprocess.run(
                ["python3", str(script)],
                capture_output=True, text=True, cwd=SCRIPT_DIR, timeout=30,
            )
            task_id = result.stdout.strip()
            if result.returncode == 0 and task_id:
                return task_id
            return None
        except (OSError, subprocess.TimeoutExpired) as e:
            self.emit_log(f"claim-task.py error: {e}")
            return None

    def _spawn_one(self):
        if len(self.pool) >= self.max_workers:
            return
        # Claim BEFORE spawning -- no race possible
        task_id = self._claim_task()
        if not task_id:
            return
        wid = self.next_wid
        self.next_wid += 1
        log_path = LOG_DIR / f"worker-{wid}-{time.strftime('%H%M%S')}.log"
        try:
            log_fh = open(log_path, "w")
            proc = subprocess.Popen(
                ["claude", "-p", "--verbose", "--output-format", "stream-json",
                 f"/doc-research 已认领任务 {task_id}，跳过 STEP 1 直接从 STEP 2 开始。"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                cwd=SCRIPT_DIR, start_new_session=True, text=True, bufsize=1,
            )
        except (OSError, FileNotFoundError) as e:
            self.emit_log(f"FAILED to spawn W#{wid}: {e}")
            # Release the claim since we can't start the worker
            script = SCRIPT_DIR / ".claude" / "skills" / "doc-research" / "scripts" / "claim-task.py"
            subprocess.run(["python3", str(script), "--release", task_id],
                           capture_output=True, cwd=SCRIPT_DIR)
            return
        w = Worker(wid=wid, proc=proc, log_path=log_path, log_fh=log_fh)
        threading.Thread(
            target=stream_reader,
            args=(proc, w.output_lines, log_fh, lambda: w._stop_reader),
            daemon=True,
        ).start()
        self.pool.append(w)
        self.total_spawned += 1
        self.emit_log(f"Spawned W#{wid} -> {task_id} (PID {proc.pid})")
        self._add_tab(f"tab-w{wid}", f"W#{wid} {task_id}")

    def _do_spawn(self):
        if self._spawning or self.draining:
            return
        active = len(self.pool)
        slots = self.max_workers - active
        avail = self.queue.claimable - active
        n = max(0, min(slots, avail))
        if n == 0:
            return
        if n == 1:
            self._spawn_one()
        else:
            self._spawning = True
            threading.Thread(target=self._staggered_spawn, args=(n,), daemon=True).start()

    def _staggered_spawn(self, n: int):
        try:
            for i in range(n):
                if len(self.pool) >= self.max_workers or self.draining:
                    break
                self.call_from_thread(self._spawn_one)
                if i < n - 1:
                    time.sleep(WORKER_STAGGER)
        finally:
            self._spawning = False

    # -- Auxiliary ---------------------------------------------------------

    def _spawn_aux(self, aux: AuxProcess):
        log_path = LOG_DIR / f"{aux.label}-{time.strftime('%H%M%S')}.log"
        log_fh = open(log_path, "w")
        proc = subprocess.Popen(
            ["claude", "-p", "--verbose", "--output-format", "stream-json",
             f"/{aux.name}"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            cwd=SCRIPT_DIR, start_new_session=True, text=True, bufsize=1,
        )
        aux.proc = proc
        aux.log_path = log_path
        aux.log_fh = log_fh
        aux.last_trigger = time.time()
        aux.output_lines = []
        aux._stop_reader = False
        threading.Thread(
            target=stream_reader,
            args=(proc, aux.output_lines, log_fh, lambda: aux._stop_reader),
            daemon=True,
        ).start()
        self.emit_log(f"Spawned /{aux.name} (PID {proc.pid})")
        self._add_tab(f"tab-{aux.label}", aux.label.title())

    def _reap_aux(self):
        for aux in (self.discover, self.expert, self.review_aux):
            lines_snap = list(aux.output_lines)
            log_path = aux.log_path
            rc = aux.reap()
            if rc is not None:
                if rc == 0:
                    self.emit_log(f"/{aux.name} done")
                else:
                    self.emit_log(f"/{aux.name} FAILED exit={rc}")
                    self._show_error_in_events(aux.name, lines_snap, log_path)
                self._schedule_tab_removal(f"tab-{aux.label}")

    def _maybe_trigger_discover(self):
        if self.discover.running:
            return
        since = time.time() - self.discover.last_trigger
        if self.queue.claimable == 0 and len(self.pool) == 0 and since >= DISCOVER_COOLDOWN:
            self.emit_log("Trigger /doc-discover: queue empty")
            self._spawn_aux(self.discover)
        elif since >= DISCOVER_INTERVAL:
            self.emit_log("Trigger /doc-discover: periodic")
            self._spawn_aux(self.discover)

    def _maybe_trigger_expert(self):
        if self.expert.running:
            return
        since = time.time() - self.expert.last_trigger
        if since >= EXPERT_INTERVAL:
            self.emit_log("Trigger /doc-expert: periodic")
            self._spawn_aux(self.expert)
        elif since >= EXPERT_COOLDOWN:
            delta = self.queue.archive - self.archive_at_start
            if delta > 0 and delta % EXPERT_TASK_THRESHOLD == 0:
                self.emit_log(f"Trigger /doc-expert: {delta} completed")
                self._spawn_aux(self.expert)

    def _maybe_trigger_review(self):
        if self.review_aux.running:
            return
        since = time.time() - self.review_aux.last_trigger
        if self.queue.review_pending > 0 and since >= REVIEW_CATCHUP_DELAY:
            self.emit_log(f"Trigger /doc-review: {self.queue.review_pending} pending")
            self._spawn_aux(self.review_aux)

    # -- Actions -----------------------------------------------------------

    def action_quit_app(self):
        self._sigint_count += 1
        if self._sigint_count == 1 and self._all_procs():
            self.draining = True
            n = len(self._all_procs())
            self.emit_log(f"Draining {n} process(es)... press q again to force quit.")
            self._refresh_ui()
        else:
            self._force_cleanup()
            self.exit()

    def action_trigger_discover(self):
        if not self.discover.running:
            self.emit_log("Manual: /doc-discover")
            self._spawn_aux(self.discover)

    def action_trigger_expert(self):
        if not self.expert.running:
            self.emit_log("Manual: /doc-expert")
            self._spawn_aux(self.expert)

    def action_trigger_review(self):
        if not self.review_aux.running:
            self.emit_log("Manual: /doc-review")
            self._spawn_aux(self.review_aux)

    def action_pause_toggle(self):
        self.paused = not self.paused
        self.emit_log("PAUSED" if self.paused else "RESUMED")
        self._refresh_ui()

    def action_add_worker(self):
        if self.max_workers < 8:
            self.max_workers += 1
            self.emit_log(f"Max workers -> {self.max_workers}")
            self._refresh_ui()

    def action_remove_worker(self):
        if self.max_workers > 1:
            self.max_workers -= 1
            self.emit_log(f"Max workers -> {self.max_workers}")
            self._refresh_ui()

    # -- Cleanup -----------------------------------------------------------

    def _all_procs(self) -> list[subprocess.Popen]:
        procs = [w.proc for w in self.pool if w.proc.poll() is None]
        for aux in (self.discover, self.expert, self.review_aux):
            if aux.proc and aux.proc.poll() is None:
                procs.append(aux.proc)
        return procs

    def _finalize_and_exit(self):
        self.queue = parse_queue()
        s = self.queue.archive - self.archive_at_start
        self.emit_log(
            f"Summary: {fmt_dur(time.time() - self.start_ts)} uptime, "
            f"{self.total_spawned} spawned, {self.total_completed} finished, "
            f"{self.total_failed} failed, +{s} archived"
        )
        self.emit_log("Goodbye.")
        self.main_log_fh.close()
        self.exit()

    def _force_cleanup(self):
        if self.shutting_down:
            return
        self.shutting_down = True
        procs = self._all_procs()
        self.emit_log(f"Force killing {len(procs)} process(es)...")

        for p in procs:
            try:
                os.killpg(os.getpgid(p.pid), signal.SIGTERM)
            except (OSError, ProcessLookupError):
                pass

        deadline = time.time() + 5
        for p in procs:
            try:
                p.wait(timeout=max(0, deadline - time.time()))
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(p.pid), signal.SIGKILL)
                except (OSError, ProcessLookupError):
                    pass

        for w in self.pool:
            if w.log_fh and hasattr(w.log_fh, "close"):
                w.log_fh.close()
        for aux in (self.discover, self.expert, self.review_aux):
            if aux.log_fh and hasattr(aux.log_fh, "close"):
                aux.log_fh.close()

        self.queue = parse_queue()
        s = self.queue.archive - self.archive_at_start
        self.emit_log(
            f"Summary: {fmt_dur(time.time() - self.start_ts)} uptime, "
            f"{self.total_spawned} spawned, {self.total_completed} finished, "
            f"{self.total_failed} failed, +{s} archived"
        )
        self.emit_log("Goodbye.")
        self.main_log_fh.close()

    def _clean_old_logs(self):
        if not LOG_DIR.exists():
            return
        cutoff = time.time() - LOG_RETAIN_DAYS * 86400
        for f in LOG_DIR.glob("*.log"):
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
            except OSError:
                pass


# -- Entry -----------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="autodoc TUI orchestrator")
    parser.add_argument("--max-workers", type=int, default=MAX_WORKERS)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    AutodocApp(min(args.max_workers, 8), args.once, args.dry_run).run()


if __name__ == "__main__":
    main()
