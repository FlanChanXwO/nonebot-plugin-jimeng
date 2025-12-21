from pydantic import BaseModel


class ScopedConfig(BaseModel):
    # 如果该选项启用，则采用账号的方式自动获取密钥并调用接口，默认为true
    use_account: bool = True
    # 每个用户的最大并发任务数
    max_concurrent_tasks_per_user: int = 2
    # 如果你需要登录
    accounts: list[dict[str,str]] = []
    # 最大重试次数
    max_retries: int = 3
    # 每次重试的间隔时间（秒）
    retry_delay: int = 1
    # 接口地址
    open_api_url: str = ''
    # 密钥（当use_account=true失效）
    secret_key: str = ""
    # 密钥前缀，如果你需要搭配逆向使用
    secret_key_prefix: str = ""
    # 模型
    model: str = 'jimeng-4.5'
    # 模型消耗点数
    model_cost: int = 9
    # 分辨率
    resolution: str = '2k'

class Config(BaseModel):
    jimeng: ScopedConfig
