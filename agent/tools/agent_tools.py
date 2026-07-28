import os
import re
from typing import Tuple

import requests
from langchain_core.tools import tool
from rag.rag_service import RagSummarizeService

rag = None


def _get_rag_service() -> RagSummarizeService:
    global rag
    if rag is None:
        rag = RagSummarizeService()
    return rag


SIZE_RULES = [
    {"min_h": 155, "max_h": 165, "min_kg": 37.5, "max_kg": 47.5, "size": "S"},
    {"min_h": 160, "max_h": 170, "min_kg": 45.0, "max_kg": 57.5, "size": "M"},
    {"min_h": 165, "max_h": 175, "min_kg": 57.5, "max_kg": 67.5, "size": "L"},
    {"min_h": 170, "max_h": 178, "min_kg": 65.0, "max_kg": 75.0, "size": "XL"},
    {"min_h": 175, "max_h": 182, "min_kg": 72.5, "max_kg": 82.5, "size": "2XL"},
    {"min_h": 178, "max_h": 185, "min_kg": 80.0, "max_kg": 90.0, "size": "3XL"},
    {"min_h": 180, "max_h": 190, "min_kg": 90.0, "max_kg": 105.0, "size": "4XL"},
    {"min_h": 190, "max_h": 300, "min_kg": 105.0, "max_kg": 200.0, "size": "5XL"},
]

SIZE_ORDER = ["S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL"]


@tool
def rag_summarize(query: str) -> str:
    """从向量存储中检索衣橱知识库资料。"""
    return _get_rag_service().rag_summarize(query)


def _get_amap_key() -> str:
    return os.getenv("AMAP_API_KEY") or os.getenv("GAODE_API_KEY", "")


def _amap_get(path: str, params: dict) -> Tuple[dict | None, str]:
    key = _get_amap_key()
    if not key:
        return None, "缺少 AMAP_API_KEY 配置"

    url = f"https://restapi.amap.com/v3/{path}"
    payload = {"key": key, **params}
    try:
        resp = requests.get(url, params=payload, timeout=6)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "1":
            return None, data.get("info", "高德接口返回异常")
        return data, ""
    except Exception as exc:
        return None, str(exc)


def _amap_ip_location() -> Tuple[dict | None, str]:
    data, err = _amap_get("ip", {})
    if err:
        return None, err
    return {
        "city": data.get("city", ""),
        "province": data.get("province", ""),
        "adcode": data.get("adcode", ""),
    }, ""


def resolve_user_city() -> str:
    loc, err = _amap_ip_location()
    if err:
        return ""
    return loc.get("city") or loc.get("province") or ""


def fetch_weather_text(city: str) -> str:
    city_input = (city or "").strip()
    if not city_input:
        loc, err = _amap_ip_location()
        if err:
            return f"天气查询失败：{err}"
        city_input = loc.get("adcode") or loc.get("city") or loc.get("province")

    if not city_input:
        return "未获取到有效城市信息，请提供城市名称或城市编码。"

    data, err = _amap_get(
        "weather/weatherInfo",
        {"city": city_input, "extensions": "all", "output": "JSON"},
    )
    if err:
        return f"天气查询失败：{err}"

    lives = data.get("lives", [])
    if lives:
        live = lives[0]
        return (
            f"{live.get('city', city_input)}：{live.get('weather', '-')}\n"
            f"气温{live.get('temperature', '-')}°C，湿度{live.get('humidity', '-')}%，"
            f"{live.get('winddirection', '-')}风{live.get('windpower', '-')}级，"
            f"发布时间{live.get('reporttime', '-')}。"
        )

    forecasts = data.get("forecasts", [])
    if not forecasts:
        return "天气查询失败：未返回实时或预报天气。"

    casts = forecasts[0].get("casts", [])
    if not casts:
        return "天气查询失败：未返回预报天气。"

    lines = []
    for cast in casts[:3]:
        date = cast.get("date", "-")
        day_weather = cast.get("dayweather", "-")
        night_weather = cast.get("nightweather", "-")
        day_temp = cast.get("daytemp", "-")
        night_temp = cast.get("nighttemp", "-")
        day_wind = cast.get("daywind", "-")
        day_power = cast.get("daypower", "-")
        lines.append(
            f"{date} {day_weather}/{night_weather} {day_temp}~{night_temp}°C {day_wind}风{day_power}级"
        )

    return "预报天气：\n" + "\n".join(lines)


