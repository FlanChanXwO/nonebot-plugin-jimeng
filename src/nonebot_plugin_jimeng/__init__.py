import asyncio
import io
from typing import Dict, Any, List, Tuple

import httpx
from nonebot import on_regex, get_driver, require, on_command
from nonebot.adapters.onebot.v11 import Bot as OneBotV11Bot
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment, GroupMessageEvent, Message
from nonebot.exception import FinishedException, IgnoredException
from nonebot.internal.params import Depends
from nonebot.log import logger
from nonebot.params import RegexGroup
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata, get_plugin_config
from nonebot.typing import T_State

from .concurrency import concurrency_limit
from .config import Config
from .models import get_cost_by_id, models as all_models
from .session_manager import SessionManager
from .utils import key_prefix_by_region

require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler

__plugin_meta__ = PluginMetadata(
    name="即梦",
    description="使用即梦 OpenAPI 进行 AI 绘画与视频生成",
    usage="文生图: \"/即梦绘画 [关键词]\"\n"
          "图生图: 回复图片并使用 \"/即梦绘画 [关键词]\"\n"
          "视频生成: \"/即梦视频\" (启动交互式向导)\n"
          "查询积分: \"/即梦积分\"",
    type="application",
    config=Config,
    supported_adapters={"~onebot.v11"},
    homepage="https://github.com/FlanChanXwO/nonebot-plugin-jimeng",
    extra={
        "author": "FlanChanXwO",
        "version": "0.4.0",
    },
)

# --- 初始化 ---
plugin_config = get_plugin_config(Config).jimeng
session_manager = SessionManager(plugin_config.accounts)
# 筛选出视频模型以供后续使用
VIDEO_MODELS = [m for m in all_models if m.get("type") == "video"]
VIDEO_RATIOS = ["16:9", "9:16", "4:3", "3:4", "1:1"]
model_prompt_text = "第3步: 请选择视频模型 (输入序号)，发送【跳过】将使用默认模型。\n" + \
                    "\n".join([f"{i + 1}. {m['id']} (消耗: {m['cost']}积分)\n   {m['description']}" for i, m in
                               enumerate(VIDEO_MODELS)])

ratio_prompt_text = "第4步: 请选择视频比例 (输入序号)，发送【跳过】将使用默认比例 (16:9)。\n" + \
                    "\n".join([f"{i + 1}. {r}" for i, r in enumerate(VIDEO_RATIOS)])


@get_driver().on_startup
async def on_startup():
    if plugin_config.use_account:
        await session_manager.initialize_sessions()
        logger.info("即梦插件初始化完成，开启定时任务刷新积分。")
        scheduler.add_job(session_manager.refresh_all_credits, "interval", hours=plugin_config.refresh_interval,
                          id="jimeng_refresh_credits")
    else:
        logger.info("即梦插件未启用多账号登录，使用固定密钥。")


# --- 匹配器定义 ---
jimeng_draw_matcher = on_regex(r"^/即梦绘画\s*(.*)$", priority=5, block=True)
jimeng_video_matcher = on_command("即梦视频", priority=5, block=True)
jimeng_credit_matcher = on_command("即梦积分", priority=5, block=True, permission=SUPERUSER)


# --- 辅助函数 ---
async def get_bot_name(bot: OneBotV11Bot, event: MessageEvent) -> str:
    """获取机器人在群里或私聊中的昵称"""
    if isinstance(event, GroupMessageEvent):
        resp = await bot.get_group_member_info(group_id=event.group_id, user_id=int(bot.self_id), no_cache=False)
        return resp.get("card") or resp.get("nickname", "我")
    resp = await bot.get_login_info()
    return resp.get("nickname", "我")


async def download_images_to_bytes(image_urls: List[str]) -> List[bytes]:
    """从给定的URL列表中并发下载图片，并返回bytes列表。"""

    async def _download_one(url: str, client: httpx.AsyncClient) -> bytes:
        try:
            resp = await client.get(url, timeout=120.0, follow_redirects=True)
            resp.raise_for_status()
            return resp.content
        except httpx.HTTPStatusError as e:
            logger.error(f"下载图片失败: HTTP {e.response.status_code}, URL: {url}")
            raise IOError(f"下载图片失败: HTTP {e.response.status_code}") from e
        except Exception as e:
            logger.error(f"下载图片时发生未知错误: {e}, URL: {url}")
            raise IOError(f"下载图片时发生未知错误: {e}") from e

    tasks = []
    async with httpx.AsyncClient() as client:
        for url in image_urls:
            tasks.append(_download_one(url, client))
        results = await asyncio.gather(*tasks, return_exceptions=False)
    return results


