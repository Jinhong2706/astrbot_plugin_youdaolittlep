import asyncio
from astrbot.api import logger


async def retry(func, *args, max_retries=3, base_delay=2, **kwargs):
    last_exception = None
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"API 调用失败 (第 {attempt + 1}/{max_retries} 次): {e}, {delay}s 后重试")
                await asyncio.sleep(delay)
    raise last_exception
