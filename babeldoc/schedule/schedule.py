import asyncio
import time
import uuid
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from schemas.api.po import PoInputRequest

logger = logging.getLogger(__name__)

from config.config import get_config
config = get_config()


class TaskStatus(str, Enum):
    """任务状态"""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class Task:
    """翻译任务"""

    task_id: str
    request: PoInputRequest
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    cancelled: bool = False
    _event: asyncio.Event = field(default_factory=asyncio.Event, repr=False)
    _asyncio_task: Optional[asyncio.Task] = field(default=None, repr=False)

    def cancel(self) -> None:
        """标记任务为已取消，并尝试中断正在执行的 asyncio 任务"""
        self.cancelled = True
        if self._asyncio_task is not None and not self._asyncio_task.done():
            self._asyncio_task.cancel()

    @property
    def job_id(self) -> str:
        return self.request.ZDATA.JOBID

    @property
    def file_name(self) -> Optional[str]:
        return self.request.ZDATA.FILE_NAME

    async def wait(self, timeout: Optional[float] = None) -> bool:
        """等待任务处理完成"""
        try:
            await asyncio.wait_for(self._event.wait(), timeout=config.task_timeout)
            return True
        except asyncio.TimeoutError:
            # raise asyncio.TimeoutError
            return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "job_id": self.job_id,
            "file_name": self.file_name,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }


class Schedule:
    """翻译任务排队调度类（单例）"""

    _instance: Optional["Schedule"] = None

    def __init__(self) -> None:
        self._pending: List[Task] = []
        self._processing: Dict[str, Task] = {}
        # TODO: 定时清理任务
        self._completed: Dict[str, Task] = {}
        # 说明：在 asyncio 单线程模型下，以下所有方法都是微秒级内存操作，
        # 不存在并发竞争，因此不需要 asyncio.Lock 也不需要 async 修饰

    @classmethod
    def get_instance(cls) -> "Schedule":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def submit(self, request: PoInputRequest) -> Task:
        """提交任务到队列末尾（纯内存操作，同步即可）"""
        task = Task(task_id=str(uuid.uuid4()), request=request)
        self._pending.append(task)
        return task

    def get_next(self) -> Optional[Task]:
        """获取队列头部任务并标记为处理中（纯内存操作，同步即可）"""
        if not self._pending:
            return None
        task = self._pending.pop(0)
        task.status = TaskStatus.PROCESSING
        task.started_at = time.time()
        self._processing[task.task_id] = task
        return task

    def move_to_position(self, task_id: str, position: int) -> Task:
        """将任务移动到指定位置（0 为队首）"""
        task = self._find_pending(task_id)
        self._pending.remove(task)
        position = max(0, min(position, len(self._pending)))
        self._pending.insert(position, task)
        return task

    def move_to_front(self, task_id: str) -> Task:
        """将任务移动到队首"""
        return self.move_to_position(task_id, 0)

    def move_to_back(self, task_id: str) -> Task:
        """将任务移动到队尾"""
        return self.move_to_position(task_id, len(self._pending) - 1)

    def remove(self, task_id: str) -> Task:
        """从等待队列中移除任务"""
        task = self._find_pending(task_id)
        self._pending.remove(task)
        task._event.set()
        return task

    def cancel(self, task_id: str) -> Task:
        """取消任务：等待中的直接移除，执行中的尝试中断"""
        # 1. 等待队列中的任务：直接移除
        for i, task in enumerate(self._pending):
            if task.task_id == task_id:
                self._pending.pop(i)
                task.cancelled = True
                task.status = TaskStatus.FAILED
                task.error = "任务已取消"
                task._event.set()
                logger.info(f"已取消等待中的任务: task_id={task_id}")
                return task
        # 2. 正在执行的任务：设置标志并中断 asyncio 任务
        task = self._processing.get(task_id)
        if task is not None:
            task.cancel()
            logger.info(f"正在取消执行中的任务: task_id={task_id}")
            return task
        # 3. 已完成的任务
        if task_id in self._completed:
            raise ValueError(f"任务 {task_id} 已完成，无法取消")
        raise ValueError(f"任务 {task_id} 不存在")

    def complete(self, task_id: str, result: Optional[Dict[str, Any]] = None) -> None:
        """标记任务为已完成"""
        task = self._processing.pop(task_id, None)
        if task is None:
            return
        task.status = TaskStatus.COMPLETED
        task.completed_at = time.time()
        task.result = result
        self._completed[task_id] = task
        task._event.set()

    def fail(self, task_id: str, error: str) -> None:
        """标记任务为失败"""
        task = self._processing.pop(task_id, None)
        if task is None:
            return
        task.status = TaskStatus.FAILED
        task.completed_at = time.time()
        task.error = error
        self._completed[task_id] = task
        task._event.set()

    def _find_pending(self, task_id: str) -> Task:
        for task in self._pending:
            if task.task_id == task_id:
                return task
        raise ValueError(f"任务 {task_id} 不在等待队列中")

    def get_pending_tasks(self) -> List[Dict[str, Any]]:
        """获取等待队列中的所有任务（含排队位置）"""
        result = []
        for index, task in enumerate(self._pending):
            d = task.to_dict()
            d["position"] = index
            result.append(d)
        return result

    def get_processing_tasks(self) -> List[Dict[str, Any]]:
        """获取正在处理中的任务"""
        return [t.to_dict() for t in self._processing.values()]

    def get_completed_tasks(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取最近完成的任务"""
        tasks = sorted(
            self._completed.values(),
            key=lambda t: t.completed_at or 0,
            reverse=True,
        )
        return [t.to_dict() for t in tasks[:limit]]

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取单个任务详情"""
        for task in self._pending:
            if task.task_id == task_id:
                return task.to_dict()
        if task_id in self._processing:
            return self._processing[task_id].to_dict()
        if task_id in self._completed:
            return self._completed[task_id].to_dict()
        return None