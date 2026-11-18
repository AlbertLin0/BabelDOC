"""翻译指标统计服务 —— 轻量 SQLite 持久化"""
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

class MetricsService:
    """翻译指标统计（单例 + 线程安全）"""
    
    _instance: Optional["MetricsService"] = None
    _lock = threading.Lock()
    
    def __init__(self, db_path: str = "metrics.db"):
        self.db_path = Path(db_path)
        self._local = threading.local()
        self._init_db()
    
    @classmethod
    def get_instance(cls, db_path: str = "metrics.db") -> "MetricsService":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(db_path)
            return cls._instance
    
    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self.db_path))
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn
    
    def _init_db(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS translate_records (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id     TEXT    NOT NULL UNIQUE,
                job_id      TEXT,
                task_type   TEXT,           -- 'text' / 'picture' / 'file'
                target_lang TEXT,
                file_name   TEXT,
                status      TEXT    NOT NULL,  -- 'completed' / 'failed'
                duration_ms INTEGER,
                error_msg   TEXT,
                created_at  REAL    NOT NULL,   -- Unix timestamp
                started_at  REAL,
                completed_at REAL,
                created_date TEXT NOT NULL    -- 'YYYY-MM-DD' 便于按日期查询
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_date ON translate_records(created_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON translate_records(status)")
        conn.commit()
    
    # ---------- 写入 ----------
    def record_task(
        self,
        task_id: str,
        job_id: str,
        task_type: str,
        target_lang: str,
        status: str,
        created_at: float,
        file_name: Optional[str] = None,
        started_at: Optional[float] = None,
        completed_at: Optional[float] = None,
        error_msg: Optional[str] = None,
    ):
        duration_ms = None
        if started_at and completed_at:
            duration_ms = int((completed_at - started_at) * 1000)
        
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO translate_records
               (task_id, job_id, task_type, target_lang, file_name, status, duration_ms,
                error_msg, created_at, started_at, completed_at, created_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (task_id, job_id, task_type, target_lang, file_name, status, duration_ms,
             error_msg, created_at, started_at, completed_at,
             datetime.fromtimestamp(created_at).strftime("%Y-%m-%d")),
        )
        conn.commit()
    
    # ---------- 查询 ----------
    def count_by_date_range(
        self,
        start_date: str,       # '2026-11-01'
        end_date: str,         # '2026-11-30'
        status: Optional[str] = None,
    ) -> int:
        """统计日期范围内的翻译总次数"""
        sql = "SELECT COUNT(*) FROM translate_records WHERE created_date BETWEEN ? AND ?"
        params = [start_date, end_date]
        if status:
            sql += " AND status = ?"
            params.append(status)
        return self._get_conn().execute(sql, params).fetchone()[0]
    
    def count_all(
        self,
        target_lang: Optional[str] = None,
        task_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        status: Optional[str] = None,
    ) -> int:
        """统计翻译任务总数，可按语言/类型/日期/状态过滤"""
        sql = "SELECT COUNT(*) FROM translate_records WHERE 1=1"
        params: list = []
        if target_lang:
            sql += " AND target_lang = ?"
            params.append(target_lang)
        if task_type:
            sql += " AND task_type = ?"
            params.append(task_type)
        if start_date and end_date:
            sql += " AND created_date BETWEEN ? AND ?"
            params += [start_date, end_date]
        if status:
            sql += " AND status = ?"
            params.append(status)
        return self._get_conn().execute(sql, params).fetchone()[0]

    def group_by_target_lang(
        self,
        target_lang: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[dict]:
        """按目标语言分组统计翻译次数；传 target_lang 只返回指定语言的次数"""
        sql = (
            "SELECT target_lang, COUNT(*) AS cnt "
            "FROM translate_records WHERE 1=1"
        )
        params: list = []
        if target_lang:
            sql += " AND target_lang = ?"
            params.append(target_lang)
        if start_date and end_date:
            sql += " AND created_date BETWEEN ? AND ?"
            params += [start_date, end_date]
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " GROUP BY target_lang ORDER BY cnt DESC"
        return [dict(r) for r in self._get_conn().execute(sql, params).fetchall()]

    def group_by_task_type(
        self,
        task_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[dict]:
        """按任务类型（text/picture/file）分组统计翻译次数；传 task_type 只返回指定类型的次数"""
        sql = (
            "SELECT task_type, COUNT(*) AS cnt "
            "FROM translate_records WHERE 1=1"
        )
        params: list = []
        if task_type:
            sql += " AND task_type = ?"
            params.append(task_type)
        if start_date and end_date:
            sql += " AND created_date BETWEEN ? AND ?"
            params += [start_date, end_date]
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " GROUP BY task_type ORDER BY cnt DESC"
        return [dict(r) for r in self._get_conn().execute(sql, params).fetchall()]