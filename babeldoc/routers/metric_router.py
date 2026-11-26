from fastapi import APIRouter
from fastapi.responses import StreamingResponse, JSONResponse
from app_devs import schedule
from babeldoc.routers.po_router import MoveTaskRequest
from schemas.api.po_execptions import PoBusinessError
from babeldoc.services.metrics import MetricsService
from babeldoc.app_devs import logger
from pydantic import BaseModel, Field
from typing import Optional


metrics = MetricsService.get_instance()

router = APIRouter()


def _apply_user_scope(user_id: Optional[str], user_role: Optional[str]) -> Optional[str]:
    """
    根据 user_role 决定是否按 user_id 过滤：
    - user_role == '0'（管理员）-> 返回 None，表示不过滤
    - 其他 -> 返回 user_id，按指定用户过滤
    """
    if user_role == "0":
        return None
    return user_id if user_id else None



class A(BaseModel):
    pageNo: int = Field(..., description="页码")
    pageSize: int = Field(..., description="每页数量")

    task_type: str | None = Field(None, description="任务类型") # TEXT PICTURE FILE 不传表示所有类型
    target_lang: str | None = Field(None, description="语言") # en zh ja ko 不传表示所有语言

    start_date: str = Field(..., description="开始日期")
    end_date: str = Field(..., description="结束日期")
    status: str | None = Field(None, description="状态")

    user_id: Optional[str] = Field(None, description="用户ID")
    user_role: Optional[str] = Field(None, description="用户角色，0为管理员")

class B(BaseModel):
    start_date: str | None = Field(None, description="开始日期")
    end_date: str | None = Field(None, description="结束日期")
    status: str | None = Field(None, description="状态")

    user_id: Optional[str] = Field(None, description="用户ID")
    user_role: Optional[str] = Field(None, description="用户角色，0为管理员")

class C(BaseModel):
    start_date: str = Field(..., description="开始日期")
    end_date: str = Field(..., description="结束日期")

    user_id: Optional[str] = Field(None, description="用户ID")
    user_role: Optional[str] = Field(None, description="用户角色，0为管理员")

@router.post("/metric/date_range")
async def get_metric(request: A) -> JSONResponse:
    """
    输入：start_date, end_date
    输出：日期范围内的翻译任务明细列表
    输出：日期范围内的翻译任务明细列表
    """
    

    return JSONResponse(content=metrics.list_by_date_range(
        pageNo=request.pageNo,
        pageSize=request.pageSize,
        start_date=request.start_date,
        end_date=request.end_date,
        task_type=request.task_type,
        language=request.target_lang,
        status=request.status,
        user_id=_apply_user_scope(request.user_id, request.user_role),
    ))






