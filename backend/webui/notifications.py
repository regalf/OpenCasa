"""Sistema di notifiche con persistenza su database per utente."""

import json
import os
import threading
from datetime import datetime, timezone

from .database import get as _db_get, set as _db_set


_lock = threading.Lock()


def _notif_key(username):
    return f"_notifications:{username}"


def get_notifications(username):
    if not username:
        return []
    raw = _db_get(_notif_key(username))
    if raw:
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def _save_notifications(username, notifs):
    _db_set(_notif_key(username), json.dumps(notifs))


def push_notification(app_id, title, message, severity="info", username=None):
    n = {
        "id": datetime.now().strftime("%Y%m%d%H%M%S.%f") + "-" + os.urandom(4).hex(),
        "app_id": app_id,
        "title": title,
        "message": message,
        "severity": severity,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "read": False,
    }
    with _lock:
        notifs = get_notifications(username)
        notifs.append(n)
        _save_notifications(username, notifs)
    return n


def delete_notification(notif_id, username=None):
    with _lock:
        notifs = get_notifications(username)
        for i, n in enumerate(notifs):
            if n["id"] == notif_id:
                notifs.pop(i)
                _save_notifications(username, notifs)
                return True
    return False


def clear_notifications(username=None):
    with _lock:
        _save_notifications(username, [])