# --- 视频生成处理器 (全新交互式) ---

@jimeng_video_matcher.handle()
async def handle_video_start(state: T_State):
    """启动视频生成交互式向导"""
    try:
        state["params"] = {}  # 初始化参数字典
        logger.info("启动即梦视频交互式向导")
    except IgnoredException:
        pass


@jimeng_video_matcher.got("image", prompt="第1步: 请发送用于生成视频的图片 (1-2张)，如果想使用纯文本生成，请发送【跳过】。")
async def handle_video_image(state: T_State):
    """步骤1：接收图片"""
    message: Message = state["image"]
    text_input = message.extract_plain_text().strip()
    image_urls = [seg.data["url"] for seg in message if seg.type == "image" and seg.data.get("url")]

    if image_urls:
        logger.info(f"交互式收到图片: {image_urls}")
        state["image_urls"] = image_urls
    elif text_input in ["跳过", "不用", "不用了", "skip"]:
        state["image_urls"] = []
    else:
        await jimeng_video_matcher.reject("输入无效，请发送图片或输入“跳过”。")


@jimeng_video_matcher.got("prompt", prompt="第2步: 请输入视频的描述 (prompt)。")
async def handle_video_prompt(state: T_State):
    """步骤2：接收Prompt"""
    prompt_text = state["prompt"].extract_plain_text().strip()
    if not prompt_text:
        await jimeng_video_matcher.reject("描述不能为空哦，请重新输入。")
    state["params"]["prompt"] = prompt_text


@jimeng_video_matcher.got("model", prompt=model_prompt_text)
async def handle_video_model(state: T_State):
    """步骤3：选择模型"""
    choice = state["model"].extract_plain_text().strip()
    if choice in ["跳过", "skip"]:
        state["params"]["model"] = plugin_config.default_video_model
        return

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(VIDEO_MODELS):
            state["params"]["model"] = VIDEO_MODELS[idx]['id']
        else:
            await jimeng_video_matcher.reject("无效的序号，请重新输入。")
    except ValueError:
        await jimeng_video_matcher.reject("请输入数字序号或“跳过”。")


@jimeng_video_matcher.got("ratio", prompt=ratio_prompt_text)
async def handle_video_ratio(bot: OneBotV11Bot, event: MessageEvent, state: T_State):
    """步骤4：选择比例"""
    choice = state["ratio"].extract_plain_text().strip()
    if choice in ["跳过", "skip"]:
        state["params"]["ratio"] = "16:9"
        return

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(VIDEO_RATIOS):
            state["params"]["ratio"] = VIDEO_RATIOS[idx]
            # --- 所有参数收集完毕，开始执行 ---
            params = state["params"]
            # 将暂存的图片URL加入
            params["filePaths"] = state.get("image_urls", [])
            logger.info(f"视频生成交互完成，最终参数: {params}")
            await process_video_request(bot, event, params)
        else:
            await jimeng_video_matcher.reject("无效的序号，请重新输入。")
    except ValueError:
        await jimeng_video_matcher.reject("请输入数字序号或“跳过”。")

