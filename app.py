import re
from dotenv import load_dotenv
load_dotenv()
import streamlit as st
from agent.react_agent import ReactAgent
from agent.tools.agent_tools import resolve_user_city, fetch_weather_text
from utils.auth import (
    ensure_user_store,
    authenticate_user,
    register_user,
    get_user_profile,
    update_user_profile,
)
from utils.chat_store import (
    ensure_chat_store,
    list_user_chats,
    get_chat_messages,
    create_chat,
    append_message,
    update_chat_title,
    delete_chat,
)

st.set_page_config(page_title="衣橱助理", page_icon="👗")
st.title("👗 衣橱助理 Agent")
st.caption("基于 LangChain ReAct Agent + RAG 检索增强")
st.divider()

st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=ZCOOL+XiaoWei&family=IBM+Plex+Sans:wght@400;600&display=swap');

        html, body, [class*="css"]  {
            font-family: 'IBM Plex Sans', 'ZCOOL XiaoWei', sans-serif;
            color: #2b2b2b;
        }
        h1, h2, h3, h4 {
            font-family: 'ZCOOL XiaoWei', 'IBM Plex Sans', sans-serif;
            letter-spacing: 0.3px;
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #f5f2ee 0%, #f9f7f4 100%);
            border-right: 1px solid #ede7e1;
        }
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {
            color: #2f2b27;
        }
        [data-testid="stSidebar"] .stButton > button {
            width: 100%;
            border-radius: 10px;
            border: 1px solid #e3dcd4;
            background: #ffffff;
            color: #2f2b27;
            padding: 0.4rem 0.6rem;
        }
        [data-testid="stSidebar"] .stButton > button:hover {
            border-color: #cfc6bb;
            background: #fdfcfb;
        }
        [data-testid="stSidebar"] .stTextInput input,
        [data-testid="stSidebar"] .stTextArea textarea {
            border-radius: 10px;
            border: 1px solid #e6dfd7;
            background: #ffffff;
        }
        [data-testid="stSidebar"] button[kind="primary"] {
            background: #efe8df;
            border-color: #d9cec2;
            color: #2f2b27;
            font-weight: 600;
            box-shadow: none;
        }
        [data-testid="stSidebar"] button[kind="primary"]:hover {
            background: #e6ddd2;
            border-color: #cdbfb1;
        }

        .chat-list-title {font-weight: 600; margin-top: 0.6rem; color: #3a342f;}
        .chat-row {display: flex; align-items: center; gap: 6px; margin: 2px 0;}
        .chat-row small {color: #8f8780;}
        .sidebar-actions button {padding: 0.25rem 0.45rem;}

        .usage-hint {
            background: linear-gradient(120deg, #fbf8f3 0%, #f4efe8 100%);
            border: 1px solid #eadfce;
            border-radius: 14px;
            padding: 1rem 1.2rem;
            margin: 0.8rem 0 1.4rem 0;
            box-shadow: 0 8px 20px rgba(64, 53, 39, 0.06);
        }
        .usage-title {
            font-weight: 600;
            margin-bottom: 0.4rem;
            color: #3b332c;
        }
        .usage-hint ul {
            margin: 0;
            padding-left: 1.2rem;
            color: #5c534b;
        }
        .usage-hint li {margin: 0.25rem 0;}
        .profile-summary {
            background: #fff7ee;
            border: 1px dashed #e6d6c4;
            border-radius: 12px;
            padding: 0.6rem 0.7rem;
            color: #6a5f55;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

ensure_user_store()
ensure_chat_store()

if "user" not in st.session_state:
    st.session_state["user"] = None
if "active_chat_id" not in st.session_state:
    st.session_state["active_chat_id"] = None


PROFILE_LABELS = {
    "height": "身高",
    "weight": "体重",
    "fit_preference": "版型偏好",
    "style_preference": "风格偏好",
    "color_preference": "颜色偏好",
    "scene_preference": "常见场景",
    "body_features": "体型特征",
}

PROFILE_KEYS = list(PROFILE_LABELS.keys())


def _profile_context(profile: dict) -> str:
    if not profile:
        return ""

    labels = PROFILE_LABELS
    parts = []
    for key, label in labels.items():
        value = str(profile.get(key, "")).strip()
        if value:
            parts.append(f"- {label}：{value}")

    if not parts:
        return ""

    return "用户画像（长期记忆，请优先参考）：\n" + "\n".join(parts)


def _profile_preview(profile: dict) -> str:
    context = _profile_context(profile)
    if not context:
        return "尚未填写"
    return context.replace("用户画像（长期记忆，请优先参考）：\n", "").replace("\n", "；")


def _split_values(text: str) -> set[str]:
    if not text:
        return set()
    parts = re.split(r"[，,;/、\s]+", text)
    return {p.strip() for p in parts if p.strip()}


def _is_conflict(old_value: str, new_value: str) -> bool:
    if not old_value or not new_value:
        return False
    old_set = _split_values(old_value)
    new_set = _split_values(new_value)
    if not old_set or not new_set:
        return False
    return old_set.isdisjoint(new_set)


def _extract_profile_from_text(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        return {}

    profile: dict[str, str] = {}

    height_match = re.search(r"(?:身高\s*)?([1-2]\d{2})\s*(?:cm|厘米)", text)
    if height_match:
        profile["height"] = f"{height_match.group(1)}cm"
    else:
        height_match = re.search(r"(?:身高\s*)?([1-2]\.\d{1,2})\s*(?:m|米)", text)
        if height_match:
            profile["height"] = f"{height_match.group(1)}m"
        else:
            height_match = re.search(r"身高\s*([1-2]\d{2})", text)
            if height_match:
                profile["height"] = f"{height_match.group(1)}cm"

    weight_match = re.search(r"(?:体重\s*)?([3-9]\d(?:\.\d+)?)\s*(kg|公斤|千克|斤)", text)
    if weight_match:
        profile["weight"] = f"{weight_match.group(1)}{weight_match.group(2)}"
    else:
        weight_match = re.search(r"体重\s*([3-9]\d(?:\.\d+)?)", text)
        if weight_match:
            profile["weight"] = f"{weight_match.group(1)}kg"

    fit_map = {
        "宽松": "宽松",
        "偏松": "宽松",
        "oversize": "宽松",
        "修身": "修身",
        "偏紧": "修身",
        "贴身": "修身",
        "合身": "标准",
        "标准": "标准",
    }
    for key, value in fit_map.items():
        if key in text.lower():
            profile["fit_preference"] = value
            break

    style_keywords = ["简约", "通勤", "甜美", "街头", "运动", "休闲", "韩系", "日系", "复古", "学院", "温柔", "法式"]
    for style in style_keywords:
        if style in text:
            profile["style_preference"] = style
            break

    color_keywords = ["黑白灰", "中性色", "暖色", "冷色", "亮色", "莫兰迪", "大地色", "低饱和", "高饱和"]
    for color in color_keywords:
        if color in text:
            profile["color_preference"] = color
            break

    scene_map = {
        "通勤": "通勤",
        "上班": "通勤",
        "约会": "约会",
        "出游": "出游",
        "旅行": "出游",
        "运动": "运动",
        "居家": "居家",
        "面试": "面试",
        "聚会": "聚会",
    }
    for key, value in scene_map.items():
        if key in text:
            profile["scene_preference"] = value
            break

    body_terms = ["肩宽", "肩窄", "胯宽", "胯窄", "腿粗", "腿细", "梨形", "H型", "X型", "O型", "腿长", "腿短"]
    body_hits = [t for t in body_terms if t in text]
    if body_hits:
        profile["body_features"] = "、".join(sorted(set(body_hits)))

    return profile


def _merge_profile(existing: dict, updates: dict) -> tuple[dict, list[str], dict]:
    merged = {key: str(existing.get(key, "")).strip() for key in PROFILE_KEYS}
    changed_fields: list[str] = []
    conflicts: dict[str, dict] = {}

    for key, value in updates.items():
        value = str(value or "").strip()
        if not value:
            continue
        current = merged.get(key, "")

        if key == "body_features" and current:
            merged_set = _split_values(current)
            merged_set.update(_split_values(value))
            merged_value = "、".join(sorted(merged_set))
            if merged_value != current:
                merged[key] = merged_value
                changed_fields.append(key)
            continue

        if current and _is_conflict(current, value):
            conflicts[key] = {"current": current, "incoming": value}
            continue

        if value != current:
            merged[key] = value
            changed_fields.append(key)

    return merged, changed_fields, conflicts


def _format_conflicts(conflicts: dict) -> str:
    if not conflicts:
        return ""
    parts = []
    for key, payload in conflicts.items():
        label = PROFILE_LABELS.get(key, key)
        parts.append(f"{label}：画像为{payload.get('current')}，本次为{payload.get('incoming')}")
    return "；".join(parts)


def _request_profile_context(profile: dict) -> str:
    if not profile:
        return ""
    parts = []
    for key, label in PROFILE_LABELS.items():
        value = str(profile.get(key, "")).strip()
        if value:
            parts.append(f"- {label}：{value}")
    if not parts:
        return ""
    return "本次请求偏好（仅用于当前回答）：\n" + "\n".join(parts)


def _conflict_context(conflicts: dict) -> str:
    if not conflicts:
        return ""
    details = []
    for key, payload in conflicts.items():
        label = PROFILE_LABELS.get(key, key)
        details.append(f"- {label}：画像={payload.get('current')} / 当前={payload.get('incoming')}")
    return (
        "检测到用户画像偏好与本次请求不一致，请在回答中提醒用户并给出折中建议，"
        "必要时询问是否更新画像。\n" + "\n".join(details)
    )

with st.sidebar:
    st.header("账号")
    if st.session_state["user"]:
        st.success(f"已登录：{st.session_state['user']}")
        if st.button("退出登录"):
            st.session_state["user"] = None
            st.session_state["active_chat_id"] = None
            st.rerun()
    else:
        tab_login, tab_register = st.tabs(["登录", "注册"])
        with tab_login:
            login_user = st.text_input("用户名", key="login_user")
            login_pass = st.text_input("密码", type="password", key="login_pass")
            if st.button("登录"):
                ok, msg = authenticate_user(login_user, login_pass)
                if ok:
                    st.session_state["user"] = login_user
                    st.rerun()
                else:
                    st.error(msg)

        with tab_register:
            reg_user = st.text_input("用户名", key="reg_user")
            reg_pass = st.text_input("密码", type="password", key="reg_pass")
            reg_pass2 = st.text_input("确认密码", type="password", key="reg_pass2")
            if st.button("注册"):
                if reg_pass != reg_pass2:
                    st.error("两次输入的密码不一致")
                else:
                    ok, msg = register_user(reg_user, reg_pass)
                    if ok:
                        st.session_state["user"] = reg_user
                        st.rerun()
                    else:
                        st.error(msg)

    if st.session_state["user"]:
        user_profile = get_user_profile(st.session_state["user"])
        st.header("对话记录")
        chats = list_user_chats(st.session_state["user"])
        st.session_state["chat_titles"] = {c["id"]: c["title"] for c in chats}

        if st.button("新对话"):
            new_id = create_chat(st.session_state["user"], "新对话")
            st.session_state["active_chat_id"] = new_id
            st.rerun()

        if chats:
            chat_ids = [c["id"] for c in chats]
            active_id = st.session_state.get("active_chat_id")
            if active_id not in chat_ids:
                active_id = chat_ids[0]
                st.session_state["active_chat_id"] = active_id

            st.markdown("<div class='chat-list-title'>最近</div>", unsafe_allow_html=True)
            for chat in chats:
                chat_id = chat["id"]
                title = chat.get("title", "新对话")
                updated_at = chat.get("updated_at", "")

                col_main, col_menu = st.columns([0.86, 0.14])
                with col_main:
                    is_active = chat_id == active_id
                    if st.button(
                        title,
                        key=f"chat_open_{chat_id}",
                        type="primary" if is_active else "secondary",
                        use_container_width=True,
                    ):
                        st.session_state["active_chat_id"] = chat_id
                        st.rerun()
                    if updated_at:
                        st.caption(updated_at)
                with col_menu:
                    with st.popover(" "):
                        new_title = st.text_input(
                            "重命名",
                            value=title,
                            key=f"rename_{chat_id}",
                        )
                        if st.button("保存名称", key=f"save_{chat_id}"):
                            update_chat_title(st.session_state["user"], chat_id, new_title.strip())
                            st.rerun()
                        if st.button("删除对话", key=f"delete_{chat_id}"):
                            delete_chat(st.session_state["user"], chat_id)
                            st.session_state["active_chat_id"] = None
                            st.rerun()
        else:
            st.caption("暂无对话记录")

        st.header("个人画像")
        st.markdown(
            f"<div class='profile-summary'>当前画像：{_profile_preview(user_profile)}</div>",
            unsafe_allow_html=True,
        )
        with st.popover("编辑画像"):
            with st.form("profile_form"):
                profile_height = st.text_input("身高", value=user_profile.get("height", ""), placeholder="165cm / 1.65m")
                profile_weight = st.text_input("体重", value=user_profile.get("weight", ""), placeholder="52kg / 104斤")
                profile_fit = st.text_input("版型偏好", value=user_profile.get("fit_preference", ""), placeholder="宽松 / 修身 / 标准")
                profile_style = st.text_input("风格偏好", value=user_profile.get("style_preference", ""), placeholder="简约 / 通勤 / 甜美")
                profile_color = st.text_input("颜色偏好", value=user_profile.get("color_preference", ""), placeholder="黑白灰 / 暖色 / 冷色")
                profile_scene = st.text_input("常见场景", value=user_profile.get("scene_preference", ""), placeholder="通勤 / 约会 / 出游")
                profile_body = st.text_area("体型特征", value=user_profile.get("body_features", ""), placeholder="肩宽、胯宽、腿型等")
                save_profile = st.form_submit_button("保存画像")

                if save_profile:
                    ok, msg = update_user_profile(
                        st.session_state["user"],
                        {
                            "height": profile_height,
                            "weight": profile_weight,
                            "fit_preference": profile_fit,
                            "style_preference": profile_style,
                            "color_preference": profile_color,
                            "scene_preference": profile_scene,
                            "body_features": profile_body,
                        },
                    )
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    st.header("设置")
    auto_weather = st.checkbox("自动定位并补充天气", value=True)


def _should_prefetch_weather(text: str) -> bool:
    if not text:
        return False
    keywords = ["天气", "穿什么", "出门", "出行", "通勤", "旅行", "带什么衣服", "搭配"]
    if not any(k in text for k in keywords):
        return False
    # If user already mentions a destination/region hint, avoid IP-based auto fill.
    location_hints = ["市", "省", "县", "区", "州", "国", "去", "到"]
    if any(h in text for h in location_hints):
        return False
    return True

if "agent" not in st.session_state:
    st.session_state["agent"] = ReactAgent()

user = st.session_state["user"]
active_chat_id = st.session_state.get("active_chat_id")
if user and active_chat_id:
    messages = get_chat_messages(user, active_chat_id)
else:
    messages = []

for message in messages:
    st.chat_message(message["role"]).write(message["content"])

if user and not messages:
        st.markdown(
                """
                <div class="usage-hint">
                    <div class="usage-title">可以直接描述你的需求，例如：</div>
                    <ul>
                        <li>根据身高体重推荐尺码</li>
                        <li>约会/通勤/出游穿搭建议</li>
                        <li>某材质衣物的洗护方式</li>
                    </ul>
                </div>
                """,
                unsafe_allow_html=True,
        )

prompt = None
if user:
    prompt = st.chat_input("输入你的需求...")
else:
    st.info("请先登录后再开始对话。")

def _build_title(text: str) -> str:
    text = (text or "").strip()
    if len(text) <= 16:
        return text or "新对话"
    return text[:16] + "..."


if prompt:
    if not active_chat_id:
        active_chat_id = create_chat(user, _build_title(prompt))
        st.session_state["active_chat_id"] = active_chat_id
    else:
        title = st.session_state.get("chat_titles", {}).get(active_chat_id, "")
        if title in ("", "新对话"):
            update_chat_title(user, active_chat_id, _build_title(prompt))

    st.chat_message("user").write(prompt)
    append_message(user, active_chat_id, "user", prompt)
    messages.append({"role": "user", "content": prompt})

    current_profile = get_user_profile(user)
    extracted_profile = _extract_profile_from_text(prompt)
    merged_profile, updated_fields, conflicts = _merge_profile(current_profile, extracted_profile)
    if updated_fields:
        update_user_profile(user, merged_profile)
        changed_labels = [PROFILE_LABELS.get(x, x) for x in updated_fields]
        st.info("已自动补充画像：" + "、".join(changed_labels))
    if conflicts:
        st.warning("检测到偏好冲突：" + _format_conflicts(conflicts))

    response_messages: list[str] = []
    enriched_prompt = prompt
    if auto_weather and _should_prefetch_weather(prompt):
        city = resolve_user_city()
        if city:
            weather_text = fetch_weather_text(city)
            if weather_text and not weather_text.startswith("天气查询失败"):
                enriched_prompt = f"{prompt}\n\n已获取天气信息：{weather_text}"

    messages_for_agent = [dict(m) for m in messages]
    if messages_for_agent and messages_for_agent[-1].get("role") == "user":
        messages_for_agent[-1]["content"] = enriched_prompt

    system_notes = []
    profile_context = _profile_context(merged_profile)
    if profile_context:
        system_notes.append({"role": "system", "content": profile_context})
    request_context = _request_profile_context(extracted_profile)
    if request_context:
        system_notes.append({"role": "system", "content": request_context})
    conflict_context = _conflict_context(conflicts)
    if conflict_context:
        system_notes.append({"role": "system", "content": conflict_context})
    if system_notes:
        messages_for_agent = system_notes + messages_for_agent

    with st.spinner("衣橱助理思考中..."):
        res_stream = st.session_state["agent"].execute_stream(messages_for_agent)

        def stream_generator(generator, cache_list):
            for chunk in generator:
                cache_list.append(chunk)
                for char in chunk:
                    yield char

        st.chat_message("assistant").write_stream(stream_generator(res_stream, response_messages))
        assistant_text = "".join(response_messages)
        append_message(user, active_chat_id, "assistant", assistant_text)
        messages.append({"role": "assistant", "content": assistant_text})
        st.rerun()
