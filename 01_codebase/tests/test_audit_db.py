import pytest
import tempfile
from pathlib import Path
from vulpes_trader.audit.db import AuditDB


def test_audit_db_init():
    """测试数据库初始化和建表"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = AuditDB(db_path=Path(tmpdir) / "test.db")
        assert db.initialized

        # 验证表存在
        tables = db.fetchall("SELECT name FROM sqlite_master WHERE type='table'")
        table_names = [t[0] for t in tables]
        assert "trades" in table_names
        assert "equity_curve" in table_names


def test_save_trade():
    """测试保存交易记录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = AuditDB(db_path=Path(tmpdir) / "test.db")
        trade_id = db.save_trade({
            "symbol": "BTC/USDT:USDT",
            "side": "long",
            "entry_price": 50000.0,
            "quantity": 0.1,
            "leverage": 5,
            "stop_loss": 48000.0,
            "take_profit": 52000.0,
            "strategy": "trend_following_v1",
        })
        assert trade_id > 0

        # 验证数据
        rows = db.fetchall("SELECT * FROM trades WHERE id=?", (trade_id,))
        assert len(rows) == 1
        assert rows[0][2] == "long"


def test_close_trade():
    """测试平仓更新"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = AuditDB(db_path=Path(tmpdir) / "test.db")
        trade_id = db.save_trade({
            "symbol": "ETH/USDT:USDT",
            "side": "short",
            "entry_price": 3000.0,
            "quantity": 0.5,
            "leverage": 3,
        })
        db.close_trade(trade_id, 2800.0, 100.0, "stop_loss")

        row = db.fetchall("SELECT exit_price, pnl, exit_reason FROM trades WHERE id=?", (trade_id,))[0]
        assert row[0] == 2800.0
        assert row[1] == 100.0
        assert row[2] == "stop_loss"
