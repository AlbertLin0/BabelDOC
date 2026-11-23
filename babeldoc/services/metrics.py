"""翻译指标统计服务 —— 轻量 SQLite 持久化"""
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Optional

from openpyxl import Workbook

from babeldoc.app_devs import logger
from babeldoc.utils.util import LangMapping

class MetricsService:
    """翻译指标统计（单例 + 线程安全）"""
    
    _instance: Optional["MetricsService"] = None
    _lock = threading.Lock()
    
    def __init__(self, db_path: str = "metrics.db"):
        self.db_path = Path(db_path)
        self._local = threading.local()
        logger.info(f"MetricsService initialized with db_path: {self.db_path}")
        self._init_db()
    
    @classmethod
    def get_instance(cls, db_path: str = "metrics.db") -> "MetricsService":
        with cls._lock:
            if cls._instance is None:
                logger.info(f"MetricsService instance created with db_path: {db_path}")
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
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (task_id, job_id, task_type, target_lang, file_name, status, duration_ms,
             error_msg, created_at, started_at, completed_at,
             datetime.fromtimestamp(created_at).strftime("%Y-%m-%d")),
        )
        conn.commit()
    
    # ---------- 查询 ----------
    def list_by_date_range(
        self,
        pageNo: int,
        pageSize: int,
        start_date: str,
        end_date: str,
        task_type: Optional[str] = None,
        language: Optional[str] = None,
        status: Optional[str] = None,
    ) -> dict:
        """分页返回日期范围内的翻译记录，支持按 type/语言/状态过滤"""
        where_clauses: list[str] = ["created_date BETWEEN ? AND ?"]
        params: list = [start_date, end_date]
        if task_type:
            where_clauses.append("task_type = ?")
            params.append(task_type)
        if language:
            where_clauses.append("target_lang = ?")
            params.append(language)
        if status:
            where_clauses.append("status = ?")
            params.append(status)
        where_sql = "WHERE " + " AND ".join(where_clauses)

        conn = self._get_conn()
        total = conn.execute(
            f"SELECT COUNT(*) FROM translate_records {where_sql}", params
        ).fetchone()[0]

        offset = (pageNo - 1) * pageSize
        records = [
            dict(r) for r in conn.execute(
                f"SELECT * FROM translate_records {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                params + [pageSize, offset],
            ).fetchall()
        ]
        return {"pageNo": pageNo, "pageSize": pageSize, "list": records}

    # 导出表头
    EXCEL_HEADERS = [
        "task_id", "job_id", "task_type", "target_lang", "file_name", "status",
        "duration_ms", "error_msg", "created_at", "started_at", "completed_at",
    ]

    def export_to_excel(
        self,
        start_date: str,
        end_date: str,
        task_type: Optional[str] = None,
        language: Optional[str] = None,
        status: Optional[str] = None,
    ) -> bytes:
        """导出日期范围内的翻译记录为 xlsx 文件（全量，不分页），返回 bytes"""
        where_clauses: list[str] = ["created_date BETWEEN ? AND ?"]
        params: list = [start_date, end_date]
        if task_type:
            where_clauses.append("task_type = ?")
            params.append(task_type)
        if language:
            where_clauses.append("target_lang = ?")
            params.append(language)
        if status:
            where_clauses.append("status = ?")
            params.append(status)
        where_sql = "WHERE " + " AND ".join(where_clauses)

        rows = self._get_conn().execute(
            f"SELECT * FROM translate_records {where_sql} ORDER BY created_at DESC",
            params,
        ).fetchall()

        wb = Workbook()
        ws = wb.active
        ws.title = "translate_records"
        ws.append(self.EXCEL_HEADERS)
        for row in rows:
            ws.append([row[h] for h in self.EXCEL_HEADERS])

        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf.getvalue()
    
    def count_all(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        status: Optional[str] = None,
    ) -> dict:
        """一次返回：总次数 + 各 type + 平均时长 + 各语言次数（全量对齐 LangMapping）+ 每日次数"""
        where_clauses: list[str] = []
        params: list = []
        if start_date and end_date:
            where_clauses.append("created_date BETWEEN ? AND ?")
            params += [start_date, end_date]
        if status:
            where_clauses.append("status = ?")
            params.append(status)
        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        conn = self._get_conn()

        # 1. 总次数
        total = conn.execute(
            f"SELECT COUNT(*) FROM translate_records {where_sql}", params
        ).fetchone()[0]

        # 2. 各 type 次数 (task_type: 'text'/'file'/'picture')
        type_rows = conn.execute(
            f"SELECT UPPER(task_type) AS k, COUNT(*) AS cnt FROM translate_records {where_sql} GROUP BY task_type",
            params,
        ).fetchall()
        type_map = {r["k"]: r["cnt"] for r in type_rows}
        text_cnt = type_map.get("TEXT", 0)
        file_cnt = type_map.get("FILE", 0)
        picture_cnt = type_map.get("PICTURE", 0)

        # 3. 平均时长 (只统计有 duration_ms 的)
        avg_row = conn.execute(
            f"SELECT AVG(duration_ms) AS avg_ms FROM translate_records {where_sql} AND duration_ms IS NOT NULL",
            params,
        ).fetchone()
        avg_duration = int(avg_row["avg_ms"]) if avg_row["avg_ms"] is not None else 0

        # 4. 各语言次数 —— 对齐 LangMapping.MAP 全量语言，没数据补 0
        lang_rows = conn.execute(
            f"SELECT target_lang, COUNT(*) AS cnt FROM translate_records {where_sql} GROUP BY target_lang",
            params,
        ).fetchall()
        lang_map = {r["target_lang"]: r["cnt"] for r in lang_rows}
        lang_children = [
            {"key": code, "value": lang_map.get(code, 0)}
            for code in LangMapping.MAP
        ]

        # 5. 每日次数
        daily_rows = conn.execute(
            f"SELECT created_date AS k, COUNT(*) AS cnt FROM translate_records {where_sql} GROUP BY created_date ORDER BY k",
            params,
        ).fetchall()
        daily_children = [{"key": r["k"], "value": r["cnt"]} for r in daily_rows]

        return {
            "list": [
                {"key": "total", "value": total},
                {"key": "dynamic", "value": text_cnt},
                {"key": "attachment", "value": file_cnt},
                {"key": "screenshot", "value": picture_cnt},
                {"key": "avgDuration", "value": avg_duration},
                {"key": "language", "value": total, "children": lang_children},
                {"key": "daily", "value": total, "children": daily_children},
            ]
        }

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

    def interface2(
        self,
        start_date: str,
        end_date: str,
    ) -> dict:
        """概览：总次数 + 成功/失败占比(%) + 平均耗时(ms)"""
        params: list = [start_date, end_date]
        where_sql = "WHERE created_date BETWEEN ? AND ?"

        conn = self._get_conn()

        total = conn.execute(
            f"SELECT COUNT(*) FROM translate_records {where_sql}", params
        ).fetchone()[0]

        completed = conn.execute(
            f"SELECT COUNT(*) FROM translate_records {where_sql} AND status = 'completed'",
            params,
        ).fetchone()[0]

        failed = conn.execute(
            f"SELECT COUNT(*) FROM translate_records {where_sql} AND status = 'failed'",
            params,
        ).fetchone()[0]

        avg_row = conn.execute(
            f"SELECT AVG(duration_ms) AS avg_ms FROM translate_records {where_sql} AND duration_ms IS NOT NULL",
            params,
        ).fetchone()
        avg_duration = int(avg_row["avg_ms"]) if avg_row["avg_ms"] is not None else 0

        completed_rate = round(completed / total * 100, 1) if total > 0 else 0.0
        failed_rate = round(failed / total * 100, 1) if total > 0 else 0.0

        return {
            "total": total,
            "completed_rate": completed_rate,
            "failed_rate": failed_rate,
            "avg_duration": avg_duration,
        }

    def interface1(self) -> dict:
        """返回最近 14 天每日翻译次数，补全缺失日期：{date: [...], count: [...]}"""
        today = datetime.now().date()
        start = today - timedelta(days=13)
        date_list = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(14)]
        rows = self._get_conn().execute(
            "SELECT created_date, COUNT(*) AS cnt FROM translate_records "
            "WHERE created_date BETWEEN ? AND ? GROUP BY created_date",
            [date_list[0], date_list[-1]],
        ).fetchall()
        cnt_map = {r["created_date"]: r["cnt"] for r in rows}
        return {
            "date": date_list,
            "count": [cnt_map.get(d, 0) for d in date_list],
        }

    def interface3(self, start_date: str, end_date: str) -> dict:
        rows = self._get_conn().execute(
            "SELECT target_lang, COUNT(*) AS cnt FROM translate_records "
            "WHERE created_date BETWEEN ? AND ? GROUP BY target_lang",
            [start_date, end_date],
        ).fetchall()
        lang_map = {r["target_lang"]: r["cnt"] for r in rows}
        languages = [
            {"name": LangMapping.MAP[code], "value": lang_map.get(code, 0)}
            for code in LangMapping.MAP
        ]
        return {
            "name": [r["name"] for r in languages],
            "count": [r["value"] for r in languages],
            }