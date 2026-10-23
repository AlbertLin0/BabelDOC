import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from schemas.api.po import PoInputRequest


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
    _event: asyncio.Event = field(default_factory=asyncio.Event, repr=False)

    @property
    def job_id(self) -> str:
        return self.request.ZDATA.JOBID

    @property
    def file_name(self) -> Optional[str]:
        return self.request.ZDATA.FILE_NAME

    async def wait(self, timeout: Optional[float] = None) -> bool:
        """等待任务处理完成"""
        try:
            await asyncio.wait_for(self._event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
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
        self._completed: Dict[str, Task] = {}
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> "Schedule":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def submit(self, request: PoInputRequest) -> Task:
        """提交任务到队列末尾"""
        async with self._lock:
            task = Task(task_id=str(uuid.uuid4()), request=request)
            self._pending.append(task)
            return task

    async def get_next(self) -> Optional[Task]:
        """获取队列头部任务并标记为处理中"""
        async with self._lock:
            if not self._pending:
                return None
            task = self._pending.pop(0)
            task.status = TaskStatus.PROCESSING
            task.started_at = time.time()
            self._processing[task.task_id] = task
            return task

    async def move_to_position(self, task_id: str, position: int) -> Task:
        """将任务移动到指定位置（0 为队首）"""
        async with self._lock:
            task = self._find_pending(task_id)
            self._pending.remove(task)
            position = max(0, min(position, len(self._pending)))
            self._pending.insert(position, task)
            return task

    async def move_to_front(self, task_id: str) -> Task:
        """将任务移动到队首"""
        return await self.move_to_position(task_id, 0)

    async def move_to_back(self, task_id: str) -> Task:
        """将任务移动到队尾"""
        async with self._lock:
            return await self.move_to_position(task_id, len(self._pending) - 1)

    async def remove(self, task_id: str) -> Task:
        """从等待队列中移除任务"""
        async with self._lock:
            task = self._find_pending(task_id)
            self._pending.remove(task)
            task._event.set()
            return task

    async def complete(self, task_id: str, result: Optional[Dict[str, Any]] = None) -> None:
        """标记任务为已完成"""
        async with self._lock:
            task = self._processing.pop(task_id, None)
            if task is None:
                return
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            task.result = result
            self._completed[task_id] = task
            task._event.set()

    async def fail(self, task_id: str, error: str) -> None:
        """标记任务为失败"""
        async with self._lock:
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

    async def get_pending_tasks(self) -> List[Dict[str, Any]]:
        """获取等待队列中的所有任务（含排队位置）"""
        async with self._lock:
            result = []
            for index, task in enumerate(self._pending):
                d = task.to_dict()
                d["position"] = index
                result.append(d)
            return result

    async def get_processing_tasks(self) -> List[Dict[str, Any]]:
        """获取正在处理中的任务"""
        async with self._lock:
            return [t.to_dict() for t in self._processing.values()]

    async def get_completed_tasks(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取最近完成的任务"""
        async with self._lock:
            tasks = sorted(
                self._completed.values(),
                key=lambda t: t.completed_at or 0,
                reverse=True,
            )
            return [t.to_dict() for t in tasks[:limit]]

    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取单个任务详情"""
        async with self._lock:
            for task in self._pending:
                if task.task_id == task_id:
                    return task.to_dict()
            if task_id in self._processing:
                return self._processing[task_id].to_dict()
            if task_id in self._completed:
                return self._completed[task_id].to_dict()
            return None