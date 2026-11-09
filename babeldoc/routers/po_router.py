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
    ZDataInput,
)
from babeldoc.utils.rsa import decrypt_data, encrypt_data
from schemas.api.po_execptions import PoValidationError, PoErrorCode
from app_devs import schedule, logger
from config.config import verify_IFYWID
from babeldoc.services.translation_service import manager

router = APIRouter()

class MoveTaskRequest(BaseModel):
    position: int = Field(..., description="目标位置（0 为队首）")

@router.post("/po/translate")
async def get_translate_result(request: PoInputRequestDescription) -> JSONResponse:
    """提交翻译任务到队列，立即返回任务标识，完成后回调通知"""
    logger.debug("收到翻译请求: ")
    logger.debug(json.dumps(request.model_dump(), ensure_ascii=False))

    zdata = ZDataInput(**decrypt_data(request.IS_INPUT.ZDATA, request.IS_INPUT.SYSID))
    if not (zdata.TEXT is not None or zdata.PICTURE is not None or zdata.FILE_ID is not None):
        raise PoValidationError(
            message="TEXT、PICTURE、FILE_ID 三者之一不能为空",
            job_id=zdata.JOBID,
            request=request,  # 携带原始请求对象，供异常处理器使用
        )

    response_IFYWID = verify_IFYWID(request.IS_INPUT.IFYWID)
    # request.IS_INPUT.IFYWID = response_IFYWID

    if zdata.TEXT is not None:
        logger.info("文本翻译：")
        translated_text = manager.translator.do_translate(zdata.TEXT)
        response = ZDataResponse(
            JOBID=zdata.JOBID,
            CODE=PoErrorCode.SUCCESS.value,
            MESSAGE="翻译成功",
            TEXT=translated_text,
        )
    else:
        logger.info(f"任务已入队: ")
        task = schedule.submit(request.IS_INPUT, response_IFYWID, zdata)
        logger.info(f"任务已入队: task_id={task.task_id}, job_id={task.job_id}")
        response = ZDataResponse(
            JOBID=zdata.JOBID,
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
                    ZDATA=encrypt_data(response, request.IS_INPUT.SYSID),
                )
            )
        )
    )