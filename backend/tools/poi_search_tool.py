"""POI Search Tool — LangChain-compatible attraction search.

Returns curated points of interest with romantic scoring.
Uses local mock data; API interface reserved for future (高德/Google).
"""

import json
from typing import List, Optional

from langchain_core.tools import tool


# ── Rich mock POI database ───────────────────────────────────────

_MOCK_POI: dict = {
    "大理": [
        {"name": "洱海环湖路", "type": "自然", "tags": ["浪漫", "自然"],
         "lat": 25.6065, "lng": 100.2299, "rating": 4.8, "cost": 0,
         "duration_min": 180, "couple_score": 9.5, "indoor": False,
         "description": "环湖公路全长约120公里，沿途湖光山色，是情侣骑行的绝佳路线。"},
        {"name": "苍山洗马潭索道", "type": "自然", "tags": ["自然", "浪漫"],
         "lat": 25.6544, "lng": 100.1246, "rating": 4.6, "cost": 300,
         "duration_min": 150, "couple_score": 8.5, "indoor": False,
         "description": "登顶苍山，俯瞰洱海全景，山顶常有云雾缭绕，如仙境般浪漫。"},
        {"name": "大理古城", "type": "人文", "tags": ["文艺", "浪漫"],
         "lat": 25.6833, "lng": 100.1620, "rating": 4.5, "cost": 0,
         "duration_min": 120, "couple_score": 9.0, "indoor": False,
         "description": "白族风情古城，青石板路两旁是手工艺店和咖啡馆，适合两人慢慢闲逛。"},
        {"name": "喜洲古镇", "type": "人文", "tags": ["文艺", "网红"],
         "lat": 25.8566, "lng": 100.1195, "rating": 4.4, "cost": 0,
         "duration_min": 120, "couple_score": 8.0, "indoor": False,
         "description": "白族传统民居群，转角楼和稻田景观很适合拍照，有地道的喜洲粑粑。"},
        {"name": "双廊古镇", "type": "人文", "tags": ["浪漫", "网红"],
         "lat": 25.9167, "lng": 100.2021, "rating": 4.3, "cost": 0,
         "duration_min": 150, "couple_score": 8.8, "indoor": False,
         "description": "洱海东岸的海景小镇，有众多海景客栈和咖啡厅，落日时分尤为浪漫。"},
        {"name": "崇圣寺三塔", "type": "文化", "tags": ["文化"],
         "lat": 25.7103, "lng": 100.1431, "rating": 4.5, "cost": 75,
         "duration_min": 90, "couple_score": 6.5, "indoor": False,
         "description": "大理地标性建筑，三塔倒映水中，庄严肃穆。"},
        {"name": "周城扎染博物馆", "type": "文化", "tags": ["文艺", "网红"],
         "lat": 25.8853, "lng": 100.0835, "rating": 4.2, "cost": 30,
         "duration_min": 90, "couple_score": 8.0, "indoor": True,
         "description": "亲手制作一块白族扎染方巾，情侣可做一对留念。"},
        {"name": "床单厂艺术区", "type": "文化", "tags": ["文艺", "网红"],
         "lat": 25.6814, "lng": 100.1611, "rating": 4.0, "cost": 0,
         "duration_min": 60, "couple_score": 7.5, "indoor": True,
         "description": "大理古城内的文创艺术区，有画廊、手作市集和精酿酒吧。"},
        {"name": "大理市博物馆", "type": "文化", "tags": ["文化"],
         "lat": 25.6783, "lng": 100.1582, "rating": 4.1, "cost": 0,
         "duration_min": 60, "couple_score": 5.0, "indoor": True,
         "description": "了解大理历史文化的窗口，馆藏南诏大理国时期文物。"},
    ],
    "丽江": [
        {"name": "丽江古城", "type": "人文", "tags": ["浪漫", "文艺", "网红"],
         "lat": 26.8721, "lng": 100.2299, "rating": 4.7, "cost": 0,
         "duration_min": 180, "couple_score": 9.2, "indoor": False,
         "description": "世界文化遗产，小桥流水人家，夜晚灯笼亮起格外浪漫。"},
        {"name": "玉龙雪山", "type": "自然", "tags": ["自然", "浪漫"],
         "lat": 27.0983, "lng": 100.1753, "rating": 4.8, "cost": 230,
         "duration_min": 240, "couple_score": 9.5, "indoor": False,
         "description": "纳西族神山，乘大索道到达海拔4506米冰川公园，看云海日出。"},
        {"name": "束河古镇", "type": "人文", "tags": ["文艺"],
         "lat": 26.9243, "lng": 100.2070, "rating": 4.4, "cost": 0,
         "duration_min": 90, "couple_score": 8.0, "indoor": False,
         "description": "比大研古城更安静的古镇，马车铃铛声中有慢时光的味道。"},
        {"name": "泸沽湖", "type": "自然", "tags": ["浪漫", "自然"],
         "lat": 27.7244, "lng": 100.7832, "rating": 4.6, "cost": 70,
         "duration_min": 480, "couple_score": 9.8, "indoor": False,
         "description": "摩梭人的母亲湖，乘猪槽船游湖，走婚桥上看日出，是情侣必去之地。"},
        {"name": "木府", "type": "文化", "tags": ["文化"],
         "lat": 26.8728, "lng": 100.2345, "rating": 4.3, "cost": 60,
         "duration_min": 90, "couple_score": 6.0, "indoor": True,
         "description": "丽江土司府邸，有'北有故宫，南有木府'之说。"},
        {"name": "白沙壁画", "type": "文化", "tags": ["文化", "文艺"],
         "lat": 26.9576, "lng": 100.2151, "rating": 4.1, "cost": 30,
         "duration_min": 60, "couple_score": 6.5, "indoor": True,
         "description": "明代壁画珍品，融合汉、藏、纳西族艺术风格。"},
    ],
    "三亚": [
        {"name": "亚龙湾", "type": "自然", "tags": ["浪漫", "自然"],
         "lat": 18.2265, "lng": 109.6475, "rating": 4.8, "cost": 0,
         "duration_min": 180, "couple_score": 9.5, "indoor": False,
         "description": "天下第一湾，沙质细腻洁白，海水清澈见底，适合情侣赤脚漫步。"},
        {"name": "蜈支洲岛", "type": "自然", "tags": ["浪漫", "自然", "网红"],
         "lat": 18.3117, "lng": 109.7608, "rating": 4.7, "cost": 144,
         "duration_min": 360, "couple_score": 9.3, "indoor": False,
         "description": "三亚最美海岛，潜水、摩托艇、沙滩午餐，非常适合情侣一日游。"},
        {"name": "天涯海角", "type": "自然", "tags": ["浪漫"],
         "lat": 18.2894, "lng": 109.3468, "rating": 4.5, "cost": 81,
         "duration_min": 120, "couple_score": 9.0, "indoor": False,
         "description": "天涯石和海角石象征爱情永恒，三亚必打卡的情侣地标。"},
        {"name": "南山文化旅游区", "type": "文化", "tags": ["文化"],
         "lat": 18.3147, "lng": 109.2004, "rating": 4.4, "cost": 129,
         "duration_min": 180, "couple_score": 6.5, "indoor": False,
         "description": "108米南海观音像矗立海中，气势恢宏。"},
        {"name": "三亚千古情", "type": "文化", "tags": ["文艺"],
         "lat": 18.2764, "lng": 109.5121, "rating": 4.3, "cost": 280,
         "duration_min": 120, "couple_score": 7.5, "indoor": True,
         "description": "大型室内歌舞秀，讲述三亚千年历史，视觉震撼。"},
        {"name": "三亚免税城", "type": "网红", "tags": ["网红"],
         "lat": 18.3176, "lng": 109.7181, "rating": 4.2, "cost": 0,
         "duration_min": 120, "couple_score": 7.0, "indoor": True,
         "description": "海棠湾国际免税城，品牌齐全，适合情侣逛街购物。"},
    ],
    "杭州": [
        {"name": "西湖", "type": "自然", "tags": ["浪漫", "自然"],
         "lat": 30.2435, "lng": 120.1495, "rating": 4.9, "cost": 0,
         "duration_min": 240, "couple_score": 10.0, "indoor": False,
         "description": "许仙白娘子的故事发生地，断桥残雪、雷峰夕照，步步都是爱情传说。"},
        {"name": "灵隐寺", "type": "文化", "tags": ["文化"],
         "lat": 30.2415, "lng": 120.0995, "rating": 4.6, "cost": 75,
         "duration_min": 120, "couple_score": 7.5, "indoor": False,
         "description": "千年古刹，深山藏古寺，求姻缘很灵验。"},
        {"name": "龙井村", "type": "自然", "tags": ["文艺", "自然"],
         "lat": 30.2209, "lng": 120.1111, "rating": 4.4, "cost": 0,
         "duration_min": 120, "couple_score": 8.0, "indoor": False,
         "description": "茶园漫步，品一盏明前龙井，山间清风和茶香是另一种浪漫。"},
    ],
    "成都": [
        {"name": "宽窄巷子", "type": "人文", "tags": ["文艺", "网红"],
         "lat": 30.6656, "lng": 104.0504, "rating": 4.5, "cost": 0,
         "duration_min": 120, "couple_score": 8.0, "indoor": False,
         "description": "老成都的院落文化，喝茶、掏耳朵、看川剧变脸，巴适得很。"},
        {"name": "大熊猫繁育基地", "type": "自然", "tags": ["自然", "网红"],
         "lat": 30.7371, "lng": 104.1441, "rating": 4.7, "cost": 58,
         "duration_min": 180, "couple_score": 8.5, "indoor": False,
         "description": "看滚滚卖萌是情侣约会最治愈的选择，记得早上去，熊猫更活跃。"},
        {"name": "锦里古街", "type": "人文", "tags": ["文艺", "网红"],
         "lat": 30.6468, "lng": 104.0448, "rating": 4.4, "cost": 0,
         "duration_min": 90, "couple_score": 7.5, "indoor": False,
         "description": "三国文化主题古街，夜晚灯笼亮起很有氛围，吃喝玩乐一条龙。"},
    ],
}


