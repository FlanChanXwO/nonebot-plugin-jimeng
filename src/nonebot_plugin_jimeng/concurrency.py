import asyncio
from typing import Dict
from nonebot import get_plugin_config
from nonebot.adapters.onebot.v11 import Event, Bot as OneBotV11Bot
from nonebot.exception import IgnoredException

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
    command_text = event.get_plaintext()
    key_prefix = "image" if "绘图" in command_text else "video"
    key = key_prefix + "_" +user_id
    semaphore = await get_user_semaphore(key)

    can_proceed = False
    try:
        # 尝试立即获取信号量，不等待
        if not semaphore.locked():
            await semaphore.acquire()
            can_proceed = True
            yield True  # 成功，将控制权交给事件处理器
        else:
            # 已被锁定，发送提示
            await bot.send(event, "你已有一个同类任务在进行中，请稍后再试。")
            yield False # 失败，将控制权交给事件处理器，但传递False
    finally:
        # 只有成功获取了锁，才需要在最后释放
        if can_proceed:
            semaphore.release()

