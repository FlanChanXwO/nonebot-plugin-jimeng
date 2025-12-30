from pydantic import BaseModel, Field


class ScopedConfig(BaseModel):
    # 如果该选项启用，则采用账号的方式自动获取密钥并调用接口，默认为true
    use_account: bool = True
    # 每个用户的最大并发任务数
    max_concurrent_tasks_per_user: int = 2
    # 如果你需要登录
    accounts: list[dict[str, str]] = []
    # 最大重试次数
    max_retries: int = 3
    # 每次重试的间隔时间（秒）
    retry_delay: int = 1
    # 请求超时时间（秒）
    timeout: int = 600
    # 接口地址
    open_api_url: str = ''
    # 密钥（当use_account=true失效）
    secret_key: str = ""
    # 默认模型
    default_image_model: str = 'jimeng-4.5'
    default_video_model: str = "jimeng-video-3.0"
    # 分辨率
    resolution: str = '2k'
    # 自动刷新账号积分数据的间隔时间，单位小时，默认1小时
    refresh_interval: int = 1

class Config(BaseModel):
    jimeng: ScopedConfig = Field(default_factory=ScopedConfig)
