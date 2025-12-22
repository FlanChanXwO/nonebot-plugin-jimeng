import asyncio
from typing import Dict
from nonebot import get_plugin_config
from nonebot.adapters.onebot.v11 import Event, Bot as OneBotV11Bot
from .config import Config

plugin_config = get_plugin_config(Config).jimeng

_user_semaphores: Dict[str, asyncio.Semaphore] = {}
_lock = asyncio.Lock()  # 一个锁，用于在创建 Semaphore 时避免竞争条件


async def get_user_semaphore(user_id: str) -> asyncio.Semaphore:
    """获取或创建用户的 Semaphore"""
    async with _lock:
        if user_id not in _user_semaphores:
            _user_semaphores[user_id] = asyncio.Semaphore(plugin_config.max_concurrent_tasks_per_user)
        return _user_semaphores[user_id]


async def concurrency_limit(event: Event, bot: OneBotV11Bot):
    """
    一个依赖项，用于限制用户并发。
    在事件处理开始前获取信号量，在结束后释放。
    """
    user_id = event.get_user_id()
    semaphore = await get_user_semaphore(user_id)

    # 尝试立即获取信号量，若已满则丢弃任务并提醒用户
    try:
        await asyncio.wait_for(semaphore.acquire(), timeout=5)
    except asyncio.TimeoutError:
        await bot.send(event, "你已有一个绘图任务在进行中，请稍后再试。")
        return
    except ExceptionGroup:
        return
    except RuntimeError:
        return
    try:
        # yield 将控制权交给事件处理器
        yield
    finally:
        # 事件处理结束后，无论成功还是失败，都释放信号量
        semaphore.release()
