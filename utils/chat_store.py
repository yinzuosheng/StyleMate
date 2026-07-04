import json
import os
import uuid
from datetime import datetime
from utils.path_tool import get_abs_path

CHAT_STORE_PATH = get_abs_path("data/chat_history.json")


def ensure_chat_store():
    if not os.path.exists(CHAT_STORE_PATH):
        os.makedirs(os.path.dirname(CHAT_STORE_PATH), exist_ok=True)
        with open(CHAT_STORE_PATH, "w", encoding="utf-8") as f:
            json.dump({"users": {}}, f, ensure_ascii=False, indent=2)


def _load_store():
    ensure_chat_store()
    with open(CHAT_STORE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_store(data: dict):
    with open(CHAT_STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _get_user_node(store: dict, username: str):
    users = store.setdefault("users", {})
    user = users.setdefault(username, {"chats": {}})
    user.setdefault("chats", {})
    return user


def list_user_chats(username: str):
    store = _load_store()
    user = _get_user_node(store, username)
    chats = []
    for chat_id, chat in user.get("chats", {}).items():
        chats.append(
            {
                "id": chat_id,
                "title": chat.get("title", "新对话"),
                "created_at": chat.get("created_at", ""),
                "updated_at": chat.get("updated_at", ""),
            }
        )
    return sorted(chats, key=lambda c: c.get("updated_at", ""), reverse=True)


def get_chat_messages(username: str, chat_id: str):
    store = _load_store()
    user = _get_user_node(store, username)
    chat = user.get("chats", {}).get(chat_id)
    if not chat:
        return []
    return chat.get("messages", [])


def create_chat(username: str, title: str):
    store = _load_store()
    user = _get_user_node(store, username)
    chat_id = uuid.uuid4().hex[:8]
    now = datetime.now().isoformat(timespec="seconds")
    user["chats"][chat_id] = {
        "title": title or "新对话",
        "created_at": now,
        "updated_at": now,
        "messages": [],
    }
    _save_store(store)
    return chat_id


def update_chat_title(username: str, chat_id: str, title: str):
    if not title:
        return
    store = _load_store()
    user = _get_user_node(store, username)
    chat = user.get("chats", {}).get(chat_id)
    if not chat:
        return
    chat["title"] = title
    chat["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _save_store(store)


def delete_chat(username: str, chat_id: str):
    store = _load_store()
    user = _get_user_node(store, username)
    chats = user.get("chats", {})
    if chat_id in chats:
        del chats[chat_id]
        _save_store(store)


def append_message(username: str, chat_id: str, role: str, content: str):
    store = _load_store()
    user = _get_user_node(store, username)
    chat = user.get("chats", {}).get(chat_id)
    if not chat:
        chat_id = create_chat(username, "新对话")
        store = _load_store()
        user = _get_user_node(store, username)
        chat = user.get("chats", {}).get(chat_id)

    chat.setdefault("messages", []).append({"role": role, "content": content})
    chat["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _save_store(store)
    return chat_id
