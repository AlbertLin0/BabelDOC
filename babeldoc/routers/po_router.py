import json
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from schemas.api.po import (
    PoInputRequestDescription,
    PoOutputResponseDescription,
    PoOutputResponse,
    ZDataResponse,
)
from schemas.api.po_execptions import PoValidationError, PoErrorCode
from app_devs import schedule, logger
from services.translation_service import verify_IFYWID

router = APIRouter()

class MoveTaskRequest(BaseModel):
    position: int = Field(..., description="目标位置（0 为队首）")

@router.post("/po/translate")
async def get_translate_result(request: PoInputRequestDescription) -> JSONResponse:
    """提交翻译任务到队列，立即返回任务标识，完成后回调通知"""
    logger.debug("收到翻译请求: ")
    logger.debug(json.dumps(request.model_dump(), ensure_ascii=False))

    zdata = request.IS_INPUT.ZDATA
    if not (zdata.TEXT is not None or zdata.PICTURE is not None or zdata.FILE_ID is not None):
        raise PoValidationError(
            message="TEXT、PICTURE、FILE_ID 三者之一不能为空",
            job_id=zdata.JOBID,
        )

    response_IFYWID = await verify_IFYWID(request.IS_INPUT.IFYWID)
    request.IS_INPUT.IFYWID = response_IFYWID

    if zdata.TEXT is not None:
        translated_text = zdata.TEXT
        response = ZDataResponse(
            JOBID=zdata.JOBID,
            CODE=PoErrorCode.SUCCESS.value,
            MESSAGE="直接返回翻译结果",
            TEXT=translated_text,
        )
    else:
        task = await schedule.submit(request.IS_INPUT)
        logger.info(f"任务已入队: task_id={task.task_id}, job_id={task.job_id}")
        response = ZDataResponse(
            JOBID=request.IS_INPUT.ZDATA.JOBID,
            CODE=PoErrorCode.SUCCESS.value,
            MESSAGE=f"任务已提交，task_id={task.task_id}",
        )

    return JSONResponse(
        content=jsonable_encoder(
            PoOutputResponseDescription(
                ES_OUTPUT=PoOutputResponse(
                    BSKEY=request.IS_INPUT.BSKEY,
                    SAPKEY=request.IS_INPUT.SAPKEY,
                    ZTYPE="S",
                    ZMESSAGE="",
                    ZDATA=response,
                )
            )
        )
    )
