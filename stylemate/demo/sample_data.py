import json
from datetime import datetime
from pathlib import Path

from stylemate.domain.models import Garment

_SAMPLE_GARMENTS = [
    ("sample-shirt-white", "白色衬衫", "上装", "白色", ["通勤", "简约"], 0),
    ("sample-jeans-blue", "浅蓝牛仔裤", "下装", "浅蓝", ["休闲", "简约"], 32),
    ("sample-trench-beige", "米色风衣", "外套", "米色", ["通勤", "简约"], 56),
    ("sample-loafers-black", "黑色乐福鞋", "鞋履", "黑色", ["通勤"], 92),
    ("sample-cardigan-cream", "奶油色针织开衫", "上装", "奶油色", ["温柔", "休闲"], 30),
    ("sample-skirt-gray", "深灰半身裙", "下装", "深灰", ["通勤", "优雅"], 40),
]
_SAMPLE_CREATED_AT = datetime(2024, 1, 1)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST_PATH = _PROJECT_ROOT / "assets" / "demo" / "wardrobe.json"


def sample_garments() -> list[Garment]:
    records = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))["garments"]
    return [
        Garment(
            id=garment_id,
            name=name,
            category=category,
            primary_color=color,
            seasons=["春", "秋"],
            styles=styles,
            image_ref=str(_MANIFEST_PATH.parent / "garments" / records[image_index]["image"]),
            source="sample",
            created_at=_SAMPLE_CREATED_AT,
        )
        for garment_id, name, category, color, styles, image_index in _SAMPLE_GARMENTS
    ]