@tool
def get_weather(city: str) -> str:
    """获取指定城市的天气（高德天气），以字符串返回。"""
    return fetch_weather_text(city)


@tool
def get_user_location() -> str:
    """获取用户所在城市名称（高德定位），以字符串返回。"""
    city = resolve_user_city()
    return city or "定位失败"


def _shift_size(size: str, fit_preference: str) -> str:
    if not fit_preference:
        return size

    shift = 0
    if "宽松" in fit_preference or "偏松" in fit_preference:
        shift = 1
    if "修身" in fit_preference or "偏紧" in fit_preference:
        shift = -1

    try:
        idx = SIZE_ORDER.index(size)
    except ValueError:
        return size

    idx = max(0, min(len(SIZE_ORDER) - 1, idx + shift))
    return SIZE_ORDER[idx]


def _match_size(height_cm: float, weight_kg: float) -> str:
    for rule in SIZE_RULES:
        if rule["min_h"] <= height_cm <= rule["max_h"] and rule["min_kg"] <= weight_kg <= rule["max_kg"]:
            return rule["size"]

    best_rule = min(
        SIZE_RULES,
        key=lambda r: abs(weight_kg - (r["min_kg"] + r["max_kg"]) / 2),
    )
    return best_rule["size"]


def _parse_number(text: str) -> float | None:
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _parse_height_cm(height_input: str) -> float | None:
    text = str(height_input).strip().lower()
    value = _parse_number(text)
    if value is None:
        return None

    if "cm" in text or "厘米" in text:
        return value
    if "m" in text or "米" in text:
        return value * 100 if value < 10 else value

    if value < 3:
        return value * 100
    return value


def _parse_weight_kg(weight_input: str) -> Tuple[float | None, str]:
    text = str(weight_input).strip().lower()
    value = _parse_number(text)
    if value is None:
        return None, ""

    if "斤" in text:
        return value * 0.5, "已按斤换算"
    if "kg" in text or "公斤" in text or "千克" in text:
        return value, ""

    if value >= 150:
        return value * 0.5, "未标注单位，按斤换算"

    return value, "未标注单位，按kg处理"


@tool
def recommend_size(height: str, weight: str, fit_preference: str = "") -> str:
    """根据身高体重推荐尺码（支持斤/公斤自动换算）。"""
    height_cm = _parse_height_cm(height)
    weight_kg, weight_note = _parse_weight_kg(weight)

    if height_cm is None or weight_kg is None:
        return "请提供有效的身高和体重，例如：165cm、52kg 或 104斤。"

    if not 120 <= height_cm <= 230:
        return "身高范围异常，请确认输入是否为厘米或米（例如 165cm 或 1.65m）。"
    if not 30 <= weight_kg <= 200:
        return "体重范围异常，请确认输入是否为公斤或斤（例如 52kg 或 104斤）。"

    base_size = _match_size(height_cm, weight_kg)
    final_size = _shift_size(base_size, fit_preference)
    note = f"，{weight_note}" if weight_note else ""

    return (
        f"推荐尺码：{final_size}。"
        f"(身高{height_cm:.0f}cm，体重{weight_kg:.1f}kg{note}，"
        f"偏好：{fit_preference or '标准'})\n"
        "建议仍以具体品牌尺码表为准。"
    )


