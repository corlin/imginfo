from fastapi import APIRouter, HTTPException

from ..services.task_store import task_store

router = APIRouter()


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    task = task_store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task
