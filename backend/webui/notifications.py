"""Sistema di notifiche con persistenza JSON."""

import json
import os
import threading
from datetime import datetime, timezone

from . import NOTIF_FILE


notifications = []
notif_lock = threading.Lock()


def load_notifications():
    global notifications
    try:
        with open(NOTIF_FILE) as f:
            notifications = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        notifications = []


def save_notifications():
    os.makedirs(os.path.dirname(NOTIF_FILE), exist_ok=True)
    with open(NOTIF_FILE, "w") as f:
        json.dump(notifications, f, indent=2)


def push_notification(app_id, title, message, severity="info"):
    n = {
        "id": datetime.now().strftime("%H%M%S.%f"),
        "app_id": app_id,
        "title": title,
        "message": message,
        "severity": severity,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "read": False,
    }
    with notif_lock:
        notifications.append(n)
    save_notifications()
    return n
