"""Focused Streamlit renderers for the StyleMate workbench."""

from html import escape

import streamlit as st

from domain.models import AgentTrace, Garment, OutfitRecommendation


def inject_style() -> None:
    st.markdown(
        """
        <style>
        .stylemate-card {border: 1px solid #e7dfd8; border-radius: 14px; padding: .85rem; margin-bottom: .7rem; background: #fffdfb;}
        .stylemate-card h4 {margin: 0 0 .25rem 0; color: #342e29;}
        .stylemate-muted {color: #746a62; font-size: .9rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_garment_card(garment: Garment, image_value=None) -> None:
    if image_value:
        st.image(image_value, use_container_width=True)
    st.markdown(
        f"<div class='stylemate-card'><h4>{escape(garment.name)}</h4>"
        f"<div class='stylemate-muted'>{escape(garment.category)} · {escape(garment.primary_color)}</div>"
        f"<div class='stylemate-muted'>{escape('、'.join(garment.styles))}</div></div>",
        unsafe_allow_html=True,
    )


def render_outfit_card(
    recommendation: OutfitRecommendation, garments: dict[str, Garment]
) -> None:
    names = [garments[item_id].name for item_id in recommendation.garment_ids if item_id in garments]
    st.markdown(
        f"<div class='stylemate-card'><h4>搭配评分 {recommendation.score}</h4>"
        f"<div>{escape(' · '.join(names))}</div><div class='stylemate-muted'>{escape(recommendation.reason)}</div></div>",
        unsafe_allow_html=True,
    )


def render_trace(trace: AgentTrace) -> None:
    with st.expander("生成过程"):
        for step in trace.steps:
            st.write(f"{step.name} · {step.status} · {step.summary}")


def render_empty_state(title: str, body: str) -> None:
    st.info(f"{title}\n\n{body}")
