"""JWT puro HMAC-SHA256, zero dipendenze."""

import base64
import hmac
import hashlib
import json
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


def make_token(username):
    ttl = parse_ttl(config["auth"]["session_ttl"])
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url(
        json.dumps({
            "username": username,
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
