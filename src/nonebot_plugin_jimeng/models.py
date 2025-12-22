def get_cost_by_id(target_id):
    for m in models:
        if m.get('id') == target_id:
            return m.get('cost')
    return 0

models = [
    {
        "id": "jimeng-4.5",
        "object": "model",
        "type": "image",
        "description": "国内、国际站均支持，支持 2k/4k、全部 ratio 及 intelligent_ratio（所有站点默认模型）",
        "support_radio": True,
        "cost": 9,
        "support_resolutions": ["2k", "4k"]
    },
    {
        "id": "jimeng-4.1",
        "object": "model",
        "type": "image",
        "description": "仅国内站支持，支持 2k/4k、全部 ratio 及 intelligent_ratio",
        "support_radio": True,
        "cost": 3,
        "support_resolutions": ["2k", "4k"]
    },
    {
        "id": "jimeng-4.0",
        "object": "model",
        "type": "image",
        "description": "国内、国际站均支持",
        "support_radio": True,
        "cost": 3,
        "support_resolutions": ["2k", "4k"]
    },
    {
        "id": "nanobananapro",
        "object": "model",
        "type": "image",
        "description": "仅国际站支持，支持 ratio 和 resolution 参数",
        "support_radio": True,
        "cost": 6,
        "support_resolutions": ["2k", "4k"]
    },
    {
        "id": "nanobanana",
        "object": "model",
        "type": "image",
        "description": "仅国际站支持",
        "support_radio": True,
        "cost": 6,
        "support_resolutions": []
    },
    {
        "id": "jimeng-3.1",
        "object": "model",
        "type": "video",
        "description": "仅国内站支持",
        "support_radio": True,
        "cost": 3,
        "support_resolutions": ["1k", "2k"]
    },
    {
        "id": "jimeng-3.0",
        "object": "model",
        "type": "video",
        "description": "国内、国际站均支持",
        "support_radio": True,
        "cost": 3,
        "support_resolutions": ["1k", "2k"]
    },
    {
        "id": "jimeng-2.1",
        "object": "model",
        "type": "video",
        "description": "仅国内站支持",
        "support_radio": True,
        "cost": 3,
        "support_resolutions": []
    },
    {
        "id": "jimeng-video-3.0",
        "object": "model",
        "type": "video",
        "description": "即梦AI视频生成模型 3.0 版本",
        "support_radio": True,
        "cost": 45,
        "support_resolutions": ["720p", "1080p"]
    },
    {
        "id": "jimeng-video-3.0-pro",
        "object": "model",
        "type": "video",
        "description": "即梦AI视频生成模型 3.0 专业版",
        "support_radio": True,
        "cost": 235,
        "support_resolutions": []
    },
    {
        "id": "jimeng-video-2.0-pro",
        "object": "model",
        "type": "video",
        "description": "即梦AI视频生成模型 2.0 专业版",
        "support_radio": True,
        "cost": 75,
        "support_resolutions": []
    }
]