# 待修复时长选择
# @jimeng_video_matcher.got("ratio", prompt=ratio_prompt_text)
# async def handle_video_ratio(state: T_State):
#     """步骤4：选择比例"""
#     choice = state["ratio"].extract_plain_text().strip()
#     if choice in ["跳过", "skip"]:
#         state["params"]["ratio"] = "16:9"
#         return
#
#     try:
#         idx = int(choice) - 1
#         if 0 <= idx < len(VIDEO_RATIOS):
#             state["params"]["ratio"] = VIDEO_RATIOS[idx]
#
#         else:
#             await jimeng_video_matcher.reject("无效的序号，请重新输入。")
#     except ValueError:
#         await jimeng_video_matcher.reject("请输入数字序号或“跳过”。")
#
#
#
# @jimeng_video_matcher.got("duration", prompt="第5步: 请选择视频时长 (输入序号)，发送【跳过】将使用默认值 (5秒)。\n1. 5秒\n2. 10秒")
# async def handle_video_duration(bot: OneBotV11Bot, event: MessageEvent, state: T_State):
#     """步骤5：设置时长并触发最终处理 (仅支持5秒或10秒)"""
#     choice = state["duration"].extract_plain_text().strip()
#     duration = 5  # 默认值 (整数)
#
#     if choice in ["跳过", "skip"]:
#         pass  # 使用默认值 5 秒
#     elif choice == "1":
#         duration = 5
#     elif choice == "2":
#         duration = 10
#     else:
#         # 如果用户输入了无效的选项，则拒绝并要求重新输入
#         await jimeng_video_matcher.reject("无效的选项，请输入 1, 2, 或“跳过”。")
#
#     state["params"]["duration"] = str(duration)
#
#     # --- 所有参数收集完毕，开始执行 ---
#     params = state["params"]
#     # 将暂存的图片URL加入
#     params["filePaths"] = state.get("image_urls", [])
#
#     logger.info(f"视频生成交互完成，最终参数: {params}")
#     await process_video_request(bot, event, params)



async def process_video_request(bot: OneBotV11Bot, event: MessageEvent, params: Dict[str, Any], _=Depends(concurrency_limit)):
    """核心视频请求处理函数 (统一本地上传)"""
    user_id = event.get_user_id()
    bot_name = await get_bot_name(bot, event)
    is_in_group = isinstance(event, GroupMessageEvent)

    if not params.get("prompt"):
        await jimeng_video_matcher.finish("【即梦视频】\n内部错误：缺少必要的 prompt 参数。")
        return

    expect_cost = get_cost_by_id(params.get("model", plugin_config.default_video_model))
    account = session_manager.get_available_account(expect_cost)
    if not account:
        await jimeng_video_matcher.finish(
            (MessageSegment.at(user_id) + "\n" if is_in_group else "") + MessageSegment.text(
                f"【即梦视频】\n当前所有账号积分不足以支付本次消耗（需要 {expect_cost} 积分），请稍后再试。"))
        return

    session_id, email, region = account["session_id"], account["email"], account["region"]
    logger.info(f"使用账号 {email} 进行视频生成，预估消耗 {expect_cost} 积分。")

    # --- 图片下载与准备 ---
    image_urls_to_download = params.pop("filePaths", [])
    files_to_upload: Dict[str, Tuple[str, io.BytesIO, str]] = {}
    if image_urls_to_download:
        await jimeng_video_matcher.send("【即梦视频】\n参数设置完成！正在下载并准备图片...")
        try:
            image_bytes_list = await download_images_to_bytes(image_urls_to_download)
            for i, img_bytes in enumerate(image_bytes_list):
                field_name = f"image_file_{i + 1}"
                files_to_upload[field_name] = (f"image_{i + 1}.png", io.BytesIO(img_bytes), "image/png")
        except Exception as e:
            await jimeng_video_matcher.finish(f"【即梦视频】\n图片处理失败: {e}")
            return

    await jimeng_video_matcher.send((MessageSegment.at(user_id) + "\n" if is_in_group else "") + MessageSegment.text(
        f"【即梦视频】\n{bot_name}正在生成视频，任务已提交，请耐心等待，预计至少耗时5~8分钟，高峰期时可能不止5~8分钟，也许会非常非常久..."))

    api_url = f"{plugin_config.open_api_url}/v1/videos/generations"
    key_prefix = key_prefix_by_region(region)
    auth_header = f"Bearer {key_prefix}{session_id}" if plugin_config.use_account else plugin_config.secret_key
    headers = {"Authorization": auth_header}

    logger.debug("params = " + str(params))

    try:
        async with httpx.AsyncClient() as client:
            timeout_value = None if plugin_config.timeout == -1 else plugin_config.timeout
            response = await client.post(api_url, data=params, files=files_to_upload, headers=headers,
                                         timeout=timeout_value)

        if response.status_code == 200:
            res_json = response.json()
            video_data = res_json.get("data")
            if not video_data or not isinstance(video_data, list) or not video_data[0].get("url"):
                raise Exception(res_json.get("message", "API返回数据格式错误"))

            video_url = video_data[0]["url"]
            logger.success(f"视频生成成功，URL: {video_url}")

            async with httpx.AsyncClient() as video_client:
                video_res = await video_client.get(video_url, timeout=300.0)
                video_res.raise_for_status()
                video_content = video_res.content

            await jimeng_video_matcher.finish((MessageSegment.at(user_id) + "\n" if is_in_group else "") +
                                              MessageSegment.text("【即梦视频】\n视频生成完成！") +
                                              MessageSegment.video(video_content))
        else:
            logger.error(f"调用即梦视频 API 失败: {response.status_code} {response.text}")
            await jimeng_video_matcher.finish(
                (MessageSegment.at(user_id) + "\n" if is_in_group else "") + MessageSegment.text(
                    f"【即梦视频】\n视频生成失败：\n错误码：{response.status_code}\n信息： {response.text}"))
    except FinishedException:
        pass
    except IgnoredException:
        pass
    except Exception as e:
        logger.exception("处理即梦视频请求时发生错误")
        await jimeng_video_matcher.finish(
            (MessageSegment.at(user_id) + "\n" if is_in_group else "") + MessageSegment.text(
                f"【即梦视频】\n发生严重错误：{e}"))


