# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: File watcher for automatic recompilation.

Tries watchdog (fsevents/inotify) first, falls back to polling if unavailable.
Mirrors the Go version's Watch() in internal/compiler/watch.go.
"""
from __future__ import annotations
import os
import threading
import time

from synth_wiki import log
from synth_wiki import paths
from synth_wiki.config import load as load_config
from synth_wiki.paths import is_ignored


def watch(project_name: str, debounce_seconds: int = 2, config_path: str = "") -> None:
    """Watch source directories and auto-compile on changes.

    1. Runs an initial compile to catch files added while watcher was stopped.
    2. Tries watchdog (fsevents on macOS, inotify on Linux) for real-time events.
    3. Falls back to polling if watchdog is not installed.
    """
    from synth_wiki.compiler.pipeline import compile as do_compile, CompileOpts

    if debounce_seconds <= 0:
        debounce_seconds = 2

    cfg = load_config(config_path or paths.config_path(), project_name)
    source_paths = cfg.resolve_sources()

    # Initial compile
    log.info("running initial compile before watching")
    result = do_compile(project_name, CompileOpts(config_path=config_path or paths.config_path()))
    if result.added > 0 or result.modified > 0 or result.removed > 0:
        log.info("initial compile complete",
                 added=result.added, summarized=result.summarized,
                 concepts=result.concepts_extracted, articles=result.articles_written)
    else:
        log.info("initial compile: nothing new to process")

    # Try watchdog first
    if _try_watchdog(project_name, source_paths, debounce_seconds, config_path):
        return

    # Fallback to polling
    log.info("watchdog not available, using polling mode",
             sources=source_paths, interval=f"{debounce_seconds * 2}s")
    _watch_poll(project_name, source_paths, cfg.ignore, debounce_seconds * 2, config_path)


def _try_watchdog(project_name: str, source_paths: list[str],
                  debounce_seconds: int, config_path: str) -> bool:
    """Try to use watchdog for file system events. Returns True if running."""
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler, FileSystemEvent
    except ImportError:
        return False

    from synth_wiki.compiler.pipeline import compile as do_compile, CompileOpts

    compile_lock = threading.Lock()
    timer_holder: list[threading.Timer] = [None]

    def trigger_compile(trigger_path: str) -> None:
        if not compile_lock.acquire(blocking=False):
            log.info("compile already in progress, skipping", trigger=trigger_path)
            return
        try:
            log.info("compiling after change", trigger=trigger_path)
            result = do_compile(project_name, CompileOpts(
                config_path=config_path or paths.config_path()))
            log.info("compile complete",
                     summarized=result.summarized,
                     concepts=result.concepts_extracted,
                     articles=result.articles_written)
        finally:
            compile_lock.release()

    class Handler(FileSystemEventHandler):
        def on_any_event(self, event: FileSystemEvent) -> None:
            if event.is_directory and event.event_type not in ("created", "deleted"):
                return
            log.info("file change detected", path=event.src_path, op=event.event_type)

            if timer_holder[0] is not None:
                timer_holder[0].cancel()
            timer_holder[0] = threading.Timer(
                debounce_seconds, trigger_compile, args=[event.src_path])
            timer_holder[0].daemon = True
            timer_holder[0].start()

    observer = Observer()
    handler = Handler()
    for sp in source_paths:
        if os.path.isdir(sp):
            observer.schedule(handler, sp, recursive=True)

    observer.start()
    log.info("watching for changes (watchdog)", sources=source_paths, debounce=debounce_seconds)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
    return True


def _watch_poll(project_name: str, source_paths: list[str], ignore: list[str],
                interval_seconds: int, config_path: str) -> None:
    """Periodically scan source directories for changes and trigger compile."""
    from synth_wiki.compiler.pipeline import compile as do_compile, CompileOpts

    compile_lock = threading.Lock()
    snapshot = _scan_snapshot(source_paths, ignore)
    log.info("initial snapshot", files=len(snapshot))

    try:
        while True:
            time.sleep(interval_seconds)
            new_snapshot = _scan_snapshot(source_paths, ignore)
            changed = []

            # New or modified files
            for path, meta in new_snapshot.items():
                old_meta = snapshot.get(path)
                if old_meta is None:
                    changed.append(path)
                    log.info("new file detected", path=path)
                elif old_meta != meta:
                    changed.append(path)
                    log.info("file modified", path=path)

            # Deleted files
            for path in snapshot:
                if path not in new_snapshot:
                    changed.append(path)
                    log.info("file removed", path=path)

            snapshot = new_snapshot

            if changed:
                log.info("changes detected", count=len(changed))
                if not compile_lock.acquire(blocking=False):
                    log.info("compile already in progress, skipping")
                    continue
                try:
                    log.info("compiling after change", trigger=changed[0])
                    result = do_compile(project_name, CompileOpts(
                        config_path=config_path or paths.config_path()))
                    log.info("compile complete",
                             summarized=result.summarized,
                             concepts=result.concepts_extracted,
                             articles=result.articles_written)
                finally:
                    compile_lock.release()
    except KeyboardInterrupt:
        pass


def _scan_snapshot(source_paths: list[str], ignore: list[str]) -> dict[str, str]:
    """Build a map of file path -> quick hash (size + mtime) for change detection."""
    snapshot: dict[str, str] = {}
    for src_dir in source_paths:
        if not os.path.isdir(src_dir):
            continue
        for root, _dirs, files in os.walk(src_dir):
            for fname in files:
                abs_path = os.path.join(root, fname)
                if is_ignored(abs_path, ignore):
                    continue
                info = os.stat(abs_path)
                snapshot[abs_path] = f"{info.st_size}-{info.st_mtime_ns}"
    return snapshot
