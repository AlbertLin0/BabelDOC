import asyncio
from fastapi.encoders import jsonable_encoder
from schedule.schedule import Task
from app_devs import schedule, config, semaphore, logger
from services.translation_service import process_translation
from services.callback_service import notify_callback

async def _handle_task(task: Task) -> None:
    """后台协程：处理单个翻译任务的完整生命周期（完成 / 失败 / 回调）"""
    try:
        logger.info(f"开始处理任务: task_id={task.task_id}, job_id={task.job_id}")
        result = await process_translation(task.request)
        await schedule.complete(task.task_id, jsonable_encoder(result))
        logger.info(f"任务处理完成: task_id={task.task_id}")
        if config.callback_url:
            await notify_callback(config.callback_url, task.task_id, jsonable_encoder(result))
    except asyncio.CancelledError:
        logger.info(f"任务被取消: task_id={task.task_id}")
        await schedule.fail(task.task_id, "任务已取消")
        if config.callback_url:
            await notify_callback(
                config.callback_url,
                task.task_id,
                {"error": "任务已取消", "task_id": task.task_id},
            )
    except Exception as e:
        logger.error(f"任务处理失败: task_id={task.task_id}, error={e}")
        await schedule.fail(task.task_id, str(e))
    finally:
        semaphore.release()

async def worker_loop() -> None:
    """后台 Worker：不断从队列头部取任务并并发执行翻译"""
    logger.info(f"翻译任务 Worker 已启动，最大并发数: {semaphore._value}")
    while True:
        task = await schedule.get_next()
        if task is None:
            await asyncio.sleep(0.2)
            continue
        await semaphore.acquire()
        asyncio_task = asyncio.create_task(_handle_task(task))
        task._asyncio_task = asyncio_task
