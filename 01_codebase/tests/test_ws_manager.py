import pytest
from vulpes_trader.data.ws_manager import WSManager
from vulpes_trader.utils.retry import async_retry


def test_ws_manager_init():
    """测试 WSManager 初始化"""
    mgr = WSManager(symbols=["BTC/USDT:USDT"], timeframes=["1m", "5m"])
    assert mgr.symbols == ["BTC/USDT:USDT"]
    assert mgr.timeframes == ["1m", "5m"]
    assert not mgr._running


def test_ws_manager_defaults():
    """测试默认参数"""
    mgr = WSManager(symbols=[], timeframes=[])
    assert mgr.exchange is None
    assert len(mgr._ticker_handlers) == 0
    assert len(mgr._ohlcv_handlers) == 0


@pytest.mark.asyncio
async def test_async_retry_no_retry_needed():
    """测试无需重试的场景"""

    async def success_func():
        return "ok"

    result = await async_retry(success_func, max_retries=3)
    assert result == "ok"
