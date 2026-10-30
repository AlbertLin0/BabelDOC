import httpx
from fastapi.encoders import jsonable_encoder
from app_devs import config, logger

async def notify_callback(callback_url: str, task_id: str, result: dict) -> None:
    """翻译完成后，将结果推送到回调地址"""
    try:
        payload = jsonable_encoder(result)
        async with httpx.AsyncClient(timeout=config.callback_timeout) as client:
            resp = await client.post(callback_url, json=payload)
            logger.info(f"回调通知已发送 task_id={task_id}, status={resp.status_code}")
    except Exception as e:
        logger.error(f"回调通知失败 task_id={task_id}, error={e}")