def _match_city(city: str) -> Optional[str]:
    for key in _MOCK_POI:
        if key in city or city in key:
            return key
    return None


def _filter_by_prefs(pois: list, preferences: str) -> list:
    """Filter POIs by comma-separated preference tags."""
    if not preferences:
        return pois
    tags = [t.strip() for t in preferences.replace("，", ",").split(",")]
    scored = []
    for poi in pois:
        score = sum(2 for t in tags if t in poi.get("tags", []))
        scored.append((score, poi))
    scored.sort(key=lambda x: (-x[0], -x[1].get("couple_score", 0)))
    return [p for _, p in scored]


# ── LangChain Tool ───────────────────────────────────────────────

@tool
def poi_search_tool(city: str, preferences: str = "") -> str:
    """搜索指定城市的景点，按情侣旅行偏好筛选和排序。

    参数:
        city: 城市名称，如"大理"、"三亚"、"杭州"
        preferences: 偏好标签，逗号分隔。可选值：浪漫, 自然, 文艺, 网红, 文化
                     留空则返回全部景点。

    返回:
        JSON数组字符串，每个景点包含名称、类型、坐标、建议时长、情侣推荐指数(1-10)、
        预估花费、室内/室外标记和简短描述。
    """
    city_key = _match_city(city)

    if city_key:
        pois = [dict(p) for p in _MOCK_POI[city_key]]
    else:
        # Generic fallback for unknown cities
        pois = [
            {"name": f"{city}城市公园", "type": "自然", "tags": ["自然", "浪漫"],
             "lat": 0.0, "lng": 0.0, "rating": 4.3, "cost": 0,
             "duration_min": 90, "couple_score": 7.0, "indoor": False,
             "description": f"{city}的城市绿地，适合散步和放松。"},
            {"name": f"{city}博物馆", "type": "文化", "tags": ["文化"],
             "lat": 0.0, "lng": 0.0, "rating": 4.0, "cost": 0,
             "duration_min": 90, "couple_score": 5.5, "indoor": True,
             "description": f"了解{city}历史文化的最佳去处。"},
            {"name": f"{city}老街", "type": "人文", "tags": ["文艺"],
             "lat": 0.0, "lng": 0.0, "rating": 4.1, "cost": 0,
             "duration_min": 60, "couple_score": 6.5, "indoor": False,
             "description": f"{city}保存最完好的老街区，有特色小吃和手工艺品。"},
            {"name": f"{city}购物中心", "type": "网红", "tags": ["网红"],
             "lat": 0.0, "lng": 0.0, "rating": 4.0, "cost": 0,
             "duration_min": 120, "couple_score": 6.0, "indoor": True,
             "description": f"{city}最大的商业综合体，适合逛街和用餐。"},
        ]

    if preferences:
        pois = _filter_by_prefs(pois, preferences)

    return json.dumps(pois, ensure_ascii=False)
