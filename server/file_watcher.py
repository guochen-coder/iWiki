"""
Watch raw/ directory for file changes, auto-ingest or delete.

Depends on: pip install watchdog
"""

from __future__ import annotations

import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "raw"

SUPPORTED = {".md", ".pdf", ".docx", ".pptx", ".xlsx", ".html", ".txt",
             ".csv", ".json", ".xml", ".yaml", ".yml", ".tsv"}


class RawFolderHandler(FileSystemEventHandler):
    def __init__(self, enqueue_fn, delete_fn):
        self._enqueue = enqueue_fn
        self._delete = delete_fn
        self._pending: dict[str, float] = {}
        self._debounce_sec = 1.0

    def _should_process(self, path: str) -> bool:
        ext = Path(path).suffix.lower()
        if ext not in SUPPORTED:
            return False
        if Path(path).name.startswith("."):
            return False
        return True

    def on_created(self, event):
        if event.is_directory or not self._should_process(event.src_path):
            return
        self._pending[event.src_path] = time.time()

    def on_modified(self, event):
        if event.is_directory or not self._should_process(event.src_path):
            return
        self._pending[event.src_path] = time.time()

    def on_deleted(self, event):
        if event.is_directory or not self._should_process(event.src_path):
            return
        self._delete(Path(event.src_path).name)

    def tick(self):
        now = time.time()
        ready = []
        for path, first_seen in list(self._pending.items()):
            if now - first_seen >= self._debounce_sec:
                ready.append(path)
                del self._pending[path]
        for path in ready:
            if Path(path).exists():
                self._enqueue(path, Path(path).name)


def start_watcher(enqueue_fn, delete_fn):
    handler = RawFolderHandler(enqueue_fn, delete_fn)
    observer = Observer()
    observer.schedule(handler, str(RAW_DIR), recursive=True)
    observer.daemon = True
    observer.start()
    return observer, handler
