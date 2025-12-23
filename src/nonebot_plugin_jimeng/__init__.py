import asyncio
from typing import cast

import httpx
from nonebot import on_regex, get_driver, require
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment, GroupMessageEvent
from nonebot.adapters.onebot.v11 import Bot as OneBotV11Bot
from nonebot.exception import FinishedException
from nonebot.internal.params import Depends
from nonebot.log import logger
from nonebot.params import RegexGroup
from nonebot.plugin import PluginMetadata, get_plugin_config
from .models import get_cost_by_id
from .concurrency import concurrency_limit
from .config import Config
from .utils import key_prefix_by_region
from .session_manager import SessionManager
require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler
__plugin_meta__ = PluginMetadata(
    name="即梦绘画",
    description="使用即梦 OpenAPI 进行 AI 绘画（支持文生图和图生图）",
    usage="文生图: /即梦绘画 [关键词]\n图生图: 回复一张图片并使用 /即梦绘画 [关键词]",
    type="application",
    config=Config,
    supported_adapters={"~onebot.v11"},
    homepage="https://github.com/FlanChanXwO/nonebot-plugin-jimeng",
    extra={
        "author": "FlanChanXwO",
        "version": "0.1.6",
    },
)

# --- 初始化 ---
plugin_config = get_plugin_config(Config).jimeng
session_manager = SessionManager(plugin_config.accounts)


@get_driver().on_startup
async def on_startup():
    if plugin_config.use_account:
        await session_manager.initialize_sessions()
        # --- 开启定时任务 ---
        logger.info("即梦绘画插件初始化完成，开启定时任务刷新积分。")
        scheduler.add_job(session_manager.refresh_all_credits, "interval", days=1, id="jimeng_refresh_credits")
    else:
        logger.info("即梦绘画插件未启用多账号登录，使用固定密钥。")


jimeng_matcher = on_regex(r"^/即梦绘画\s*(.*)$", priority=5, block=True)


