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
        tables = db.query("SELECT name FROM sqlite_master WHERE type='table'")
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
        rows = db.query("SELECT * FROM trades WHERE id=?", (trade_id,))
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
        result = db.close_trade(trade_id, 2800.0, 100.0, "stop_loss")
        assert result is True  # 更新成功

        row = db.query("SELECT exit_price, pnl, exit_reason FROM trades WHERE id=?", (trade_id,))[0]
        assert row[0] == 2800.0
        assert row[1] == 100.0
        assert row[2] == "stop_loss"
        
        # 测试不存在的交易
        result = db.close_trade(999, 0, 0, "test")
        assert result is False


def test_execute_returns_rowcount():
    """测试 execute 返回影响行数"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = AuditDB(db_path=Path(tmpdir) / "test.db")
        rows = db.execute(
            "INSERT INTO trades(symbol,side,entry_price,quantity,leverage,entry_time) VALUES('BTC','long',50000,0.1,5,'2024-01-01')"
        )
        assert rows == 1


def test_query_returns_list():
    """测试 query 返回列表"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = AuditDB(db_path=Path(tmpdir) / "test.db")
        rows = db.query("SELECT name FROM sqlite_master WHERE type='table'")
        assert isinstance(rows, list)


def test_all_tables_exist():
    """测试所有5张表都已创建"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = AuditDB(db_path=Path(tmpdir) / "test.db")
        tables = db.query("SELECT name FROM sqlite_master WHERE type='table'")
        table_names = [t[0] for t in tables]
        assert "trades" in table_names
        assert "signals" in table_names
        assert "equity_curve" in table_names
        assert "trade_reviews" in table_names
        assert "parameter_history" in table_names
