from nonebot import require
import asyncio
import json
import random
import httpx
import aiofiles
from typing import List, Dict, Optional, Any, Tuple
from nonebot.log import logger
require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_cache_file

PLUGIN_NAME = "nonebot_plugin_jimeng"

class SessionManager:
    """
    管理和维护用于 API 认证的 session 及用户积分。
    """

    def __init__(self, accounts: List[Dict[str, str]]):
        self._accounts_config = accounts
        self._cache_file = get_cache_file(PLUGIN_NAME, "cache.json")
        self._accounts_data: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def _read_cache(self) -> Dict[str, Any]:
        """异步读取缓存文件"""
        if not self._cache_file.exists():
            return {}
        try:
            async with aiofiles.open(self._cache_file, "r", encoding="utf-8") as f:
                return json.loads(await f.read())
        except Exception:
            logger.warning("读取即梦缓存文件失败，将创建新的缓存。")
            return {}

    async def _write_cache(self):
        """异步写入缓存文件"""
        async with self._lock:
            try:
                async with aiofiles.open(self._cache_file, "w", encoding="utf-8") as f:
                    await f.write(json.dumps(self._accounts_data, indent=4))
            except Exception:
                logger.exception("写入即梦缓存文件失败。")

    async def _verify_and_get_credit(self, session_id: str) -> Optional[int]:
        """验证 session_id 是否有效，并返回当前积分。"""
        url = "https://commerce-api-sg.capcut.com/commerce/v1/benefits/user_credit"
        headers = {
            "Referer": "https://dreamina.capcut.com",
            "Origin": "https://dreamina.capcut.com",
            "Content-Type": "application/json",
            "Appid": "513641",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        cookies = {"sessionid": session_id}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, cookies=cookies)
            if response.status_code == 200:
                data = response.json()
                if data.get("ret") == "0":
                    credit_info = data["data"]["credit"]
                    total = sum(credit_info.get(k, 0) for k in ["vip_credit", "gift_credit", "purchase_credit"])
                    return int(total)
        except Exception:
            pass
        return None

    async def _login_and_get_data(self, email: str, password: str) -> Optional[Tuple[str, int]]:
        """登录，成功后返回 (session_id, credit)"""
        url = "https://login-row.www.capcut.com/passport/web/email/login/"
        params = {"aid": "513641", "account_sdk_source": "web"}
        form_data = {"email": email, "password": password, "mix_mode": "1"}
        headers = {
            "Referer": "https://dreamina.capcut.com",
            "Origin": "https://dreamina.capcut.com",
            "Appid": "513641",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, params=params, data=form_data,headers=headers)
            if response.status_code == 200 and response.json().get("message") == "success":
                session_id = response.cookies.get("sessionid")
                if session_id:
                    credit = await self._verify_and_get_credit(session_id)
                    if credit is not None:
                        logger.success(f"账号 {email} 登录成功，积分为: {credit}。")
                        return session_id, credit
        except Exception as e:
            logger.error(f"登录时发生未知错误，账号: {email}: {e}")
        logger.error(f"账号 {email} 登录或获取积分失败。")
        return None

    async def initialize_sessions(self):
        """初始化所有账号的 session 和积分数据"""
        async with self._lock:
            self._accounts_data = await self._read_cache()

            for acc_conf in self._accounts_config:
                email = acc_conf["account"]
                password = acc_conf["password"]

                cached_data = self._accounts_data.get(email)
                if cached_data and "session_id" in cached_data:
                    credit = await self._verify_and_get_credit(cached_data["session_id"])
                    if credit is not None:
                        logger.info(f"账号 {email} 使用缓存的 session 登录成功，当前积分为: {credit}。")
                        self._accounts_data[email]["credit"] = credit
                        continue
                    else:
                        logger.info(f"账号 {email} 的缓存 session 已失效，尝试重新登录。")

                login_data = await self._login_and_get_data(email, password)
                if login_data:
                    self._accounts_data[email] = {"session_id": login_data[0], "credit": login_data[1]}
                else:
                    # 如果登录失败，从缓存中移除，以防使用无效数据
                    if email in self._accounts_data:
                        del self._accounts_data[email]

        await self._write_cache()
        logger.info(f"即梦绘图插件初始化完成，可用账号数量: {self.get_available_account_count()}")

    def get_available_account(self, cost: int) -> Optional[Dict[str, Any]]:
        """获取一个积分充足的可用账号"""
        available_accounts = [
            {"email": email, **data}
            for email, data in self._accounts_data.items()
            if data.get("credit", 0) >= cost
        ]
        if not available_accounts:
            return None
        return random.choice(available_accounts)

    async def update_credit(self, email: str, cost: int):
        """更新指定账号的积分"""
        async with self._lock:
            if email in self._accounts_data:
                self._accounts_data[email]["credit"] = self._accounts_data[email].get("credit", 0) - cost
        await self._write_cache()

    def get_available_account_count(self) -> int:
        return len(self._accounts_data)

    def is_available(self) -> bool:
        return self.get_available_account_count() > 0
