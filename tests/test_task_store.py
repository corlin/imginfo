from app.services.task_store import TaskStore


def test_task_lifecycle():
    store = TaskStore()

    task = store.create("analysis")
    assert task["status"] == "pending"
    assert task["type"] == "analysis"

    store.mark_running(task["id"])
    assert store.get(task["id"])["status"] == "running"

    store.mark_completed(task["id"], {"id": 123})
    completed = store.get(task["id"])
    assert completed["status"] == "completed"
    assert completed["result"] == {"id": 123}
    assert completed["error"] is None


def test_task_failure_sets_error():
    store = TaskStore()
    task = store.create("generation")

    store.mark_failed(task["id"], "boom")

    failed = store.get(task["id"])
    assert failed["status"] == "failed"
    assert failed["error"] == "boom"
