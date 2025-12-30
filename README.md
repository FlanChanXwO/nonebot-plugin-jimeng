<div align="center">
    <a href="https://v2.nonebot.dev/store">
    <img src="https://raw.githubusercontent.com/fllesser/nonebot-plugin-template/refs/heads/resource/.docs/NoneBotPlugin.svg" width="310" alt="logo"></a>

## ✨ 即梦绘画 ✨
[![LICENSE](https://img.shields.io/github/license/FlanChanXwO/nonebot-plugin-jimeng.svg)](./LICENSE)
[![pypi](https://img.shields.io/pypi/v/nonebot-plugin-jimeng.svg)](https://pypi.python.org/pypi/nonebot-plugin-jimeng)
[![python](https://img.shields.io/badge/python-3.10|3.11|3.12|3.13-blue.svg)](https://www.python.org)
[![uv](https://img.shields.io/badge/package%20manager-uv-black?style=flat-square&logo=uv)](https://github.com/astral-sh/uv)
<br/>
[![ruff](https://img.shields.io/badge/code%20style-ruff-black?style=flat-square&logo=ruff)](https://github.com/astral-sh/ruff)
[![pre-commit](https://results.pre-commit.ci/badge/github/FlanChanXwO/nonebot-plugin-jimeng/master.svg)](https://results.pre-commit.ci/latest/github/FlanChanXwO/nonebot-plugin-jimeng/master)

</div>

## 📖 介绍

一个基于 NoneBot2 的 AI 创作插件，通过调用**即梦（Jimeng）**的 OpenAPI 实现图片生成和视频生成功能。

- **文生图**：根据文本描述生成图片。
- **图生图**：结合图片和文本描述生成新的图片。
- **文生视频**：根据文本描述生成视频。
- **图生视频**：根据图片描述生成视频。
- **多账号支持**：内置简单的多账号轮询和积分管理机制。

## 💿 安装

<details open>
<summary>使用 nb-cli 安装 (推荐)</summary>
在 nonebot2 项目的根目录下打开命令行, 输入以下指令即可安装

    nb plugin install nonebot-plugin-jimeng --upgrade

</details>

<details>
<summary>使用包管理器安装</summary>
在 nonebot2 项目的插件目录下, 打开命令行, 根据你使用的包管理器, 输入相应的安装命令

<details>
<summary>pip</summary>

    pip install nonebot-plugin-jimeng

</details>
<details>
<summary>pdm</summary>

    pdm add nonebot-plugin-jimeng

</details>
<details>
<summary>poetry</summary>

    poetry add nonebot-plugin-jimeng

</details>
<details>
<summary>uv</summary>

    uv pip install nonebot-plugin-jimeng

</details>

</details>

安装后，请打开 nonebot2 项目根目录下的 `pyproject.toml` 文件, 在 `[tool.nonebot]` 部分的 `plugins` 列表中添加 `nonebot_plugin_jimeng` 以加载插件。

    [tool.nonebot]
    plugins = [
        # ... other plugins
        "nonebot_plugin_jimeng"
    ]


## ⚙️ 配置

在您的 nonebot2 项目的 `.env` 或 `.env.prod` 文件中添加以下配置项。

|                   配置项                   | 必填 |     默认值      | 说明                                                                                                                                |
|:---------------------------------------:|:--:|:------------:|:----------------------------------------------------------------------------------------------------------------------------------|
|           `JIMENG__ACCOUNTS`            | 否  |     `[]`     | 即梦账号（目前主要是国际服支持账密登录）列表。当 `JIMENG_USE_ACCOUNT=true` 时需要填写。格式为 `'[{"account": "user1@example.com", "password": "password1"}, ...]'` |
|          `JIMENG__USE_ACCOUNT`          | 否  |    `True`    | 是否通过账号自动获取密钥。如果设为 `False`，则需要提供 `JIMENG_SECRET_KEY`。                                                                              |
|         `JIMENG__OPEN_API_URL`          | 否  |     `''`     | 逆向 API 的地址或官方API地址。                                                                                                               |
|      `JIMENG__DEFAULT_IMAGE_MODEL`      | 否  | `jimeng-4.5` | 默认使用的图像生成模型。                                                                                                                      |
|      `JIMENG__DEFAULT_VIDEO_MODEL`      | 否  | `jimeng-video-3.0` | 默认使用的视频生成模型。                                                                                                                      |
|          `JIMENG__RESOLUTION`           | 否  |     `2k`     | 图像模型生成分辨率。                                                                                                                        |
| `JIMENG__MAX_CONCURRENT_TASKS_PER_USER` | 否  |     `2`      | 每个用户的最大并发任务数。                                                                                                                     |
|          `JIMENG__MAX_RETRIES`          | 否  |     `3`      | 请求失败时的最大重试次数，一般是上传图片出现问题重试。                                                                                                       |
|          `JIMENG__RETRY_DELAY`          | 否  |     `1`      | 每次重试的间隔时间（秒）。                                                                                                                     |
|            `JIMENG__TIMEOUT`            | 否  |    `600`     | 发送API请求的超时时间（秒）。如果为`-1`则不会有超时设置                                                                                                   |
|          `JIMENG__SECRET_KEY`           | 否  |     `""`     | API 密钥。当 `JIMENG_USE_ACCOUNT=false` 时生效。                                                                                          |
|       `JIMENG__REFRESH_INTERVAL`        | 否  |     `1`      | 自动刷新账号积分数据的间隔时间，单位小时，默认1小时                                                                                                        |
### `JIMENG_ACCOUNTS` 格式说明
这是一个 JSON 字符串数组，每个对象代表一个即梦账号。插件启动时会根据此配置初始化 `session_id`。

**配置示例：**
JIMENG__ACCOUNTS配置示例
```env
# .env.prod
JIMENG_ACCOUNTS='[{"email": "your_email1@example.com", "password": "12234" , "region": "hk"}, {"email": "your_email1@example.com", "password": "12234" , "region": "jp"}]'
```


## 💡 注意事项
如果使用图生图功能，请确保你的图片可以被正确访问

## 

## 🎉 使用

### 指令表
|         指令          | 说明                                 |
|:-------------------:|:-----------------------------------|
|    `即梦绘画 <关键词>`     | **文生图**。根据提供的关键词进行创作。              |
| `即梦绘画 <关键词>` (回复图片) | **图生图**。回复一张图片，并附上关键词，将在原图基础上进行创作。 |
|       `即梦积分`        | 查询可用账号的积分                          |
|       `即梦视频`        | **文/图生视频**。启动交互式向导设置参数然后生成视频。      |
### 🎨 效果图
**文生图**
```
即梦绘画 画一个二次元狐娘给我
```
![img_1.png](https://github.com/FlanChanXwO/nonebot-plugin-jimeng/blob/master/assets/img_1.png)

**图生图**
(回复一张图片)
```
即梦绘画 让她躺在一个洁白的床
```
![img.png](https://github.com/FlanChanXwO/nonebot-plugin-jimeng/blob/master/assets/img.png)

**文生视频**
```
即梦视频 一个苹果摔落在地上
```
![img_2.png](https://github.com/FlanChanXwO/nonebot-plugin-jimeng/blob/master/assets/img_2.png)
![img_3.png](https://github.com/FlanChanXwO/nonebot-plugin-jimeng/blob/master/assets/img_3.png)

**图生视频**
```
即梦视频 (在交互式向导中提供图片)
```
![img_4.png](https://github.com/FlanChanXwO/nonebot-plugin-jimeng/blob/master/assets/img_4.png)
![img_5.png](https://github.com/FlanChanXwO/nonebot-plugin-jimeng/blob/master/assets/img_5.png)

## TODO

- [x] 完成文生图功能 (text-to-image)
- [x] 完成图生图功能 (image-to-image)
- [ ] 完成交互式自定义参数生成图片功能 (text/image-to-image)
- [x] 完成图生视频功能 (image-to-video)
- [x] 完成文生视频功能 (text-to-video)
- [x] 完成图生视频功能 (image-to-video)
- [x] 完成交互式自定义参数生成视频功能 (text/image-to-video)
- [x] 多账号轮询与积分管理

## 🙏 致谢
感谢 [https://github.com/iptag/jimeng-api](https://github.com/iptag/jimeng-api) 提供的 OpenAPI 支持。
