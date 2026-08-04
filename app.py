"""StyleMate: a demo-first, inventory-grounded wardrobe workbench."""

import json
import uuid
from pathlib import Path
from urllib.parse import quote

import streamlit as st
from dotenv import load_dotenv
from pydantic import ValidationError

from config.runtime import RuntimeSettings
from domain.models import Garment, OutfitRecommendation, OutfitRequest
from ui.components import (
    inject_style,
    render_empty_state,
    render_garment_card,
    render_outfit_card,
    render_trace,
)
from ui.state import (
    AppContext,
    build_context,
    delete_garment,
    load_sample_wardrobe,
    validated_garment_update,
)


load_dotenv()
st.set_page_config(page_title="StyleMate 衣橱管家", page_icon="👔", layout="wide")
inject_style()


def _labels(value: str) -> list[str]:
    return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]


def _image_value(context: AppContext, garment: Garment):
    if not garment.image_ref:
        return None
    if garment.image_ref.startswith("demo/"):
        project_root = Path(__file__).resolve().parent
        sample_path = (project_root / garment.image_ref).resolve()
        try:
            sample_path.relative_to(project_root)
        except ValueError:
            return None
        if sample_path.suffix.lower() == ".svg" and sample_path.is_file():
            svg_text = sample_path.read_text(encoding="utf-8")
            return f"data:image/svg+xml;utf8,{quote(svg_text)}"
        return sample_path
    return context.image_store.read(context.owner_id, garment.image_ref)


def _draft_form(context: AppContext) -> None:
    draft = st.session_state.get("stylemate_draft")
    upload = st.session_state.get("stylemate_upload")
    if not draft or not upload:
        return

    st.subheader("确认衣物信息")
    with st.form("stylemate_confirm_garment"):
        name = st.text_input("名称", value=draft.get("name", ""))
        category = st.text_input("类别", value=draft.get("category", ""), placeholder="上装、下装、外套或鞋履")
        color = st.text_input("颜色", value=draft.get("primary_color", ""))
        material = st.text_input("材质", value=draft.get("material") or "")
        seasons = st.text_input("适用季节（逗号分隔）", value="，".join(draft.get("seasons", [])), placeholder="春、秋")
        styles = st.text_input("风格（逗号分隔）", value="，".join(draft.get("styles", [])), placeholder="通勤、简约")
        confirmed = st.form_submit_button("确认入库", type="primary")
    if not confirmed:
        return
    try:
        garment = Garment.model_validate(
            {
                **draft,
                "id": draft.get("id") or str(uuid.uuid4()),
                "name": name.strip(),
                "category": category.strip(),
                "primary_color": color.strip(),
                "material": material.strip() or None,
                "seasons": _labels(seasons),
                "styles": _labels(styles),
                "source": "manual" if draft.get("source") == "manual" else "ai",
            }
        )
        context.wardrobe_service.save_confirmed(
            context.owner_id, garment, upload["bytes"], upload["mime_type"]
        )
    except (ValidationError, ValueError) as exc:
        st.error(f"请补全有效的衣物信息：{exc}")
        return
    st.session_state.pop("stylemate_draft", None)
    st.session_state.pop("stylemate_upload", None)
    st.success("已保存到你的衣橱。")
    st.rerun()


def _today_tab(context: AppContext, garments: list[Garment]) -> None:
    st.subheader("从现有衣橱开始搭配")
    if not garments:
        render_empty_state("衣橱还是空的", "先加载样例衣橱，或在“我的衣橱”中识别一件衣物。")
        if st.button("加载样例衣橱", type="primary", key="load_samples_today"):
            count = load_sample_wardrobe(context)
            st.success(f"已添加 {count} 件样例衣物。")
            st.rerun()
        return

    with st.form("today_outfit_form"):
        scene = st.text_input("场景", value="通勤")
        city = st.text_input("城市（可选）")
        style = st.text_input("偏好风格（可选）")
        generate = st.form_submit_button("生成今日搭配", type="primary")
    if generate:
        outcome = context.outfit_skill.run(
            context.owner_id,
            OutfitRequest(scene=scene.strip() or "日常", city=city.strip() or None, style_preference=style.strip() or None),
        )
        st.session_state["stylemate_outfits"] = outcome
    outcome = st.session_state.get("stylemate_outfits")
    if outcome:
        st.info(outcome.user_message)
        by_id = {garment.id: garment for garment in garments}
        for payload in outcome.data.get("recommendations", [])[:3]:
            render_outfit_card(OutfitRecommendation.model_validate(payload), by_id)
        render_trace(outcome.trace)


