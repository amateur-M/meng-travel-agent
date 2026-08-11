"""search_food — Search for restaurants near destination.

M1 placeholder: returns curated mock restaurant data.
M2 will replace this with a real map API (高德 / Google Maps).
"""

from typing import Dict, Any, List

from agents.state import AgentState


_MOCK_FOOD: Dict[str, List[dict]] = {
    "大理": [
        {"name": "段公子餐厅", "cuisine": "云南菜", "rating": 4.6,
         "avg_cost": 80, "location": "大理古城人民路"},
        {"name": "再回首凉鸡米线", "cuisine": "小吃", "rating": 4.5,
         "avg_cost": 20, "location": "大理古城"},
        {"name": "喜洲粑粑", "cuisine": "小吃", "rating": 4.4,
         "avg_cost": 15, "location": "喜洲镇"},
        {"name": "酸辣鱼庄", "cuisine": "云南菜", "rating": 4.3,
         "avg_cost": 60, "location": "洱海边"},
        {"name": "乳扇小摊", "cuisine": "小吃", "rating": 4.2,
         "avg_cost": 10, "location": "大理古城"},
        {"name": "花时间私房菜", "cuisine": "创意菜", "rating": 4.7,
         "avg_cost": 120, "location": "大理古城"},
        {"name": "88号西点屋", "cuisine": "甜品", "rating": 4.4,
         "avg_cost": 50, "location": "大理古城博爱路"},
    ],
    "丽江": [
        {"name": "阿妈腊排骨", "cuisine": "云南菜", "rating": 4.5,
         "avg_cost": 70, "location": "丽江古城"},
        {"name": "88号小吃店", "cuisine": "小吃", "rating": 4.4,
         "avg_cost": 30, "location": "丽江古城"},
        {"name": "东巴谷野菌火锅", "cuisine": "火锅", "rating": 4.6,
         "avg_cost": 100, "location": "丽江市区"},
        {"name": "雪山鱼庄", "cuisine": "云南菜", "rating": 4.3,
         "avg_cost": 80, "location": "玉龙县"},
    ],
    "三亚": [
        {"name": "第一市场海鲜", "cuisine": "海鲜", "rating": 4.5,
         "avg_cost": 150, "location": "三亚第一市场"},
        {"name": "椰子鸡", "cuisine": "海南菜", "rating": 4.4,
         "avg_cost": 80, "location": "三亚市区"},
        {"name": "抱罗粉", "cuisine": "小吃", "rating": 4.3,
         "avg_cost": 20, "location": "三亚市区"},
        {"name": "清补凉", "cuisine": "甜品", "rating": 4.5,
         "avg_cost": 15, "location": "三亚各夜市"},
    ],
}


def search_food(state: AgentState) -> Dict[str, Any]:
    """Search restaurants for the given destination.

    M1: returns pre-curated mock data.
    M2: replaces with live map API + preference filtering.

    Returns:
        Partial state with food_list populated.
    """
    params = state.get("parsed_params", {})
    destination = params.get("destination", "")

    candidates = []
    for key, foods in _MOCK_FOOD.items():
        if key in destination or destination in key:
            candidates = foods
            break

    if not candidates:
        candidates = [
            {"name": f"{destination}本地餐厅", "cuisine": "本地菜", "rating": 4.3,
             "avg_cost": 60, "location": f"{destination}市区"},
            {"name": f"{destination}小吃街", "cuisine": "小吃", "rating": 4.2,
             "avg_cost": 25, "location": f"{destination}市区"},
        ]

    return {
        "food_list": candidates,
        "current_phase": "search_food",
    }
