import json
import os
import secrets
import hashlib
from datetime import datetime
from utils.path_tool import get_abs_path

USER_STORE_PATH = get_abs_path("data/users.json")


def ensure_user_store():
    if not os.path.exists(USER_STORE_PATH):
        os.makedirs(os.path.dirname(USER_STORE_PATH), exist_ok=True)
        with open(USER_STORE_PATH, "w", encoding="utf-8") as f:
            json.dump({"users": {}}, f, ensure_ascii=False, indent=2)


def _load_users():
    ensure_user_store()
    with open(USER_STORE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_users(data: dict):
    with open(USER_STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def register_user(username: str, password: str):
    username = (username or "").strip()
    password = password or ""

    if not username or not password:
        return False, "用户名和密码不能为空"
    if len(username) < 3:
        return False, "用户名至少3个字符"
    if len(password) < 6:
        return False, "密码至少6位"

    data = _load_users()
    users = data.get("users", {})

    if username in users:
        return False, "用户名已存在"

    salt = secrets.token_hex(16)
    password_hash = _hash_password(password, salt)

    users[username] = {
        "salt": salt,
        "password_hash": password_hash,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "profile": {},
    }
    data["users"] = users
    _save_users(data)

    return True, "注册成功"


def authenticate_user(username: str, password: str):
    username = (username or "").strip()
    password = password or ""

    if not username or not password:
        return False, "用户名或密码不能为空"

    data = _load_users()
    users = data.get("users", {})
    info = users.get(username)
    if not info:
        return False, "用户名或密码错误"

    expected = info.get("password_hash", "")
    salt = info.get("salt", "")
    if not salt or not expected:
        return False, "用户名或密码错误"

    if _hash_password(password, salt) != expected:
        return False, "用户名或密码错误"

    return True, "登录成功"


def get_user_profile(username: str) -> dict:
    username = (username or "").strip()
    if not username:
        return {}

    data = _load_users()
    users = data.get("users", {})
    info = users.get(username, {})
    profile = info.get("profile", {})
    return profile if isinstance(profile, dict) else {}


def update_user_profile(username: str, profile: dict):
    username = (username or "").strip()
    if not username:
        return False, "用户名不能为空"

    data = _load_users()
    users = data.get("users", {})
    info = users.get(username)
    if not info:
        return False, "用户不存在"

    clean_profile = {
        "height": str(profile.get("height", "")).strip(),
        "weight": str(profile.get("weight", "")).strip(),
        "fit_preference": str(profile.get("fit_preference", "")).strip(),
        "style_preference": str(profile.get("style_preference", "")).strip(),
        "color_preference": str(profile.get("color_preference", "")).strip(),
        "scene_preference": str(profile.get("scene_preference", "")).strip(),
        "body_features": str(profile.get("body_features", "")).strip(),
    }

    info["profile"] = clean_profile
    users[username] = info
    data["users"] = users
    _save_users(data)
    return True, "个人画像已保存"
