"""Kratos Multi-Engine Database Abstraction & Auto-Discovery."""

import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple


class DatabaseEngine:
    def __init__(self, engine_id: str, db_path: Path):
        self.engine_id = engine_id
        self.db_path = db_path
        self._schema_cache: Dict[str, List[str]] | None = None

    def get_tables(self) -> List[str]:
        if self._schema_cache is None:
            self.introspect()
        return list(self._schema_cache.keys())

    def introspect(self) -> Dict[str, List[str]]:
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [r[0] for r in cursor.fetchall()]

        schema = {}
        for t in tables:
            cursor.execute(f"PRAGMA table_info('{t}');")
            schema[t] = [r[1] for r in cursor.fetchall()]

        conn.close()
        self._schema_cache = schema
        return schema

    def execute_readonly(self, sql: str, max_rows: int = 500) -> Tuple[List[str], List[Dict[str, Any]], float, bool]:
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        start = time.perf_counter()
        cursor.execute(sql)
        raw_rows = cursor.fetchmany(max_rows + 1)
        duration_ms = (time.perf_counter() - start) * 1000.0

        truncated = len(raw_rows) > max_rows
        rows_to_keep = raw_rows[:max_rows]

        cols = [d[0] for d in cursor.description] if cursor.description else []
        rows = [dict(r) for r in rows_to_keep]

        conn.close()
        return cols, rows, duration_ms, truncated


class EngineRegistry:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.engines: Dict[str, DatabaseEngine] = {}
        self.active_engine_id: str = "northwind"
        self.discover()

    def discover(self):
        if not self.data_dir.exists():
            return
        for db_file in self.data_dir.glob("*.db"):
            engine_id = db_file.stem.lower()
            if engine_id not in self.engines:
                self.engines[engine_id] = DatabaseEngine(engine_id, db_file)

    def get_active(self) -> DatabaseEngine:
        if self.active_engine_id not in self.engines:
            self.discover()
        if self.active_engine_id not in self.engines:
            raise ValueError(f"Active engine '{self.active_engine_id}' not found.")
        return self.engines[self.active_engine_id]

    def set_active(self, engine_id: str):
        if engine_id not in self.engines:
            self.discover()
        if engine_id not in self.engines:
            raise ValueError(f"Engine '{engine_id}' is not registered.")
        self.active_engine_id = engine_id
