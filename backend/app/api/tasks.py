"""Task status and management API."""
from fastapi import APIRouter, HTTPException
from typing import Optional
from app.orchestration.workflow import WorkflowManager

router = APIRouter()
workflow_manager = WorkflowManager()


@router.get("/{task_id}")
async def get_task_status(task_id: str):
    """Get task status by ID."""
    status = await workflow_manager.get_task_status(task_id)
    
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return status


@router.get("/")
async def list_tasks(limit: int = 10, offset: int = 0):
    """List recent tasks."""
    tasks = await workflow_manager.list_tasks(limit=limit, offset=offset)
    return {"tasks": tasks, "limit": limit, "offset": offset}


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a running task."""
    success = await workflow_manager.cancel_task(task_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Task not found or cannot be cancelled")
    
    return {"status": "cancelled", "task_id": task_id}

