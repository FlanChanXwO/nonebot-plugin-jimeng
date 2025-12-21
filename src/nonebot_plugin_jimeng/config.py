from typing import Optional

from pydantic import BaseModel


class ScopedConfig(BaseModel):
    # 如果该选项启用，则采用账号的方式自动获取密钥并调用接口，默认为true
    use_account: Optional[bool]
    # 如果你需要登录
    accounts: list[dict[str,str]]
    # 域名（用于区分国内国外）
    domain: str
    # 接口地址
    open_api_url: str
    # 密钥（当use_account=true失效）
    secret_key: Optional[str]
    # 密钥前缀，如果你需要搭配逆向使用
    secret_key_prefix: str = ""
    # 模型
    model: str
    # 模型消耗点数
    model_cost: int = 9
    # 分辨率
    resolution: str
    # 如果不配置该参数，则采用"intelligent_ratio": true
    radio: Optional[str] = None

class Config(BaseModel):
    jimeng: ScopedConfig
