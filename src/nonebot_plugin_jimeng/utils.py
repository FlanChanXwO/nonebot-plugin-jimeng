def key_prefix_by_region(region: str) -> str:
    """根据地区返回对应的密钥前缀"""
    region_prefix_map = {
        "HK": "hk-",
        "US": "us-",
        "SG": "sg-",
        "EU": "eu-",
        "IN": "in-",
        "JP": "jp-",
        "AU": "au-",
    }
    return region_prefix_map.get(region.upper(), "")