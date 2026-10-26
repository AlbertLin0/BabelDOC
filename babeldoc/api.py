import asyncio
import json
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from schemas.api.po import PoInputRequest, ZDataPayload, ZDataResponse, PoOutputResponse, PoResponseFlag
from schemas.api.po_execptions import PoApiException, PoValidationError, PoBusinessError, PoErrorCode
from schedule.schedule import Schedule, TaskStatus, Task

import logging
logger = logging.getLogger("数科调度翻译服务")
logging.basicConfig(level=logging.INFO)

from config.config import get_config
config = get_config()

# 调度器单例
schedule = Schedule.get_instance()


async def process_translation(request: PoInputRequest) -> PoInputRequest:
    """翻译任务处理逻辑（占位实现，后续接入真实翻译流程）"""
    zdata = ZDataPayload.model_validate(request.ZDATA)
    # 翻译接口路由
    if zdata.TEXT is not None:
        # 文本翻译
        translated_text = zdata.TEXT  # TODO: 接入真实文本翻译
        response = ZDataPayload(
            JOBID=zdata.JOBID,
            CODE=PoResponseFlag.S.value,
            MESSAGE=zdata.MESSAGE,
            TEXT=translated_text,
            PICTURE=zdata.PICTURE,
            FILE_ID=zdata.FILE_ID,
            FILE_NAME=zdata.FILE_NAME,
            FILE_ARCID=zdata.FILE_ARCID,
            FILE_DOCID=zdata.FILE_DOCID,
            ZEXTRA1=zdata.ZEXTRA1,
            ZEXTRA2=zdata.ZEXTRA2,
            ZEXTRA3=zdata.ZEXTRA3,
            ZEXTRA4=zdata.ZEXTRA4,
            ZEXTRA5=zdata.ZEXTRA5,
        )
    elif zdata.PICTURE is not None:
        # 图片翻译
        new_FILE_ID = "FI23456"
        new_FILE_NAME = f"{zdata.FILE_NAME}_translated.png"
        new_FILE_ARCID = zdata.FILE_ARCID
        new_FILE_DOCID = zdata.FILE_DOCID

        response = ZDataPayload(
            JOBID=zdata.JOBID,
            CODE=PoResponseFlag.S.value,
            MESSAGE=zdata.MESSAGE,
            TEXT=zdata.TEXT,
            PICTURE=zdata.PICTURE,
            FILE_ID=new_FILE_ID,
            FILE_NAME=new_FILE_NAME,
            FILE_ARCID=new_FILE_ARCID,
            FILE_DOCID=new_FILE_DOCID,
            ZEXTRA1=zdata.ZEXTRA1,
            ZEXTRA2=zdata.ZEXTRA2,
            ZEXTRA3=zdata.ZEXTRA3,
            ZEXTRA4=zdata.ZEXTRA4,
            ZEXTRA5=zdata.ZEXTRA5,
        )
    elif zdata.FILE_ID is not None:
        # 文件翻译
        new_FILE_ID = "FI23456"
        new_FILE_NAME = f"{zdata.FILE_NAME}_translated.png"
        new_FILE_ARCID = zdata.FILE_ARCID
        new_FILE_DOCID = zdata.FILE_DOCID

        response = ZDataPayload(
            JOBID=zdata.JOBID,
            CODE=PoResponseFlag.S.value,
            MESSAGE=zdata.MESSAGE,
            TEXT=zdata.TEXT,
            PICTURE=zdata.PICTURE,
            FILE_ID=new_FILE_ID,
            FILE_NAME=new_FILE_NAME,
            FILE_ARCID=new_FILE_ARCID,
            FILE_DOCID=new_FILE_DOCID,
            ZEXTRA1=zdata.ZEXTRA1,
            ZEXTRA2=zdata.ZEXTRA2,
            ZEXTRA3=zdata.ZEXTRA3,
            ZEXTRA4=zdata.ZEXTRA4,
            ZEXTRA5=zdata.ZEXTRA5,
        )
    else:
        raise PoValidationError(message="TEXT、PICTURE、FILE_ID 三者之一不能为空")

    return PoInputRequest(
        IS_INPUT=config.IS_INPUT,
        SYSID=config.SYSID,
        IFYWID=request.IFYWID,
        BSKEY=config.BSKEY,
        SAPKEY=config.SAPKEY,
        ZORG=config.ZORG,
        ZFILED1=request.ZFILED1,
        ZFILED2=request.ZFILED2,
        ZFILED3=request.ZFILED3,
        ZFILED4=request.ZFILED4,
        ZFILED5=request.ZFILED5,
        ZDATA=response,
    )

