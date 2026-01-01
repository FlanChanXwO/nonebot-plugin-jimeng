import asyncio
from typing import Dict

from nonebot import get_plugin_config

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