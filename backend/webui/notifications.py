"""Sistema di notifiche con persistenza su database per utente."""

import json
import os
import threading
from datetime import datetime, timezone

from .database import get as _db_get, set as _db_set


_lock = threading.Lock()


def _notif_key(username):
    return f"_notifications:{username}"


def get_notifications(username, app_id=None):
    if not username:
        return []
    raw = _db_get(_notif_key(username))
    if raw:
        try:
            notifs = json.loads(raw)
            if app_id:
                notifs = [n for n in notifs if n.get("app_id") == app_id]
            return notifs
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


def delete_notification(notif_id, username=None, app_id=None):
    with _lock:
        notifs = get_notifications(username)
        for i, n in enumerate(notifs):
            if n["id"] == notif_id:
                if app_id and n.get("app_id") != app_id:
                    return False
                notifs.pop(i)
                _save_notifications(username, notifs)
                return True
    return False


def clear_notifications(username=None, app_id=None):
    with _lock:
        if app_id:
            notifs = get_notifications(username)
            notifs = [n for n in notifs if n.get("app_id") != app_id]
            _save_notifications(username, notifs)
        else:
            _save_notifications(username, [])
