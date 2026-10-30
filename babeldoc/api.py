import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from schemas.api.po import PoInputRequest, ZDataPayload, ZDataResponse, PoOutputResponse, PoResponseFlag, PoReturnRequest
from schemas.api.po import PoInputRequestDescription, PoReturnRequestDescription, PoOutputResponseDescription
from schemas.api.po_execptions import PoApiException
from app_devs import logger, config
from services.workloop_service import worker_loop
from babeldoc.routers.po_router import router as po_router
from babeldoc.routers.queue_router import router as queue_router



app = FastAPI(title="数科调度翻译服务")
app.include_router(po_router)
app.include_router(queue_router)



@app.on_event("startup")
async def on_startup() -> None:
    """应用启动时后台启动 Worker"""
    asyncio.create_task(worker_loop())


@app.exception_handler(PoApiException)
async def po_exception_handler(
    request: Request,
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

    # 优先从异常携带的原始请求对象取 BSKEY/SAPKEY，取不到则回退到 config
    if exc.request is not None:
        bskey = exc.request.IS_INPUT.BSKEY
        sapkey = exc.request.IS_INPUT.SAPKEY
    else:
        bskey = ""
        sapkey = ""

    po_response = PoOutputResponseDescription(
        ES_OUTPUT=PoOutputResponse(
            BSKEY=bskey,
            SAPKEY=sapkey,
            ZTYPE="E",
            ZMESSAGE="",
            ZDATA=zdata_response,
        )
    )

    return JSONResponse(content=jsonable_encoder(po_response))

@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    # 全局异常处理

    logger.error(f"系统全局异常捕获: {exc}")

    return JSONResponse(content=jsonable_encoder(PoOutputResponseDescription(
        ES_OUTPUT=PoOutputResponse(
            BSKEY="",
            SAPKEY="",
            ZTYPE="E",
            ZMESSAGE="",
            ZDATA=ZDataResponse(JOBID="", CODE="E_SYS_999", MESSAGE=str(exc)),
        )
    )))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=38001)