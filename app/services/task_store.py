"""Small in-process task registry for long-running prototype jobs."""
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, Optional
from uuid import uuid4


TERMINAL_STATUSES = {"completed", "failed"}


class TaskStore:
    def __init__(self) -> None:
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()

    def create(self, task_type: str) -> Dict[str, Any]:
        task_id = uuid4().hex
        task = {
            "id": task_id,
            "type": task_type,
            "status": "pending",
            "result": None,
            "error": None,
            "created_at": _now(),
            "updated_at": _now(),
        }
        with self._lock:
            self._tasks[task_id] = task
        return task.copy()

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            task = self._tasks.get(task_id)
            return task.copy() if task else None

    def mark_running(self, task_id: str) -> None:
        self._update(task_id, status="running", error=None)

    def mark_completed(self, task_id: str, result: Any) -> None:
        self._update(task_id, status="completed", result=result, error=None)

    def mark_failed(self, task_id: str, error: str) -> None:
        self._update(task_id, status="failed", error=error)

    def _update(self, task_id: str, **changes: Any) -> None:
        with self._lock:
            if task_id not in self._tasks:
                return
            self._tasks[task_id].update(changes)
            self._tasks[task_id]["updated_at"] = _now()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


task_store = TaskStore()