# --- 绘画处理器 (保持不变) ---
@jimeng_draw_matcher.handle()
async def handle_jimeng_draw(event: MessageEvent, bot: OneBotV11Bot, _=Depends(concurrency_limit),
                             prompt_group: tuple = RegexGroup()):
    """图生图&文生图处理器 (V2 - 图生图统一本地上传)"""
    prompt = prompt_group[0].strip()
    user_id = event.get_user_id()
    bot_name = await get_bot_name(bot, event)
    is_in_group = isinstance(event, GroupMessageEvent)

    image_url, is_img2img = None, False
    if event.reply:
        for seg in event.reply.message:
            if seg.type == "image":
                image_url = seg.data.get("url")
                if image_url:
                    is_img2img = True
                    logger.info(f"检测到图生图请求，图片URL: {image_url}")
                break
        if not is_img2img:
            await jimeng_draw_matcher.finish(MessageSegment.text("【即梦绘画】\n请引用图片进行图生图绘画哦！"))
            return
    if not prompt and not is_img2img:  # 文生图必须有prompt
        await jimeng_draw_matcher.finish(MessageSegment.text("【即梦绘画】\n请输入你想要画的内容！"))
        return

    cost = get_cost_by_id(plugin_config.default_image_model)
    expect_cost = cost * 4
    account = session_manager.get_available_account(expect_cost)
    if not account:
        await jimeng_draw_matcher.finish(
            (MessageSegment.at(user_id) + "\n" if is_in_group else "") + MessageSegment.text(
                f"【即梦绘画】\n当前所有账号积分不足以支付本次消耗（需要 {expect_cost} 积分），请稍后再试。"))
        return

    session_id, email, region = account["session_id"], account["email"], account["region"]
    logger.info(f"使用账号 {email} 进行绘图，预估消耗 {expect_cost} 积分。")

    # --- 图片下载与准备 (图生图) ---
    files_to_upload: Dict[str, Tuple[str, io.BytesIO, str]] = {}
    if is_img2img:
        await jimeng_draw_matcher.send("【即梦绘画】\n正在下载并准备图片，请稍候...")
        try:
            # 图生图API只支持一张图片，字段为 images
            image_bytes_list = await download_images_to_bytes([image_url])
            files_to_upload["images"] = ("image.png", io.BytesIO(image_bytes_list[0]), "image/png")
        except Exception as e:
            await jimeng_draw_matcher.finish(f"【即梦绘画】\n图片处理失败: {e}")
            return

    await jimeng_draw_matcher.send((MessageSegment.at(user_id) + "\n" if is_in_group else "") + MessageSegment.text(
        f"【即梦绘图】\n{bot_name}正在绘画哦，花费时间至少1~3分钟，请稍候..."))

    api_url = f"{plugin_config.open_api_url}/v1/images/{'compositions' if is_img2img else 'generations'}"
    key_prefix = key_prefix_by_region(region)
    headers = {
        "Authorization": f"Bearer {key_prefix}{session_id}" if plugin_config.use_account else plugin_config.secret_key}

    payload = {"model": plugin_config.default_image_model, "prompt": prompt, "resolution": plugin_config.resolution}

    max_retries, retry_delay = plugin_config.max_retries, plugin_config.retry_delay
    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient() as client:
                timeout_value = None if plugin_config.timeout == -1 else plugin_config.timeout
                if is_img2img:  # 图生图：multipart
                    response = await client.post(api_url, data=payload, files=files_to_upload, headers=headers,
                                                 timeout=timeout_value)
                else:  # 文生图：json
                    headers["Content-Type"] = "application/json"

                    response = await client.post(api_url, json=payload, headers=headers, timeout=timeout_value)

            if response.status_code == 200:
                res_json = response.json()
                img_data_list = res_json.get("data")
                if img_data_list is None:
                    if res_json.get("code") == -2007 and attempt < max_retries:
                        logger.warning(f"API返回上传失败，准备重试。响应: {res_json}")
                        await asyncio.sleep(retry_delay)
                        continue
                    raise Exception(res_json.get("message", "API返回未知错误，data为空。"))

                img_count = len(img_data_list)
                actual_cost = img_count * cost
                if plugin_config.use_account:
                    await session_manager.update_credit(email, actual_cost)
                logger.success(f"账号 {email} 绘图成功，消耗 {actual_cost} 积分。")

                images_msgs = (MessageSegment.at(user_id) + "\n" if is_in_group else "") + MessageSegment.text(
                    f"【即梦绘画】\n完成【共{img_count}张】")

                # 下载结果图
                result_urls = [img["url"] for img in img_data_list]
                image_contents = await download_images_to_bytes(result_urls)
                for content in image_contents:
                    if content: images_msgs.append(MessageSegment.image(content))

                await jimeng_draw_matcher.finish(images_msgs)
                break
            else:
                logger.error(f"调用即梦 API 失败: {response.status_code} {response.text}")
                await jimeng_draw_matcher.finish(
                    (MessageSegment.at(user_id) + "\n" if is_in_group else "") + MessageSegment.text(
                        f"【即梦绘画】\n绘图失败了：\n错误码：{response.status_code}\n信息： {response.text}"))
                break
        except FinishedException:
            pass
        except IgnoredException:
            pass
        except Exception as e:
            logger.exception(f"处理即梦绘图请求时发生错误 (尝试次数 {attempt + 1}): {e}")
            if attempt >= max_retries:
                await jimeng_draw_matcher.finish(
                    (MessageSegment.at(user_id) + "\n" if is_in_group else "") + MessageSegment.text(
                        f"【即梦绘画】\n发生严重错误，已重试 {max_retries} 次但仍失败：{e}"))
                break


