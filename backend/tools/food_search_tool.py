"""Food Search Tool — LangChain-compatible restaurant discovery.

Returns curated restaurant recommendations with atmosphere tags for couples.
Uses local mock data; API interface reserved for future (Amap / Google Places).
"""

import json
from typing import Optional

from langchain_core.tools import tool


# ── Rich mock restaurant database ─────────────────────────────────

_MOCK_FOOD: dict = {
    "大理": [
        {"name": "古城人家", "cuisine": "白族菜", "avg_cost": 80,
         "atmosphere": ["本地老店", "庭院用餐"],
         "rating": 4.6, "couple_score": 8.5,
         "description": "白族庭院里的私房菜，酸辣鱼和乳扇是招牌，环境安静有格调。"},
        {"name": "洱海边·落日餐厅", "cuisine": "融合菜", "avg_cost": 150,
         "atmosphere": ["浪漫烛光", "景观位"],
         "rating": 4.5, "couple_score": 9.5,
         "description": "洱海边的玻璃房餐厅，落日时分金色的湖面是最佳背景，需要提前预定。"},
        {"name": "喜洲粑粑老店", "cuisine": "白族小吃", "avg_cost": 25,
         "atmosphere": ["本地老店"],
         "rating": 4.4, "couple_score": 6.0,
         "description": "喜洲古镇最有名的破酥粑粑，炭火烤制，咸甜两种口味都值得尝试。"},
        {"name": "人民路小馆", "cuisine": "创意云南菜", "avg_cost": 100,
         "atmosphere": ["网红打卡", "文艺"],
         "rating": 4.3, "couple_score": 8.0,
         "description": "古城人民路上的网红餐厅，鲜花入菜是特色，拍照很出片。"},
        {"name": "双廊海景火锅", "cuisine": "火锅", "avg_cost": 120,
         "atmosphere": ["景观位", "浪漫烛光"],
         "rating": 4.4, "couple_score": 8.5,
         "description": "面朝洱海吃菌子火锅，晚风吹过时氛围感拉满。"},
        {"name": "寂照庵斋饭", "cuisine": "素食", "avg_cost": 20,
         "atmosphere": ["文艺", "宁静"],
         "rating": 4.7, "couple_score": 8.0,
         "description": "苍山上的尼姑庵，多肉植物花园里的斋饭，清淡却令人难忘。"},
    ],
    "丽江": [
        {"name": "阿婆腊排骨", "cuisine": "纳西菜", "avg_cost": 70,
         "atmosphere": ["本地老店"],
         "rating": 4.6, "couple_score": 7.0,
         "description": "丽江最有名腊排骨火锅，汤底浓郁，肉香四溢，需排队。"},
        {"name": "雪山下的帐篷餐厅", "cuisine": "西餐", "avg_cost": 200,
         "atmosphere": ["浪漫烛光", "景观位", "网红打卡"],
         "rating": 4.5, "couple_score": 9.5,
         "description": "白沙古镇旁的野奢帐篷餐厅，正对玉龙雪山，晚餐时雪山被夕阳染成金色。"},
        {"name": "88号小吃店", "cuisine": "纳西小吃", "avg_cost": 35,
         "atmosphere": ["本地老店"],
         "rating": 4.5, "couple_score": 6.5,
         "description": "古城内排队最长的鸡豆凉粉店，味道正宗，性价比极高。"},
        {"name": "束河咖啡馆", "cuisine": "西式简餐", "avg_cost": 60,
         "atmosphere": ["文艺", "宁静"],
         "rating": 4.2, "couple_score": 8.0,
         "description": "束河古镇里的阳光玻璃房，brunch和手冲咖啡都很棒。"},
    ],
    "三亚": [
        {"name": "第一市场海鲜", "cuisine": "海鲜", "avg_cost": 150,
         "atmosphere": ["本地老店"],
         "rating": 4.4, "couple_score": 7.0,
         "description": "三亚最有烟火气的海鲜市场，自选海鲜后交由店家加工，新鲜实惠。"},
        {"name": "海底餐厅", "cuisine": "西餐", "avg_cost": 400,
         "atmosphere": ["浪漫烛光", "网红打卡", "私密包厢"],
         "rating": 4.6, "couple_score": 10.0,
         "description": "亚特兰蒂斯海底餐厅，用餐时有魔鬼鱼和鲨鱼游过头顶，极致浪漫体验。"},
        {"name": "椰子鸡·椰语堂", "cuisine": "海南菜", "avg_cost": 80,
         "atmosphere": ["网红打卡"],
         "rating": 4.3, "couple_score": 7.5,
         "description": "现砍椰子做汤底的文昌鸡火锅，清甜鲜美，三亚必吃。"},
        {"name": "天涯海角日落吧", "cuisine": "酒吧/简餐", "avg_cost": 100,
         "atmosphere": ["景观位", "浪漫烛光"],
         "rating": 4.3, "couple_score": 9.0,
         "description": "天涯海角景区旁的沙滩吧，躺椅上喝椰汁看日落，浪漫到极致。"},
    ],
    "杭州": [
        {"name": "楼外楼", "cuisine": "杭帮菜", "avg_cost": 200,
         "atmosphere": ["景观位", "本地老店"],
         "rating": 4.5, "couple_score": 8.5,
         "description": "西湖边百年老店，东坡肉和西湖醋鱼是招牌，二楼窗边可赏湖景。"},
        {"name": "绿茶餐厅（龙井路）", "cuisine": "创意杭帮菜", "avg_cost": 90,
         "atmosphere": ["文艺", "网红打卡"],
         "rating": 4.3, "couple_score": 8.0,
         "description": "龙井茶园中的餐厅，小桥流水，环境清幽，性价比高。"},
        {"name": "新白鹿餐厅", "cuisine": "杭帮菜", "avg_cost": 60,
         "atmosphere": ["本地老店"],
         "rating": 4.4, "couple_score": 7.0,
         "description": "本地人最爱的平价杭帮菜，糖醋里脊和蛋黄鸡翅是必点。"},
        {"name": "湖畔居茶楼", "cuisine": "茶点", "avg_cost": 88,
         "atmosphere": ["景观位", "文艺", "宁静"],
         "rating": 4.5, "couple_score": 9.0,
         "description": "西湖边的百年茶楼，一壶龙井配几碟茶点，看湖光山色，消磨一下午。"},
    ],
    "成都": [
        {"name": "小龙坎火锅", "cuisine": "火锅", "avg_cost": 100,
         "atmosphere": ["网红打卡"],
         "rating": 4.5, "couple_score": 7.5,
         "description": "成都火锅扛把子，牛油红锅麻辣鲜香，等位时可以看川剧变脸。"},
        {"name": "玉林路小酒馆", "cuisine": "酒吧/简餐", "avg_cost": 80,
         "atmosphere": ["文艺", "网红打卡"],
         "rating": 4.3, "couple_score": 8.5,
         "description": "赵雷《成都》里唱的小酒馆就在这里，民谣和精酿是标配。"},
        {"name": "陈麻婆豆腐", "cuisine": "川菜", "avg_cost": 60,
         "atmosphere": ["本地老店"],
         "rating": 4.4, "couple_score": 7.0,
         "description": "百年老字号，麻婆豆腐的发源地，价格亲民味道正宗。"},
        {"name": "太古里·翠园", "cuisine": "粤菜/点心", "avg_cost": 180,
         "atmosphere": ["私密包厢", "浪漫烛光"],
         "rating": 4.6, "couple_score": 9.0,
         "description": "太古里顶层的精致粤菜，环境优雅私密，适合重要的晚餐约会。"},
    ],
}


