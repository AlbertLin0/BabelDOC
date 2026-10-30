import asyncio
import logging

from config.config import get_config
from schedule.schedule import Schedule

logger = logging.getLogger("数科调度翻译服务")
logging.basicConfig(level=logging.INFO)

config = get_config()
schedule = Schedule.get_instance()

# 并发控制：同一时刻最多同时处理的翻译任务数
CONCURRENCY_LIMIT = getattr(config, "concurrency_limit", 5)
semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