@router.post("/metric/export")
async def export_excel(request: A):
    """导出日期范围内的翻译记录为 Excel 文件下载"""
    data = metrics.export_to_excel(
        start_date=request.start_date,
        end_date=request.end_date,
        task_type=request.task_type,
        language=request.target_lang,
        status=request.status,
        user_id=_apply_user_scope(request.user_id, request.user_role),
    )
    filename = f"translate_records_{request.start_date}_{request.end_date}.xlsx"
    from io import BytesIO
    return StreamingResponse(
        BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/metric/all")
async def get_sum(request: B) -> JSONResponse:
    """
    输出：翻译总次数 + 按语言分组 + 按类型分组
    """
    result = metrics.count_all(
        start_date=request.start_date,
        end_date=request.end_date,
        status=request.status,
        user_id=_apply_user_scope(request.user_id, request.user_role),
    )
    total_item = next((x for x in result["list"] if x["key"] == "total"), {})
    logger.debug(
        "all stats: total=%s | start=%s end=%s status=%s",
        total_item.get("value", 0),
        request.start_date,
        request.end_date,
        request.status,
    )
    return JSONResponse(content=result)


class single(BaseModel):
    user_id: Optional[str] = Field(None, description="用户ID")
    user_role: Optional[str] = Field(None, description="用户角色，0为管理员")

@router.post("/metric/interface1")
async def get_interface1(request: single) -> JSONResponse:
    """
    输入：user_id, user_role
    输出：翻译任务概览
    """
    return JSONResponse(content=metrics.interface1(
        user_id=_apply_user_scope(request.user_id, request.user_role),
    ))


@router.post("/metric/interface2")
async def get_interface2(request: C) -> JSONResponse:
    """
    输入：start_date, end_date
    输出：日期范围内的翻译任务概览
    """
    return JSONResponse(content=metrics.interface2(
        start_date=request.start_date,
        end_date=request.end_date,
        user_id=_apply_user_scope(request.user_id, request.user_role),
    ))


@router.post("/metric/interface3")
async def get_interface3(request: C) -> JSONResponse:
    """
    输入：start_date, end_date
    输出：日期范围内的翻译任务概览
    """
    return JSONResponse(content=metrics.interface3(
        start_date=request.start_date,
        end_date=request.end_date,
        user_id=_apply_user_scope(request.user_id, request.user_role),
    ))


from fastapi import HTTPException
from babeldoc.schedule.schedule import Schedule
from datetime import datetime
import time

sche = Schedule.get_instance()
class single2(BaseModel):
    task_id:str


@router.post("/metric/move_up")
def move_up(request: single2):
    try:
        sche.move_up(request.task_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail="排队接口异常")
    return JSONResponse(content={"message": "OK"}, status_code=200)


@router.post("/metric/move_down")
def move_down(request: single2):
    try:
        sche.move_down(request.task_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail="排队接口异常")
    return JSONResponse(content={"message": "OK"}, status_code=200)


@router.post("/metric/remove")
def remove(request: single2):
    try:
        sche.remove(request.task_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail="排队接口异常")
    return JSONResponse(content={"message": "OK"}, status_code=200)


class move_to_postition_(BaseModel):
    task_id: str
    position: int 
    user_id: Optional[str] = Field(None, description="用户ID")
    user_role: Optional[str] = Field(None, description="用户角色，0为管理员")

@router.post("/metric/move_to_position")
def move_to_position(request: move_to_postition_):
    try:
        sche.move_to_position(request.task_id, request.position-1)
    except Exception as e:
        raise HTTPException(status_code=500, detail="排队接口异常")
    return JSONResponse(content={"message": "OK"}, status_code=200)

class cancel_(BaseModel): 
    task_id: str
    user_id: Optional[str] = Field(None, description="用户ID")
    user_role: Optional[str] = Field(None, description="用户角色，0为管理员")
@router.post("/metric/cancel")
def cancel(request: single2):
    try:
        sche.cancel(request.task_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail="排队接口异常")
    return JSONResponse(content={"message": "OK"}, status_code=200)

@router.post("/metric/get_pending")
def get_pending(request: single):
    tasks = sche.get_pending()
    scope = _apply_user_scope(request.user_id, request.user_role)
    if scope is not None:
        tasks = [t for t in tasks if t.zdata.USER_ID == scope]

    res = []
    try:
        for index, task in enumerate(tasks):
            item = {
                "position": index, 
                "task_id": task.task_id,
                "task_name": "附件翻译" if task.zdata.FILE_ARCID else "截图翻译",
                "created_at": datetime.fromtimestamp(task.created_at).strftime("%Y-%m-%d %H:%M:%S"), # 转格式为字符串YYYY-MM-DD HH:MM:SS
                "file_name": task.file_name if task.file_name else "截图",
                "predicted_time": 20,
                "status": task.status.value,
            }
            res.append(item)
        return JSONResponse(content={"message": "OK", "data": res}, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail="排队接口异常")

@router.post("/metric/get_processing")
def get_processing(request: single):
    tasks = sche.get_processing()
    scope = _apply_user_scope(request.user_id, request.user_role)
    if scope is not None:
        tasks = [t for t in tasks if t.zdata.USER_ID == scope]
    res = []
    try:
        for task in tasks:
            item = {
                "task_id": task.task_id,
                "task_name": "附件翻译" if task.zdata.FILE_ARCID else "截图翻译",
                "created_at": datetime.fromtimestamp(task.created_at).strftime("%Y-%m-%d %H:%M:%S"), # 转格式为字符串YYYY-MM-DD HH:MM:SS
                "file_name": task.file_name if task.file_name else "截图",
                "predicted_time": 20,
                "status": task.status.value,
            }
            res.append(item)
        return JSONResponse(content={"message": "OK", "data": res}, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail="排队接口异常")



@router.post("/metric/get_completed")
def get_completed(request: single):
    tasks = sche.get_completed()
    scope = _apply_user_scope(request.user_id, request.user_role)
    if scope is not None:
        tasks = [t for t in tasks if t.zdata.USER_ID == scope]
    res = []
    try:
        for task in tasks:
            item = {
                "task_id": task.task_id,
                "task_name": "附件翻译" if task.zdata.FILE_ARCID else "截图翻译",
                "created_at": datetime.fromtimestamp(task.created_at).strftime("%Y-%m-%d %H:%M:%S"), # 转格式为字符串YYYY-MM-DD HH:MM:SS
                "file_name": task.file_name if task.file_name else "截图",
                "predicted_time": 20,
                "status": task.status.value,
            }
            res.append(item)
        return JSONResponse(content={"message": "OK", "data": res}, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail="排队接口异常")



class D(BaseModel):
    pageNo: int = Field(1, description="页码")
    pageSize: int = Field(10, description="每页数量")
    file_name: Optional[str] = Field(None, description="文件名")
    status: Optional[str] = Field(None, description="状态")

    user_id: Optional[str] = Field(None, description="用户ID")
    user_role: Optional[str] = Field(None, description="用户角色，0为管理员")



# 前端友好状态 → 内部状态映射
_STATUS_ALIAS = {
    "queue": "PENDING",
    "running": "PROCESSING",
    "completed": "COMPLETED",
    "failed": "FAILED",
    "cancelled": "CANCELLED",
}


def _map_status(raw: Optional[str]) -> Optional[str]:
    """把前端传来的 status 映射为内部 TaskStatus 值"""
    if raw is None:
        return None
    lower = raw.lower()
    return _STATUS_ALIAS.get(lower, raw.upper())


@router.post("/metric/get_list")
def get_list(request: D):
    """
    输入：pageNo, pageSize, file_name, status（queue/running/completed/failed 或原始状态值）
    输出：翻译任务列表（排队中 + 执行中 + 已完成/已失败），按创建时间倒序分页
    """
    scope = _apply_user_scope(request.user_id, request.user_role)
    internal_status = _map_status(request.status)

    wait_len = len(sche.get_pending())
    processing_len = len(sche.get_processing())

    # 构建排队位置映射：task_id -> 排队序号（1-based）
    pending_pos_map: dict[str, int] = {}
    for idx, t in enumerate(sche.get_pending()):
        pending_pos_map[t.task_id] = idx + 1  # 1-based，0 = 队首

    # 收集原始时间戳用于排序
    raw_items: list[tuple[float, dict]] = []

    # 1. 从内存取排队中 + 执行中任务
    if internal_status in (None, "PENDING", "PROCESSING"):
        mem_tasks = list(sche.get_pending()) + list(sche.get_processing())
        if scope is not None:
            mem_tasks = [t for t in mem_tasks if t.zdata.USER_ID == scope]
        if internal_status is not None:
            mem_tasks = [t for t in mem_tasks if t.status.value == internal_status]
        if request.file_name is not None:
            kw = request.file_name.strip().lower()
            mem_tasks = [t for t in mem_tasks if (t.file_name or "").lower().startswith(kw)]

        for task in mem_tasks:
            base = task.started_at or task.created_at
            elapsed = round(time.time() - base)
            raw_items.append((task.created_at, {
                "task_id": task.task_id,
                "task_name": "附件翻译" if task.zdata.FILE_ARCID else "截图翻译",
                "created_at": datetime.fromtimestamp(task.created_at).strftime("%Y-%m-%d %H:%M:%S"),
                "file_name": task.file_name if task.file_name else "截图",
                "predicted_time": max(0, elapsed),
                "status": task.status.value.lower(),
                "queue_position": pending_pos_map.get(task.task_id, None),
            }))

    # 2. 从数据库取已完成/已失败/已取消任务
    if internal_status in (None, "COMPLETED", "FAILED", "CANCELLED"):
        db_status = None
        if internal_status is not None and internal_status not in ("PENDING", "PROCESSING"):
            db_status = internal_status.lower()
        db_rows = metrics.get_completed(
            file_name=request.file_name,
            status=db_status,
            user_id=scope,
        )
        for row in db_rows:
            elapsed = None
            if row.get("completed_at") is not None and row.get("created_at") is not None:
                elapsed = round(row["completed_at"] - row["created_at"])
            raw_items.append((row["created_at"], {
                "task_id": row["task_id"],
                "task_name": "附件翻译" if row.get("file_name") else "截图翻译",
                "created_at": datetime.fromtimestamp(row["created_at"]).strftime("%Y-%m-%d %H:%M:%S"),
                "file_name": row["file_name"] if row.get("file_name") else "截图",
                "predicted_time": elapsed,
                "status": row["status"].lower(),
                "queue_position": None,
            }))

    # 3. 按创建时间倒序 + 去重（task_id 相同只保留时间新的那条）
    raw_items.sort(key=lambda x: x[0], reverse=True)
    seen_ids = set()
    deduped = []
    for _, item in raw_items:
        if item["task_id"] not in seen_ids:
            seen_ids.add(item["task_id"])
            deduped.append(item)

    # 4. 分页
    total = len(deduped)
    offset = (request.pageNo - 1) * request.pageSize
    page_data = deduped[offset:offset + request.pageSize]

    logger.debug(
        "get_list: total=%s | pageNo=%s pageSize=%s | wait=%s processing=%s",
        total, request.pageNo, request.pageSize, wait_len, processing_len
    )
    logger.debug("get_list: page_data=%s", page_data)

    return JSONResponse(
        content={
            "message": "OK",
            "pageNo": request.pageNo,
            "pageSize": request.pageSize,
            "data": page_data,
            "wait_num": wait_len,
            "processing_num": processing_len,
            "current_concurrency": processing_len,
            "total_concurrency": 5,
            "total": total
        },
        status_code=200,
    )