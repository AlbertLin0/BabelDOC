from dotenv import load_dotenv
load_dotenv()

import asyncio
import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from babeldoc.schemas.api.po import ZDataResponse, PoOutputResponse, PoOutputResponseDescription
from babeldoc.schemas.api.po_execptions import PoApiException, PoValidationError
from babeldoc.app_devs import logger, config
from babeldoc.services.workloop_service import worker_loop
from babeldoc.routers.po_router import router as po_router
from babeldoc.routers.queue_router import router as queue_router
from babeldoc.utils.rsa import encrypt_data
from babeldoc.config.config import random_str_generate
from typing import Optional, Any


app = FastAPI(title="数科调度翻译服务")
app.include_router(po_router)
app.include_router(queue_router)

@app.on_event("startup")
async def on_startup() -> None:
    """应用启动时后台启动 Worker"""
    asyncio.create_task(worker_loop())


def safe_random_str() -> str:
    """
    安全生成随机字符串。
    如果随机字符串生成失败，则返回空字符串，避免异常处理器二次异常。
    """
    try:
        return random_str_generate()
    except Exception:
        logger.exception("随机字符串生成失败")
        return "1234567890"


def build_fallback_response(
    bskey: str = "",
    sapkey: str = "",
    message: str = "服务器异常处理器内部错误",
) -> dict[str, Any]:
    """
    """
    return {
        "ES_OUTPUT": {
            "BSKEY": bskey,
            "SAPKEY": sapkey,
            "ZTYPE": "E",
            "ZMESSAGE": message,
            "ZDATA": "",
        }
    }

@app.middleware("http")
async def capture_po_request_info(request: Request, call_next):

    request.state.ifywid = None
    request.state.bskey = None
    request.state.sapkey = None

    if request.url.path.startswith("/po"):
        try:
            body = await request.body()
            data = json.loads(body)

            is_input = data.get("IS_INPUT")

            if not isinstance(is_input, dict):
                return JSONResponse(
                    status_code=400,
                    content={"detail": "IS_INPUT 参数缺失或格式错误"}
                )

            # 提取并校验必要字段
            required_fields = ["IFYWID", "BSKEY", "SAPKEY"]

            missing_fields = [
                field for field in required_fields
                if not isinstance(is_input.get(field), str)
                or not is_input.get(field)
            ]

            if missing_fields:
                return JSONResponse(
                    status_code=400,
                    content={
                        "detail": f"必要参数缺失或为空: {', '.join(missing_fields)}"
                    }
                )

            request.state.ifywid = is_input["IFYWID"]
            request.state.bskey = is_input["BSKEY"]
            request.state.sapkey = is_input["SAPKEY"]

        except json.JSONDecodeError as e:
            raise PoValidationError(message="请求体不是合法的 JSON 格式") from e

        except Exception as e:
            logger.exception("PO 请求参数预处理失败")
            raise e

    return await call_next(request)

@app.exception_handler(PoApiException)
async def po_exception_handler(
    request: Request,
    exc: PoApiException,
) -> JSONResponse:
    """
    PO 接口业务异常处理器。
    """

    logger.warning(
        "PO 接口异常捕获 | path=%s | code=%s | message=%s | job_id=%s",
        request.url.path,
        exc.code,
        exc.message,
        exc.job_id,
    )

    try:
        # 构造业务异常数据
        zdata_response = ZDataResponse(
            JOBID=exc.job_id or "",
            CODE=exc.code.value,
            MESSAGE=exc.message,
        )
        encrypted_data = encrypt_data(zdata_response, request.state.sysid)
        po_response = PoOutputResponseDescription(
            ES_OUTPUT=PoOutputResponse(
                BSKEY=request.state.bskey,
                SAPKEY=request.state.sapkey,
                ZTYPE="E",
                ZMESSAGE="PO接口异常",
                ZDATA=encrypted_data,
            )
        )

        return JSONResponse(
            status_code=500,
            content=jsonable_encoder(po_response)
        )

    except Exception:
        # PO 异常响应构造或加密失败
        logger.exception(
            "PO 接口异常响应构造失败或加密失败 | path=%s | job_id=%s",
            request.url.path,
            exc.job_id,
        )
        return JSONResponse(
            status_code=500,
            content=build_fallback_response(
                bskey=request.state.bskey,
                sapkey=request.state.sapkey,
            )
        )

@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """
    全局未预期异常处理器。
    """
    logger.error(
        "系统全局异常捕获 | path=%s | method=%s",
        request.url.path,
        request.method,
        exc_info=(type(exc), exc, exc.__traceback__),
    )

    bskey = safe_random_str()
    sapkey = safe_random_str()

    try:
        zdata_response = ZDataResponse(
            JOBID="",
            CODE="E_SYS_999",
            MESSAGE="服务器内部错误",
        )
        encrypted_data = encrypt_data(zdata_response, request.state.sysid)
        po_response = PoOutputResponseDescription(
            ES_OUTPUT=PoOutputResponse(
                BSKEY=request.state.bskey,
                SAPKEY=request.state.sapkey,
                ZTYPE="E",
                ZMESSAGE="服务器内部错误",
                ZDATA=encrypted_data,
            )
        )

        return JSONResponse(
            status_code=500,
            content=jsonable_encoder(po_response)
        )

    except Exception:
        # 异常处理器自身发生异常
        logger.exception(
            "全局异常响应构造或加密失败 | path=%s",
            request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content=build_fallback_response(
                bskey=bskey,
                sapkey=sapkey,
            )
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=38001)