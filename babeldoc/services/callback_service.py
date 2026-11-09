import httpx
from fastapi.encoders import jsonable_encoder
from app_devs import config, logger
import json
async def notify_callback(callback_url: str, task_id: str, result: dict) -> None:
    """翻译完成后，将结果推送到回调地址"""
    try:
        payload = jsonable_encoder(result)
        async with httpx.AsyncClient(timeout=config.callback_timeout, verify=False) as client:
            logger.info(f"回调已经发送")
            logger.info(f"回调通知已发送 task_id={task_id}")
            logger.info(
                f"[回调请求] task_id={task_id}"
                f" | url={callback_url}"
                f" | payload={json.dumps(payload, ensure_ascii=False)}"
            )
            # header = {
            #     "USERNAME": config.callback_USERNAME, 
            #     "PASSWORD": config.callback_PASSWORD
            # }
            resp = await client.post(
                callback_url, 
                json=payload, 
                auth=httpx.BasicAuth(
                    username=config.callback_USERNAME,
                    password=config.callback_PASSWORD
                ))
            logger.info(
                f"[回调响应] task_id={task_id}"
                f" | status={resp.status_code}"
                f" | body={resp.text}"
            )
            
    except Exception as e:
        logger.error(f"回调通知失败 task_id={task_id}, error={e}")