# --- 积分查询处理器 (保持不变) ---
@jimeng_credit_matcher.handle()
async def handle_check_credit():
    if not plugin_config.use_account:
        await jimeng_credit_matcher.finish("【即梦积分】\n当前未启用多账号模式，无法查询积分。")
        return

    await jimeng_credit_matcher.send("【即梦积分】\n正在获取所有账号的积分信息，请稍候...")
    try:
        await session_manager.refresh_all_credits()
    except Exception as e:
        logger.exception("手动刷新即梦积分时发生错误。")
        await jimeng_credit_matcher.finish(f"【即梦积分】\n获取积分时遇到错误: {e}")
        return

    accounts_data = session_manager.get_all_accounts_data()
    if not accounts_data:
        await jimeng_credit_matcher.finish("【即梦积分】\n获取完成，但未找到任何可用的即梦账号。")
        return

    total_credit = 0
    message_lines = ["【即梦积分】\n所有账号积分详情如下："]
    sorted_accounts = sorted(accounts_data.items(), key=lambda item: item[0])

    for email, data in sorted_accounts:
        credit = data.get("credit", 0)
        message_lines.append(f"账号: {email}\n剩余积分: {credit}")
        total_credit += credit

    message_lines.append("--------------------")
    message_lines.append(f"总计可用账号: {len(accounts_data)}个")
    message_lines.append(f"总计剩余积分: {total_credit}")

    await jimeng_credit_matcher.finish("\n".join(message_lines))
