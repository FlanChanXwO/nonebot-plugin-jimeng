import httpx
from nonebot import on_regex, get_driver
from nonebot.exception import FinishedException
from nonebot.plugin import PluginMetadata, get_plugin_config
from nonebot.adapters.onebot.v11 import MessageEvent, Message, MessageSegment
from nonebot.params import RegexGroup
from nonebot.log import logger

from .config import Config
from .session_manager import SessionManager

__plugin_meta__ = PluginMetadata(
    name="即梦绘画",
    description="使用即梦 OpenAPI 进行 AI 绘画（支持文生图和图生图）",
    usage="文生图: /即梦绘图 [关键词]\n图生图: 回复一张图片并使用 /即梦 [关键词]",
    type="application",
    config=Config,
    supported_adapters={"~onebot.v11"},
    homepage="https://github.com/FlanChanXwO/nonebot-plugin-jimeng",
    extra={
        "author": "FlanChanXwO",
        "version": "0.1.0",
    },
)

# --- 初始化 ---
plugin_config = get_plugin_config(Config).jimeng
session_manager = SessionManager(plugin_config.accounts)


@get_driver().on_startup
async def on_startup():
    await session_manager.initialize_sessions()


jimeng_matcher = on_regex(r"^/即梦绘画\s*(.*)$", priority=5, block=True)


@jimeng_matcher.handle()
async def handle_jimeng_draw(event: MessageEvent, prompt_group: tuple = RegexGroup()):
    prompt = prompt_group[0].strip()
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

    if not prompt and not is_img2img:
        await jimeng_matcher.finish("请输入你想要画的内容，或者回复一张图片并加上描述哦！")
        return

    # --- 积分和账号检查 ---
    cost = plugin_config.model_cost  # 默认成本，你可以为图生图设置不同成本
    account = session_manager.get_available_account(cost)

    if not account:
        await jimeng_matcher.finish(f"当前所有账号积分不足以支付本次消耗（需要 {cost} 积分），请稍后再试。")
        return

    session_id = account["session_id"]
    email = account["email"]

    await jimeng_matcher.send("【即梦绘图】正在画画哦，请稍候...")

    try:
        headers = {
            "Authorization": f"Bearer {plugin_config.secret_key_prefix}{session_id}",
        }

        # --- 构建请求 ---
        if is_img2img:
            # 图生图
            api_url = f"{plugin_config.open_api_url}/v1/images/compositions"
            headers["Content-Type"] = "application/json"
            payload = {
                "model": plugin_config.model,
                "prompt": prompt,
                "images": [image_url],
                "resolution": plugin_config.resolution,
            }
            if plugin_config.radio:
                payload["ratio"] = plugin_config.radio

        else:
            # 文生图
            api_url = f"{plugin_config.open_api_url}/v1/images/generations"
            headers["Content-Type"] = "application/json"
            payload = {
                "model": plugin_config.model,
                "prompt": prompt,
                "resolution": plugin_config.resolution,
            }
            if plugin_config.radio:
                payload["ratio"] = plugin_config.radio
            else:
                payload["intelligent_ratio"] = True

        # --- 发送请求 ---
        async with httpx.AsyncClient() as client:
            response = await client.post(api_url, json=payload, headers=headers, timeout=300.0)

        if response.status_code == 200:
            # --- 处理成功响应 ---
            response_json = response.json()
            if response_json["data"] is None:
                raise Exception(response_json["message"])
            await session_manager.update_credit(email, cost)
            logger.success(f"账号 {email} 绘图成功，消耗 {cost} 积分。")
            images_msgs = []
            for result_image in response_json["data"]:
                img_url = result_image["url"]
                # 发送图片
                async with httpx.AsyncClient() as client:
                    logger.debug("正在下载图片{}".format(img_url))
                    image_data = await client.get(img_url)
                    images_msgs.append(MessageSegment.image(image_data.content))
            logger.success(f"正在发送{len(images_msgs)}个图片结果。")
            # 发送图片
            await jimeng_matcher.finish(Message(images_msgs))
        else:
            # --- 处理失败响应 ---
            logger.error(f"调用即梦 API 失败: {response.status_code} {response.text}")
            await jimeng_matcher.finish(f"绘图失败了，服务器返回错误：{response.status_code}")
    except FinishedException:
        pass
    except Exception as e:
        logger.exception(f"处理即梦绘图请求时发生错误: {e}")
        await jimeng_matcher.finish(f"{e}")
