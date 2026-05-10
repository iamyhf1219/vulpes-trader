"""SQLite 数据库 — 存储交易记录、复盘数据、权益曲线"""

import sqlite3
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, List, Any, Iterator
from datetime import datetime, timezone

DB_DIR = Path(__file__).parent.parent.parent / "data"


class AuditDB:
    """轻量级 SQLite 数据库封装"""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            DB_DIR.mkdir(exist_ok=True)
            db_path = DB_DIR / "vulpes.db"
        self.db_path = db_path
        self.initialized = False
        self._init_db()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        """上下文管理器：自动关闭连接"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        """初始化建表"""
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    quantity REAL NOT NULL,
                    leverage INTEGER NOT NULL,
                    pnl REAL,
                    entry_time TIMESTAMP NOT NULL,
                    exit_time TIMESTAMP,
                    stop_loss REAL,
                    take_profit REAL,
                    exit_reason TEXT,
                    strategy TEXT,
                    signal_snapshot TEXT
                );

                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP NOT NULL,
                    symbol TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    confidence REAL,
                    indicators TEXT,
                    executed BOOLEAN DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS equity_curve (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP NOT NULL,
                    equity REAL NOT NULL,
                    unrealized_pnl REAL,
                    margin_used REAL
                );

                CREATE TABLE IF NOT EXISTS trade_reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id INTEGER REFERENCES trades(id),
                    overall_grade TEXT,
                    win_loss_category TEXT,
                    root_cause TEXT,
                    lessons_learned TEXT,
                    parameter_adjustments TEXT
                );

                CREATE TABLE IF NOT EXISTS parameter_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP NOT NULL,
                    parameter_name TEXT NOT NULL,
                    old_value REAL,
                    new_value REAL,
                    reason TEXT,
                    trade_id INTEGER
                );
            """)
        self.initialized = True

    def query(self, sql: str, params: tuple = ()) -> List[Any]:
        """执行 SQL 查询，返回所有结果行"""
        with self._conn() as conn:
            return conn.execute(sql, params).fetchall()

    def execute(self, sql: str, params: tuple = ()) -> int:
        """执行 INSERT/UPDATE/DELETE，返回影响行数"""
        with self._conn() as conn:
            cur = conn.execute(sql, params)
            return cur.rowcount

    def save_trade(self, trade_data: dict) -> int:
        """保存交易记录，返回 ID"""
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO trades 
                (symbol, side, entry_price, quantity, leverage, 
                 stop_loss, take_profit, strategy, signal_snapshot, entry_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    trade_data["symbol"],
                    trade_data["side"],
                    trade_data["entry_price"],
                    trade_data["quantity"],
                    trade_data["leverage"],
                    trade_data.get("stop_loss"),
                    trade_data.get("take_profit"),
                    trade_data.get("strategy"),
                    json.dumps(trade_data.get("signal_snapshot", {})),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            return cur.lastrowid

    def close_trade(self, trade_id: int, exit_price: float, pnl: float,
                    exit_reason: str) -> bool:
        """平仓更新，返回是否找到并更新了该交易"""
        with self._conn() as conn:
            cur = conn.execute(
                """UPDATE trades SET exit_price=?, pnl=?, exit_time=?,
                   exit_reason=? WHERE id=?""",
                (exit_price, pnl, datetime.now(timezone.utc).isoformat(),
                 exit_reason, trade_id),
            )
            return cur.rowcount > 0
