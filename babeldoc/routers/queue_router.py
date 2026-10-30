from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app_devs import schedule
from babeldoc.routers.po_router import MoveTaskRequest
from schemas.api.po_execptions import PoBusinessError

router = APIRouter()

@router.get("/po/queue")
async def get_queue_status() -> JSONResponse:
    pending = await schedule.get_pending_tasks()
    processing = await schedule.get_processing_tasks()
    completed = await schedule.get_completed_tasks(limit=50)
    return JSONResponse(content={
        "pending": pending,
        "processing": processing,
        "completed": completed,
        "pending_count": len(pending),
        "processing_count": len(processing),
    })

@router.get("/po/queue/{task_id}")
async def get_task_detail(task_id: str) -> JSONResponse:
    task = await schedule.get_task(task_id)
    if task is None:
        raise PoBusinessError(message=f"任务 {task_id} 不存在")
    return JSONResponse(content=task)

@router.post("/po/queue/{task_id}/move")
async def move_task(task_id: str, body: MoveTaskRequest) -> JSONResponse:
    try:
        task = await schedule.move_to_position(task_id, body.position)
    except ValueError as e:
        raise PoBusinessError(message=str(e))
    return JSONResponse(content={
        "message": f"任务已移动到位置 {body.position}",
        "task_id": task.task_id,
        "job_id": task.job_id,
    })

@router.post("/po/queue/{task_id}/move_to_front")
async def move_task_to_front(task_id: str) -> JSONResponse:
    try:
        task = await schedule.move_to_front(task_id)
    except ValueError as e:
        raise PoBusinessError(message=str(e))
    return JSONResponse(content={
        "message": "任务已移动到队首",
        "task_id": task.task_id,
        "job_id": task.job_id,
    })

@router.post("/po/queue/{task_id}/move_to_back")
async def move_task_to_back(task_id: str) -> JSONResponse:
    try:
        task = await schedule.move_to_back(task_id)
    except ValueError as e:
        raise PoBusinessError(message=str(e))
    return JSONResponse(content={
        "message": "任务已移动到队尾",
        "task_id": task.task_id,
        "job_id": task.job_id,
    })

@router.delete("/po/queue/{task_id}")
async def remove_task(task_id: str) -> JSONResponse:
    try:
        task = await schedule.remove(task_id)
    except ValueError as e:
        raise PoBusinessError(message=str(e))
    return JSONResponse(content={
        "message": "任务已从队列移除",
        "task_id": task.task_id,
        "job_id": task.job_id,
    })

@router.post("/po/queue/{task_id}/cancel")
async def cancel_task(task_id: str) -> JSONResponse:
    try:
        task = await schedule.cancel(task_id)
    except ValueError as e:
        raise PoBusinessError(message=str(e))
    return JSONResponse(content={
        "message": f"任务 {task_id} 已取消",
        "task_id": task.task_id,
        "job_id": task.job_id,
        "status": task.status.value,
    })
