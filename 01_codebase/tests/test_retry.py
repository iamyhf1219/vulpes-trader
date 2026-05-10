import pytest
from vulpes_trader.utils.retry import async_retry


class MockFailingFunc:
    def __init__(self):
        self.attempts = 0

    async def call(self):
        self.attempts += 1
        if self.attempts < 3:
            raise ConnectionError("Temporary failure")
        return "success"


@pytest.mark.asyncio
async def test_async_retry_success():
    """测试指数退避重试最终成功"""
    obj = MockFailingFunc()
    result = await async_retry(obj.call, max_retries=3)
    assert result == "success"
    assert obj.attempts == 3


@pytest.mark.asyncio
async def test_async_retry_exhausted():
    """测试重试耗尽后抛出异常"""
    obj = MockFailingFunc()

    class AlwaysFail:
        def __init__(self):
            self.attempts = 0
        async def call(self):
            self.attempts += 1
            raise ConnectionError("Always fails")

    failer = AlwaysFail()
    with pytest.raises(ConnectionError):
        await async_retry(failer.call, max_retries=2, base_delay=0.01)
    assert failer.attempts == 3  # initial + 2 retries
