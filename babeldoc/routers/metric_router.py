from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app_devs import schedule
from babeldoc.routers.po_router import MoveTaskRequest
from schemas.api.po_execptions import PoBusinessError
from babeldoc.services.metrics import MetricsService
from babeldoc.app_devs import logger
metrics = MetricsService.get_instance()

router = APIRouter()

@router.post("/metric/date_range")
async def get_metric(request) -> JSONResponse:
    """
    输入：start_date, end_date
    输出：翻译任务统计信息
    """
    logger.debug(metrics.count_by_date_range(start_date=request.start_date, end_date=request.end_date))
    return JSONResponse(content=metrics.count_by_date_range(start_date=request.start_date, end_date=request.end_date))


@router.post("/metric/all")
async def get_sum(request) -> JSONResponse:
    """
    输出：翻译任务总数
    """
    logger.debug(metrics.count_all(target_lang=request.target_lang, task_type=request.task_type, start_date=request.start_date, end_date=request.end_date))
    return JSONResponse(content=metrics.count_all(target_lang=request.target_lang, task_type=request.task_type, start_date=request.start_date, end_date=request.end_date))