async def verify_IFYWID(IFYWID: str) -> str:
    """从任务中提取 IFYWID"""
    if IFYWID == "FI1301":
        res = "FI1300"
    elif IFYWID == "FI1299":
        res = "FI1298"
    elif IFYWID == "FI1297":
        res = "FI1296"
    else:
        raise PoValidationError(message=f"未知 IFYYWID: {IFYWID}")
    return res

async def notify_callback(callback_url: str, task_id: str, result: dict) -> None:
    """翻译完成后，将结果推送到回调地址"""
    try:
        payload = jsonable_encoder(result)
        async with httpx.AsyncClient(timeout=config.callback_timeout) as client:
            resp = await client.post(callback_url, json=payload)
            logger.info(f"回调通知已发送 task_id={task_id}, status={resp.status_code}")
    except Exception as e:
        logger.error(f"回调通知失败 task_id={task_id}, error={e}")


async def worker_loop() -> None:
    """后台 Worker：不断从队列头部取任务并执行翻译"""
    logger.info("翻译任务 Worker 已启动")
    while True:
        task = await schedule.get_next()
        if task is None:
            await asyncio.sleep(0.2)
            continue
        try:
            logger.info(f"开始处理任务: task_id={task.task_id}, job_id={task.job_id}")
            result = await process_translation(task.request)
            await schedule.complete(task.task_id, jsonable_encoder(result))
            logger.info(f"任务处理完成: task_id={task.task_id}")
            # 翻译完成后推送回调

            if config.callback_url:
                await notify_callback(
                    config.callback_url,
                    task.task_id,
                    jsonable_encoder(result),
                )
        except Exception as e:
            logger.error(f"任务处理失败: task_id={task.task_id}, error={e}")
            await schedule.fail(task.task_id, str(e))


app = FastAPI(title="数科调度翻译服务")


@app.on_event("startup")
async def on_startup() -> None:
    """应用启动时后台启动 Worker"""
    asyncio.create_task(worker_loop())

@app.exception_handler(PoApiException)
async def po_exception_handler(
    request: PoInputRequest, 
    exc: PoApiException
) -> JSONResponse:
    logger.error(f"PO 接口异常捕获: Code={exc.code}, Message={exc.message}, JobID={exc.job_id}")
    
    job_id = exc.job_id
    if not job_id:
        # if exception occurs before parsing JobID, use empty string as JobID
        job_id = ""

    zdata_response = ZDataResponse(
        JOBID=job_id, 
        CODE=exc.code.value,
        MESSAGE=exc.message
    )

    po_response = PoOutputResponse(
        ES_OUTPUT = config.ES_OUTPUT, 
        BSKEY = config.BSKEY,
        SAPKEY = config.SAPKEY,
        ZTYPE = "E",
        ZMESSAGE = "",
        ZDATA = zdata_response
    )

    # serialize po_response to JSON string. Need test this
    return JSONResponse(content=jsonable_encoder(po_response))

@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    # 全局异常处理

    logger.error(f"系统全局异常捕获: {exc}")

    return JSONResponse(content=jsonable_encoder(PoOutputResponse(
        ES_OUTPUT = config.ES_OUTPUT, 
        BSKEY = config.BSKEY,
        SAPKEY = config.SAPKEY,
        ZTYPE = "E",
        ZMESSAGE = "",
        ZDATA = ZDataResponse(JOBID="", CODE="E_SYS_999", MESSAGE=str(exc))
    )))