def _wardrobe_tab(context: AppContext, garments: list[Garment]) -> None:
    st.subheader("我的衣橱")
    if not garments:
        render_empty_state("还没有衣物", "上传一张清晰的衣物照片，识别后确认入库。")
        if st.button("加载样例衣橱", type="primary", key="load_samples_wardrobe"):
            load_sample_wardrobe(context)
            st.rerun()
    else:
        categories = sorted({garment.category for garment in garments})
        styles = sorted({style for garment in garments for style in garment.styles})
        selected_category = st.selectbox("按类别筛选", ["全部", *categories])
        selected_style = st.selectbox("按风格筛选", ["全部", *styles])
        visible = [
            garment for garment in garments
            if (selected_category == "全部" or garment.category == selected_category)
            and (selected_style == "全部" or selected_style in garment.styles)
        ]
        for garment in visible:
            with st.container(border=True):
                render_garment_card(garment, _image_value(context, garment))
                with st.expander("编辑或删除"):
                    with st.form(f"edit_{garment.id}"):
                        name = st.text_input("名称", garment.name, key=f"name_{garment.id}")
                        category = st.text_input("类别", garment.category, key=f"category_{garment.id}")
                        color = st.text_input("颜色", garment.primary_color, key=f"color_{garment.id}")
                        material = st.text_input("材质", garment.material or "", key=f"material_{garment.id}")
                        seasons = st.text_input("适用季节", "，".join(garment.seasons), key=f"seasons_{garment.id}")
                        styles_value = st.text_input("风格", "，".join(garment.styles), key=f"styles_{garment.id}")
                        save = st.form_submit_button("保存修改")
                    if save:
                        try:
                            updated = validated_garment_update(
                                garment,
                                name=name,
                                category=category,
                                primary_color=color,
                                material=material,
                                seasons=seasons,
                                styles=styles_value,
                            )
                            context.repository.save_garment(context.owner_id, updated)
                            st.rerun()
                        except ValidationError as exc:
                            st.error(f"无法保存：{exc}")
                    if st.button("删除这件衣物", key=f"delete_{garment.id}"):
                        delete_garment(context, garment.id)
                        st.rerun()

    st.divider()
    st.subheader("新增衣物")
    uploaded = st.file_uploader("上传衣物照片", type=["jpg", "jpeg", "png", "webp"])
    note = st.text_input("补充说明（可选）", placeholder="例如：偏宽松的米色风衣")
    if uploaded and st.button("识别衣物", type="primary"):
        image_bytes = uploaded.getvalue()
        outcome = context.onboarding_skill.run(
            context.owner_id, image_bytes, uploaded.type, uploaded.name, note
        )
        st.session_state["stylemate_draft"] = outcome.data["garment"]
        st.session_state["stylemate_upload"] = {"bytes": image_bytes, "mime_type": uploaded.type}
        st.session_state["stylemate_onboarding_trace"] = outcome.trace
        st.info(outcome.user_message)
    _draft_form(context)
    if trace := st.session_state.get("stylemate_onboarding_trace"):
        render_trace(trace)


def _assistant_tab(context: AppContext, garments: list[Garment]) -> None:
    st.subheader("搭配助手")
    if not garments:
        render_empty_state("需要一点衣橱基础", "添加至少一件上装和一件下装，再生成搭配。")
        return
    with st.form("assistant_outfit_form"):
        scene = st.text_input("这次要去哪里？", value="约会")
        city = st.text_input("所在城市（可选）", key="assistant_city")
        style = st.text_input("想要的风格（可选）", key="assistant_style")
        submitted = st.form_submit_button("给我搭配建议", type="primary")
    if submitted:
        outcome = context.outfit_skill.run(
            context.owner_id,
            OutfitRequest(scene=scene.strip() or "日常", city=city.strip() or None, style_preference=style.strip() or None),
        )
        st.info(outcome.user_message)
        by_id = {garment.id: garment for garment in garments}
        for payload in outcome.data.get("recommendations", [])[:3]:
            render_outfit_card(OutfitRecommendation.model_validate(payload), by_id)
        render_trace(outcome.trace)


def _about_tab(context: AppContext) -> None:
    st.subheader("关于项目")
    st.markdown("**技术栈**：Streamlit、Pydantic、SQLite（本地模式）、DashScope 视觉识别。")
    mode_text = "演示模式仅在当前浏览器会话保存数据。" if context.settings.app_mode == "demo" else "本地模式将衣物元数据保存在本机 SQLite，图片保存在本地目录。"
    st.write(mode_text)
    st.info("隐私说明：上传图片仅用于本次识别与本地衣橱保存；页面的生成过程不会展示图片字节或 API 密钥。")
    artifact = Path("artifacts/evaluation.json")
    if not artifact.is_file():
        st.caption("评测将在发布前生成。")
        return
    try:
        metrics = json.loads(artifact.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        st.caption("评测将在发布前生成。")
        return
    rates = dict(
        list(
            (key, value)
            for key, value in metrics.items()
            if "rate" in key.lower()
        )[:3]
    )
    if rates:
        st.json(rates)
    else:
        st.caption("评测将在发布前生成。")


def main() -> None:
    settings = RuntimeSettings.from_env()
    context = build_context(st.session_state, settings)
    garments = context.repository.list_garments(context.owner_id)
    st.title("StyleMate 衣橱管家")
    st.caption("用已有衣物，快速得到可执行的今日搭配。")
    today, wardrobe, assistant, about = st.tabs(["今日搭配", "我的衣橱", "搭配助手", "关于项目"])
    with today:
        _today_tab(context, garments)
    with wardrobe:
        _wardrobe_tab(context, garments)
    with assistant:
        _assistant_tab(context, garments)
    with about:
        _about_tab(context)


main()
