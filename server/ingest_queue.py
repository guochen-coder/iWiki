"""
Persistent ingest queue with serial processing and auto-retry.

- Serial: one ingest at a time, FIFO ordering
- Disk-persisted: .ingest_queue.json survives server restart
- Auto-retry: up to 3 attempts on failure
"""

from __future__ import annotations

import json
import asyncio
import uuid
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUEUE_FILE = PROJECT_ROOT / ".ingest_queue.json"


@dataclass
class QueuedIngest:
    task_id: str
    file_path: str
    raw_name: str
    status: str = "queued"
    retries: int = 0
    max_retries: int = 3
    created_at: str = ""
    error: str | None = None
    result: dict | None = None
    progress: list[dict] = field(default_factory=list)


class IngestQueue:
    def __init__(self, on_complete=None):
        self._lock = asyncio.Lock()
        self._tasks: dict[str, QueuedIngest] = {}
        self._processing = False
        self._on_complete = on_complete
        self._restore()

    def _restore(self):
        if QUEUE_FILE.exists():
            try:
                data = json.loads(QUEUE_FILE.read_text())
                for t in data:
                    task = QueuedIngest(**t)
                    if task.status == "processing":
                        task.status = "queued"
                    self._tasks[task.task_id] = task
            except (json.JSONDecodeError, TypeError):
                pass

    def _persist(self):
        try:
            data = [asdict(t) for t in self._tasks.values()]
            tmp = QUEUE_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            tmp.replace(QUEUE_FILE)
        except Exception:
            pass

    async def enqueue(self, file_path: str, raw_name: str) -> str:
        async with self._lock:
            tid = uuid.uuid4().hex[:12]
            task = QueuedIngest(
                task_id=tid,
                file_path=file_path,
                raw_name=raw_name,
                created_at=datetime.now().isoformat(),
            )
            self._tasks[tid] = task
            self._persist()
        asyncio.create_task(self._worker())
        return tid

    async def _worker(self):
        if self._processing:
            return

        async with self._lock:
            self._processing = True
            pending = [t for t in self._tasks.values() if t.status == "queued"]
            if not pending:
                self._processing = False
                return
            task = pending[0]
            task.status = "processing"
            self._persist()

        try:
            from tools import ingest
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, ingest.ingest, task.file_path, True)
            async with self._lock:
                task.status = "done"
                task.result = result
                self._persist()
            if self._on_complete:
                await self._on_complete(task)
        except Exception as e:
            async with self._lock:
                task.retries += 1
                task.error = str(e)[:500]
                task.status = "queued" if task.retries < task.max_retries else "failed"
                self._persist()
        finally:
            async with self._lock:
                self._processing = False
            asyncio.create_task(self._worker())

    async def cancel(self, task_id: str) -> bool:
        async with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status == "queued":
                task.status = "failed"
                task.error = "Cancelled by user"
                self._persist()
                return True
            return False

    async def retry(self, task_id: str) -> bool:
        async with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status == "failed":
                task.status = "queued"
                task.retries = 0
                task.error = None
                self._persist()
                asyncio.create_task(self._worker())
                return True
            return False

    def get_all(self) -> list[dict]:
        tasks = sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)
        return [asdict(t) for t in tasks]