class MoveTaskRequest(BaseModel):
    position: int = Field(..., description="目标位置（0 为队首）")


@app.post("/po/translate")
async def get_translate_result(
    request: PoInputRequest
) -> JSONResponse:
    """提交翻译任务到队列，立即返回任务标识，完成后回调通知"""
    logger.debug("收到翻译请求: ")
    logger.debug(json.dumps(request.model_dump(), ensure_ascii=False))

    # 校验翻译类型字段（TEXT / PICTURE / FILE_ID 三选一）
    zdata = request.ZDATA
    if not (zdata.TEXT is not None or zdata.PICTURE is not None or zdata.FILE_ID is not None):
        raise PoValidationError(
            message="TEXT、PICTURE、FILE_ID 三者之一不能为空",
            job_id=zdata.JOBID,
        )
    # 校验 IFYWID
    response_IFYWID = await verify_IFYWID(request.IFYWID)
    request.IFYWID = response_IFYWID

    # 提交任务到队列
    task = await schedule.submit(request)
    logger.info(f"任务已入队: task_id={task.task_id}, job_id={task.job_id}")

    # 立即返回任务标识，不等待翻译完成
    response = ZDataResponse(
        JOBID=zdata.JOBID,
        CODE=PoErrorCode.SUCCESS.value,
        MESSAGE=f"任务已提交，task_id={task.task_id}",
    )
    return JSONResponse(
        PoOutputResponse(
            ES_OUTPUT=config.ES_OUTPUT,
            BSKEY=config.BSKEY,
            SAPKEY=config.SAPKEY,
            ZTYPE="S",
            ZMESSAGE="",
            ZDATA=response,
        )
    )


# ==================== 队列管理接口 ====================

@app.get("/po/queue")
async def get_queue_status() -> JSONResponse:
    """查看队列状态：等待中 + 处理中 + 最近完成的任务"""
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


@app.get("/po/queue/{task_id}")
async def get_task_detail(task_id: str) -> JSONResponse:
    """查询单个任务详情"""
    task = await schedule.get_task(task_id)
    if task is None:
        raise PoBusinessError(message=f"任务 {task_id} 不存在")
    return JSONResponse(content=task)


@app.post("/po/queue/{task_id}/move")
async def move_task(task_id: str, body: MoveTaskRequest) -> JSONResponse:
    """将任务移动到指定位置"""
    try:
        task = await schedule.move_to_position(task_id, body.position)
    except ValueError as e:
        raise PoBusinessError(message=str(e))
    return JSONResponse(content={
        "message": f"任务已移动到位置 {body.position}",
        "task_id": task.task_id,
        "job_id": task.job_id,
    })


@app.post("/po/queue/{task_id}/move_to_front")
async def move_task_to_front(task_id: str) -> JSONResponse:
    """将任务移动到队首（最高优先级）"""
    try:
        task = await schedule.move_to_front(task_id)
    except ValueError as e:
        raise PoBusinessError(message=str(e))
    return JSONResponse(content={
        "message": "任务已移动到队首",
        "task_id": task.task_id,
        "job_id": task.job_id,
    })


@app.post("/po/queue/{task_id}/move_to_back")
async def move_task_to_back(task_id: str) -> JSONResponse:
    """将任务移动到队尾"""
    try:
        task = await schedule.move_to_back(task_id)
    except ValueError as e:
        raise PoBusinessError(message=str(e))
    return JSONResponse(content={
        "message": "任务已移动到队尾",
        "task_id": task.task_id,
        "job_id": task.job_id,
    })


@app.delete("/po/queue/{task_id}")
async def remove_task(task_id: str) -> JSONResponse:
    """从队列中移除任务"""
    try:
        task = await schedule.remove(task_id)
    except ValueError as e:
        raise PoBusinessError(message=str(e))
    return JSONResponse(content={
        "message": "任务已从队列移除",
        "task_id": task.task_id,
        "job_id": task.job_id,
    })