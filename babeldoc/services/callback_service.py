import httpx
from fastapi.encoders import jsonable_encoder
from app_devs import config, logger
import json

async def notify_callback(callback_url: str, task_id: str, result: dict) -> None:
    """翻译完成后，将结果推送到回调地址"""
    try:
        payload = jsonable_encoder(result)
        # 日志：请求信息（请求体）
        logger.info(
            f"[回调请求] task_id={task_id} | url={callback_url} | payload={json.dumps(payload, ensure_ascii=False)}"
        )
        async with httpx.AsyncClient(timeout=config.callback_timeout, verify=False) as client:
            resp = await client.post(
                callback_url,
                json=payload,
                auth=httpx.BasicAuth(
                    username=config.callback_USERNAME,
                    password=config.callback_PASSWORD
                )
            )
            # 日志：响应信息
            logger.info(
                f"[回调响应] task_id={task_id} | status={resp.status_code} | body={resp.text}"
            )
            # 可选：非2xx判定，主动抛异常进入except
            resp.raise_for_status()

    except httpx.HTTPStatusError as e:
        logger.error(
            f"[回调HTTP错误] task_id={task_id} | url={callback_url} | status={e.response.status_code} | resp_body={e.response.text}"
        )
        raise
    except httpx.TransportError as e:
        logger.error(
            f"[回调网络异常] task_id={task_id} | url={callback_url} | payload={json.dumps(payload, ensure_ascii=False)} | error={str(e)}"
        )
        raise
    except Exception as e:
        logger.error(
            f"[回调未知异常] task_id={task_id} | url={callback_url} | payload={json.dumps(payload, ensure_ascii=False)} | error={str(e)}"
        )
        raise