def _match_city(city: str) -> Optional[str]:
    for key in _MOCK_FOOD:
        if key in city or city in key:
            return key
    return None


def _filter_and_score(restaurants: list, cuisine: str, budget_per_person: float) -> list:
    """Filter by budget (strict) and cuisine (soft score boost), then sort by couple_score."""
    # Strict budget filter
    if budget_per_person > 0:
        restaurants = [r for r in restaurants if r["avg_cost"] <= budget_per_person]

    # Score by cuisine match and couple_score
    scored = []
    for r in restaurants:
        score = 0.0
        if cuisine and cuisine != "不限":
            if cuisine in r["cuisine"] or r["cuisine"] in cuisine:
                score += 3
            broad_map = {
                "中餐": ["川菜", "杭帮菜", "粤菜", "白族菜", "纳西菜", "海南菜", "云南菜", "素食"],
                "西餐": ["西餐", "融合菜", "西式简餐"],
                "火锅": ["火锅"],
                "小吃": ["小吃"],
                "海鲜": ["海鲜"],
            }
            for broad, specifics in broad_map.items():
                if cuisine in (broad,) and r["cuisine"] in specifics:
                    score += 2
        scored.append((score + r.get("couple_score", 5) / 10, r))
    scored.sort(key=lambda x: -x[0])
    return [r for _, r in scored]


# ── LangChain Tool ───────────────────────────────────────────────

@tool
def food_search_tool(city: str, cuisine: str = "不限", budget_per_person: float = 0.0) -> str:
    """Search for restaurants in a city, filterable by cuisine and per-person budget.

    Args:
        city: City name (Chinese), e.g. "大理", "成都", "三亚".
        cuisine: Cuisine preference, e.g. "中餐", "火锅", "西餐", "海鲜", "不限".
        budget_per_person: Per-person budget ceiling (yuan). 0 = no limit.

    Returns:
        JSON array of restaurants with name, cuisine, avg_cost, atmosphere tags,
        rating, and couple_score.
    """
    city_key = _match_city(city)

    if city_key:
        restaurants = [dict(r) for r in _MOCK_FOOD[city_key]]
    else:
        restaurants = [
            {"name": f"{city}本地菜馆", "cuisine": "本地菜", "avg_cost": 80,
             "atmosphere": ["本地老店"], "rating": 4.0, "couple_score": 6.5,
             "description": f"{city}最受欢迎的本地菜馆。"},
            {"name": f"{city}景观餐厅", "cuisine": "融合菜", "avg_cost": 120,
             "atmosphere": ["景观位", "浪漫烛光"], "rating": 4.2, "couple_score": 7.5,
             "description": f"{city}视野最好的餐厅，适合约会。"},
            {"name": f"{city}夜市小吃", "cuisine": "小吃", "avg_cost": 30,
             "atmosphere": ["本地老店"], "rating": 4.1, "couple_score": 6.0,
             "description": f"{city}最热闹的夜市，各种地道小吃应有尽有。"},
        ]

    filtered = _filter_and_score(restaurants, cuisine, budget_per_person)
    return json.dumps(filtered, ensure_ascii=False)
