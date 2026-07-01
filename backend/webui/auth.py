"""JWT puro HMAC-SHA256, zero dipendenze. User management in DB."""

import base64
import hashlib
import hmac
import json
import os
import time

from . import config


def _b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s):
    s += "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s)


def parse_ttl(val):
    unit = val[-1]
    num = int(val[:-1])
    if unit == "h":
        return num * 3600
    if unit == "m":
        return num * 60
    if unit == "s":
        return num
    return 86400


def make_token(username, is_root=False, role="regular"):
    ttl = parse_ttl(config["auth"]["session_ttl"])
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url(
        json.dumps({
            "username": username,
            "is_root": is_root,
            "role": role,
            "exp": int(time.time()) + ttl,
            "iat": int(time.time()),
        }).encode()
    )
    sig_input = f"{header}.{payload}"
    sig = _b64url(
        hmac.new(
            config["auth"]["jwt_secret"].encode(),
            sig_input.encode(),
            hashlib.sha256,
        ).digest()
    )
    return f"{sig_input}.{sig}"


def verify_token(token):
    parts = token.split(".")
    if len(parts) != 3:
        return None
    sig_input = f"{parts[0]}.{parts[1]}"
    expected = _b64url(
        hmac.new(
            config["auth"]["jwt_secret"].encode(),
            sig_input.encode(),
            hashlib.sha256,
        ).digest()
    )
    if not hmac.compare_digest(parts[2], expected):
        return None
    try:
        payload = json.loads(_b64url_decode(parts[1]))
    except Exception:
        return None
    if time.time() > payload.get("exp", 0):
        return None
    return payload


# ── User management in encrypted DB ──

def hash_password(password):
    salt = os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 10000)
    return base64.b64encode(salt + h).decode()


def verify_password(password, stored):
    try:
        raw = base64.b64decode(stored)
        salt, h = raw[:16], raw[16:]
        return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 10000) == h
    except Exception:
        return False


def create_user(username, password, role="regular"):
    from . import database as dbmod
    key = "_user:" + username
    if dbmod.get(key):
        return False, "User exists"
    value = json.dumps({"hash": hash_password(password), "role": role, "created": time.time()})
    dbmod.set(key, value)
    return True, ""


def delete_user(username):
    from . import database as dbmod
    user_prefix = "_user:" + username
    dbmod.delete(user_prefix)
    # Clean up user-scoped keys
    for key in dbmod.list_keys():
        if key.startswith("_notifications:" + username) or \
           key.startswith("_avatar:" + username) or \
           key.startswith("_pref:" + username + ":") or \
           key.startswith("_app_perm_state:" + username + ":") or \
           key.startswith("_app_limits:" + username + ":"):
            dbmod.delete(key)


def list_users():
    from . import database as dbmod
    keys = [k for k in dbmod.list_keys() if k.startswith("_user:")]
    users = []
    for k in keys:
        data = json.loads(dbmod.get(k))
        users.append({"username": k[6:], "role": data.get("role", "regular"), "created": data.get("created", 0)})
    return users


def get_user(username):
    from . import database as dbmod
    data = dbmod.get("_user:" + username)
    if not data:
        return None
    return json.loads(data)


def get_user_role(username):
    info = get_user(username)
    if info:
        return info.get("role", "regular")
    return None


def set_user_role(username, role):
    from . import database as dbmod
    key = "_user:" + username
    data = dbmod.get(key)
    if not data:
        return False, "User not found"
    info = json.loads(data)
    info["role"] = role
    dbmod.set(key, json.dumps(info))
    return True, ""


def set_first_admin(username):
    from . import database as dbmod
    dbmod.set("_first_admin", username)


def get_first_admin():
    from . import database as dbmod
    return dbmod.get("_first_admin")


def is_protected_admin(username):
    return get_first_admin() == username


def user_count():
    from . import database as dbmod
    return len([k for k in dbmod.list_keys() if k.startswith("_user:")])


def authenticate(config, username, password):
    """Returns dict with username, is_root and role, or None on failure."""
    # Check root user (from config file)
    auth_cfg = config.get("auth", {})
    root_user = auth_cfg.get("root_user", "root")
    if username == root_user:
        root_pass = auth_cfg.get("root_password", "")
        if root_pass and (root_pass == password or verify_password(password, root_pass)):
            return {"username": username, "is_root": True, "role": "root"}

    # Backward compat: also check old auth.username/auth.password as root
    old_user = auth_cfg.get("username")
    old_pass = auth_cfg.get("password")
    if old_user and username == old_user and old_pass == password:
        return {"username": username, "is_root": True, "role": "root"}

    # Check DB users
    from . import database as dbmod
    data = dbmod.get("_user:" + username)
    if not data:
        return None
    info = json.loads(data)
    if verify_password(password, info.get("hash", "")):
        return {"username": username, "is_root": False, "role": info.get("role", "regular")}
    return None