@jimeng_matcher.handle()
async def handle_jimeng_draw(event: MessageEvent,
                             bot: OneBotV11Bot,
                             _=Depends(concurrency_limit),  # 依赖注入 - 拦截器
                             prompt_group: tuple = RegexGroup()):
    prompt = prompt_group[0].strip()
    user_id = event.get_user_id()
    is_in_group = type(event) == GroupMessageEvent
    if is_in_group:
        resp = await bot.get_group_member_info(group_id=cast(GroupMessageEvent, event).group_id,
                                               user_id=int(bot.self_id),
                                               no_cache=False)
        card = resp["card"]
        nickname = resp["nickname"]
        bot_name = card if card else nickname
    else:
        resp = await bot.get_stranger_info(user_id=int(bot.self_id), no_cache=False)
        bot_name = resp["nickname"]

    image_url = None
    is_img2img = False
    # 检查是否为图生图 (回复图片)
    if event.reply:
        for seg in event.reply.message:
            if seg.type == "image":
                image_url = seg.data.get("url")
                if image_url:
                    is_img2img = True
                    logger.info(f"检测到图生图请求，图片URL: {image_url}")
                break
        # 如果没有图片则提示
        if not is_img2img:
            await jimeng_matcher.finish(
                ((MessageSegment.at(user_id) + "\n" if is_in_group else "") if is_in_group else "") + MessageSegment.text("【即梦绘画】\n请引用图片进行图生图绘画哦！"))
            return
    if not prompt:
        await jimeng_matcher.finish((MessageSegment.at(user_id) + "\n" if is_in_group else "") + MessageSegment.text(
            "【即梦绘画】\n请输入你想要画的内容，或者回复一张图片并加上描述哦！"))
        return

    # --- 积分和账号检查 ---
    cost = get_cost_by_id(plugin_config.model)
    # 预期消耗点数
    expect_cost = cost * 4
    account = session_manager.get_available_account(expect_cost)

    if not account:
        await jimeng_matcher.finish((MessageSegment.at(user_id) + "\n" if is_in_group else "") + MessageSegment.text(
            f"【即梦绘画】\n当前所有账号积分不足以支付本次消耗（需要 {expect_cost} 积分），请稍后再试。"))
        return
    session_id = account["session_id"]
    email = account["email"]
    region = account["region"]
    logger.info("使用账号 {} 进行绘图，预估消耗 {} 积分。".format(email, expect_cost))

    # --- 发送初始提示 ---
    await jimeng_matcher.send((MessageSegment.at(user_id) + "\n" if is_in_group else "") + MessageSegment.text(
        f"【即梦绘图】\n{bot_name}正在绘画哦，花费时间至少1~3分钟，请稍候..."))
    # 从配置中获取重试次数和延迟
    max_retries = plugin_config.max_retries
    retry_delay = plugin_config.retry_delay

    if is_img2img:
        await jimeng_matcher.send(
            (MessageSegment.at(user_id) + "\n" if is_in_group else "") + MessageSegment.text("【即梦绘画】\n正在上传图片，请稍候..."))

    # --- 构建请求 ---
    api_url = f"{plugin_config.open_api_url}/v1/images/{'compositions' if is_img2img else 'generations'}"
    key_prefix = key_prefix_by_region(region)
    logger.debug("使用 API URL: {}，密钥前缀：{}".format(api_url,key_prefix))
    headers = {
        "Authorization": f"Bearer {key_prefix}{session_id}" if plugin_config.use_account else plugin_config.secret_key,
        "Content-Type": "application/json"
    }
    payload = {
        "model": plugin_config.model,
        "prompt": prompt,
        "resolution": plugin_config.resolution
    }
    if is_img2img:
        # 图生图
        payload["images"] = [image_url]

    for attempt in range(max_retries + 1):  # +1 使得总共执行 max_retries+1 次 (1次初次尝试 + max_retries次重试)
        try:
            # --- 发送请求 ---
            async with httpx.AsyncClient() as client:
                response = await client.post(api_url, json=payload, headers=headers, timeout=plugin_config.timeout)

            if response.status_code == 200:
                # --- 处理成功响应 ---
                response_json = response.json()
                img_url_json_list = response_json.get("data")
                message = response_json.get("message", "")
                code = response_json.get("code", 0)

                # 新增：检查是否需要重试的特定条件
                if img_url_json_list is None and code == -2007:
                    logger.warning(f"检测到“上传失败”，准备重试。响应: {response_json}")
                    # 如果是最后一次尝试，则不再重试，直接抛出异常并结束
                    if attempt >= max_retries:
                        logger.error(f"达到最大重试次数 ({max_retries})，绘图失败。")
                        raise Exception(f"上传失败，已达到最大重试次数。最后错误: {message}")

                    logger.info(f"第 {attempt + 1} 次尝试失败，将在 {retry_delay} 秒后重试...")
                    await asyncio.sleep(retry_delay)
                    continue  # 进入下一次循环重试

                # 如果img_url_json_list为None，但不是因为“上传失败”，则直接报错
                if img_url_json_list is None:
                    logger.error(f"API返回成功状态码，但data为空，且不符合重试条件。响应: {response_json}")
                    raise Exception(message or "API返回未知错误，data为空。")

                # --- 真正成功的逻辑 ---
                img_count = len(img_url_json_list)
                actual_cost = img_count * cost
                if plugin_config.use_account:
                    await session_manager.update_credit(email, actual_cost)
                logger.success(f"账号 {email} 绘图成功，消耗 {actual_cost} 积分。")

                images_msgs = (MessageSegment.at(user_id) + "\n" if is_in_group else "") + MessageSegment.text(f"【即梦绘画】\n完成【共{img_count}张】")

                async def download_image(url: str, client: httpx.AsyncClient) -> bytes:
                    """下载单个图片并返回其二进制内容"""
                    try:
                        response = await client.get(url, timeout=120.0)  # 增加下载超时时间
                        response.raise_for_status()  # 确保下载成功
                        return response.content
                    except httpx.HTTPStatusError as e:
                        logger.error(f"下载图片失败: {e.response.status_code}, URL: {url}")
                        # 返回一个空 bytes 对象或抛出异常，这里选择记录错误后返回空
                        return b""
                    except Exception as e:
                        logger.error(f"下载图片时发生未知错误: {e}, URL: {url}")
                        return b""

                # 2. 创建下载任务列表
                download_tasks = []
                # 3. 复用同一个 httpx.AsyncClient 实例以提高效率
                async with httpx.AsyncClient() as img_client:
                    for result_image in img_url_json_list:
                        img_url = result_image["url"]
                        logger.debug(f"创建图片下载任务: {img_url}")
                        # 将协程对象添加到任务列表
                        task = download_image(img_url, img_client)
                        download_tasks.append(task)

                    # 4. 使用 asyncio.gather 并发执行所有下载任务
                    logger.info(f"正在并行下载 {len(download_tasks)} 张图片...")
                    # results 会是一个包含所有图片 bytes 内容的列表
                    image_contents = await asyncio.gather(*download_tasks)

                logger.info(f"正在发送 {img_count} 个图片结果。")

                # 5. 将下载好的图片内容添加到消息段
                for content in image_contents:
                    if content:  # 确保内容不为空（即下载成功）
                        images_msgs.append(MessageSegment.image(content))

                logger.info(f"图片全部下载完成，正在发送 {img_count} 个图片结果。")
                # 发送图片
                await jimeng_matcher.finish(images_msgs)
                # 成功处理后，必须跳出重试循环
                break

            else:
                # --- 处理失败响应 (如 4xx, 5xx 错误) ---
                # 这种错误通常是不可重试的（如认证失败、参数错误），所以直接失败
                logger.error(f"调用即梦 API 失败: {response.status_code} {response.text}")
                await jimeng_matcher.finish((MessageSegment.at(user_id) + "\n" if is_in_group else "") + MessageSegment.text(
                    f"【即梦绘画】\n绘图失败了，服务器返回错误：\n错误码：{response.status_code}\n错误信息： {response.text}"))
                # 失败后也要跳出循环
                break

        except FinishedException:
            # 捕获 finish() 异常，防止被下面的通用 Exception 捕获
            raise
        except Exception as e:
            # 捕获所有其他异常（包括我们自己抛出的重试失败异常）
            logger.exception(f"处理即梦绘图请求时发生错误 (尝试次数 {attempt + 1}): {e}")
            # 如果是最后一次尝试，则发送最终失败消息
            if attempt >= max_retries:
                await jimeng_matcher.finish((MessageSegment.at(user_id) + "\n" if is_in_group else "") + MessageSegment.text(
                    f"【即梦绘画】\n发生严重错误，已重试 {max_retries} 次但仍失败：{e}"))
            else:
                pass
