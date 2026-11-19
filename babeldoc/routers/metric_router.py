from fastapi import APIRouter
from fastapi.responses import StreamingResponse, JSONResponse
from app_devs import schedule
from babeldoc.routers.po_router import MoveTaskRequest
from schemas.api.po_execptions import PoBusinessError
from babeldoc.services.metrics import MetricsService
from babeldoc.app_devs import logger
from pydantic import BaseModel, Field

metrics = MetricsService.get_instance()

router = APIRouter()

class A(BaseModel):
    pageNo: int = Field(..., description="页码")
    pageSize: int = Field(..., description="每页数量")

    task_type: str | None = Field(None, description="任务类型") # TEXT PICTURE FILE 不传表示所有类型
    target_lang: str | None = Field(None, description="语言") # en zh ja ko 不传表示所有语言

    start_date: str = Field(..., description="开始日期")
    end_date: str = Field(..., description="结束日期")
    status: str | None = Field(None, description="状态")

class B(BaseModel):
    start_date: str | None = Field(None, description="开始日期")
    end_date: str | None = Field(None, description="结束日期")
    status: str | None = Field(None, description="状态")

class C(BaseModel):
    start_date: str = Field(..., description="开始日期")
    end_date: str = Field(..., description="结束日期")

@router.post("/metric/date_range")
async def get_metric(request: A) -> JSONResponse:
    """
    输入：start_date, end_date
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

@router.post("metric/interface1")
async def get_interface1(request: C) -> JSONResponse:
    """
    输入：start_date, end_date
    输出：日期范围内的翻译任务概览
    """
    return JSONResponse(content=metrics.interface1(
        start_date=request.start_date,
        end_date=request.end_date,
    ))


@router.post("metric/interface2")
async def get_interface2(request: C) -> JSONResponse:
    """
    输入：start_date, end_date
    输出：日期范围内的翻译任务概览
    """
    return JSONResponse(content=metrics.interface2(
        start_date=request.start_date,
        end_date=request.end_date,
    ))