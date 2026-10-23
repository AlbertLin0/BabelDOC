import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from schemas.api.po import PoInputRequest, ZDataPayload, ZDataResponse, PoOutputResponse
from schemas.api.po_execptions import PoApiException, PoValidationError, PoBusinessError, PoErrorCode
from schedule.schedule import Schedule

import logging
logger = logging.getLogger("数科调度翻译服务")
logging.basicConfig(level=logging.INFO)

from config.config import get_config
config = get_config()

# xxx


app = FastAPI(title="数科调度翻译服务")

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



@app.post("/po/translate")
async def get_translate_result(
    request: PoInputRequest
) -> JSONResponse:

    logger.debug("收到请求: ")
    logger.debug(json.dumps(request.model_dump(), ensure_ascii=False))

    try:
        pass


    except PoApiException as exc:
        logger.error(f"PO 接口字段验证失败: {exc}")
        raise
    except Exception as e:
        logger.error(f"PO 接口字段验证失败: {e}")
        raise PoBusinessError(message=str(e), job_id=request.ZDATA.JOBID)


    pass