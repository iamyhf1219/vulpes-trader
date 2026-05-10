"""指数退避重试工具"""

import asyncio
import logging
from typing import Callable, Awaitable, TypeVar, Any

T = TypeVar("T")
logger = logging.getLogger("vulpes.retry")


async def async_retry(
    func: Callable[..., Awaitable[T]],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple = (ConnectionError, TimeoutError),
    *args,
    **kwargs,
) -> T:
    """
    异步指数退避重试

    Args:
        func: 异步函数
        max_retries: 最大重试次数
        base_delay: 初始延迟（秒）
        max_delay: 最大延迟（秒）
        exceptions: 捕获的异常类型
    """
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except exceptions as e:
            last_exception = e
            if attempt < max_retries:
                delay = min(base_delay * (2 ** attempt), max_delay)
                logger.warning(
                    "重试 %d/%d: %s, %.1f秒后重试",
                    attempt + 1, max_retries, str(e), delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error("重试耗尽 (%d次): %s", max_retries, str(e))
                raise