@tool
def recommend_outfit(scene: str, style: str, season: str, color_preference: str = "") -> str:
    """根据场景、风格、季节和色彩偏好推荐穿搭。"""
    scene = (scene or "日常").strip()
    style = (style or "简约").strip()
    season = (season or "春秋").strip()
    if season.endswith("季"):
        season = season.replace("季", "")
    color_preference = (color_preference or "中性色").strip()

    scene_map = {
        "通勤": ("衬衫/针织上衣", "直筒西裤/半裙", "乐福鞋/低跟鞋", "简洁托特包"),
        "约会": ("柔和上衣", "高腰半裙/直筒裤", "玛丽珍/短靴", "精致小包"),
        "出游": ("功能外套/卫衣", "直筒牛仔/工装裤", "运动鞋", "轻量双肩包"),
        "运动": ("速干上衣", "运动紧身/短裤", "跑鞋", "吸汗帽"),
    }

    style_map = {
        "简约": "选择线条干净、版型利落的单品，控制颜色数量。",
        "甜美": "加入浅色系与小面积点缀配饰。",
        "通勤": "突出干净利落的廓形与质感面料。",
        "街头": "可用宽松版型与层次叠穿。",
        "运动": "强调功能性与舒适度。",
    }

    season_map = {
        "春": "外搭轻薄风衣/针织开衫，注意昼夜温差。",
        "夏": "选择透气面料与浅色系，减少层次。",
        "秋": "外搭夹克/薄呢外套，层次清晰。",
        "冬": "选择保暖内层+羽绒/大衣，注意保暖与活动度。",
        "春秋": "薄外套+内搭，兼顾温度与质感。",
    }

    top, bottom, shoes, acc = scene_map.get(scene, ("基础上衣", "直筒下装", "休闲鞋", "简洁包"))
    style_note = style_map.get(style, "保持整体风格统一，避免过多元素冲突。")
    season_note = season_map.get(season, "根据温度增减层次。")

    return (
        f"场景：{scene} | 风格：{style} | 季节：{season}\n"
        f"- 上装：{top}\n"
        f"- 下装：{bottom}\n"
        f"- 鞋履：{shoes}\n"
        f"- 配饰：{acc}\n"
        f"- 颜色建议：{color_preference}\n"
        f"- 风格提示：{style_note}\n"
        f"- 季节提示：{season_note}"
    )


@tool
def care_guide(material: str) -> str:
    """根据材质给出洗护建议。"""
    key = (material or "").strip().lower()
    guides = {
        "棉": "水温<=30C，中性洗涤剂，反面清洗，阴干。",
        "牛仔": "翻面洗，减少频繁清洗，避免暴晒。",
        "羊毛": "优先干洗，手洗用羊毛洗涤剂，平铺晾干。",
        "羊绒": "低温手洗或干洗，平铺阴干，防虫蛀收纳。",
        "真丝": "优先干洗，轻柔手洗，避免暴晒与拧绞。",
        "羽绒": "使用羽绒专用洗涤剂，充分漂洗，轻拍恢复蓬松。",
        "麻": "水温<=30C，轻柔清洗，熨烫前先湿润。",
        "雪纺": "手洗优先，轻柔按压，阴干避免勾丝。",
    }

    for k, v in guides.items():
        if k in key:
            return v

    return _get_rag_service().rag_summarize(f"{material} 洗涤 养护 注意事项")


@tool
def wardrobe_gap_check(items: str, season: str = "") -> str:
    """根据已有单品清单给出衣橱缺口提醒。"""
    if not items:
        return "请提供已有单品清单，例如：白衬衫、牛仔裤、运动鞋。"

    season = season or "通用"
    if season.endswith("季"):
        season = season.replace("季", "")
    item_list = [x.strip() for x in re.split(r"[，,;；/\n]", items) if x.strip()]

    basics = {
        "通用": ["白衬衫", "基础T恤", "直筒裤", "牛仔裤", "休闲鞋"],
        "春": ["风衣", "薄针织", "浅色外套"],
        "夏": ["短袖T恤", "轻薄短裤", "凉鞋"],
        "秋": ["夹克", "针织衫", "长裤"],
        "冬": ["羽绒服", "保暖内衣", "短靴"],
    }

    need = basics.get(season, basics["通用"])
    missing = [b for b in need if not any(b in item for item in item_list)]

    if not missing:
        return f"{season}季基础单品已较完整。可考虑升级版型或颜色丰富度。"

    return f"{season}季建议补齐：" + "、".join(missing)


@tool
def item_style_analysis(description: str) -> str:
    """根据衣物描述进行风格和版型标签分析。"""
    if not description:
        return "请提供衣物描述，如：短款牛仔外套、廓形、浅蓝。"

    tags = []
    mapping = {
        "牛仔": "休闲",
        "西装": "通勤",
        "针织": "温柔",
        "廓形": "韩系",
        "短款": "利落",
        "长款": "优雅",
        "运动": "运动",
        "工装": "街头",
    }

    for k, v in mapping.items():
        if k in description:
            tags.append(v)

    if not tags:
        tags.append("简约")

    return f"风格标签：{', '.join(sorted(set(tags)))}。建议围绕该风格搭配基础色与同风格单品。"


