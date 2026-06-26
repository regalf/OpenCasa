"""Reverse proxy per app di terze parti (/app/<id> → localhost:<port>)."""

import json
import logging
import urllib.parse
import urllib.request
import urllib.error

from . import config
from .appmanager import get_app


def handle_app_proxy(handler, path):
    parts = path.split("/", 3)
    if len(parts) < 3:
        return handler._send_error(400, "invalid proxy path")
    app_id = parts[2]
    rest = parts[3] if len(parts) > 3 else ""

    # App-scoped notification API — handle directly instead of forwarding to app
    if rest.startswith("api/v1/notif"):
        return _handle_notif_api(handler, app_id, rest, path)

    app = get_app(app_id)
    if not app:
        return handler._send_error(404, "app not found")
    if app.get("status") != "running":
        return handler._send_error(503, "app not running")
    target_port = app.get("port", 0)
    if not target_port:
        return handler._send_error(502, "no port configured in app manifest")
    target_url = f"http://127.0.0.1:{target_port}/{rest}"
    qs = urllib.parse.urlparse(handler.path).query
    if qs:
        target_url += "?" + qs

    body = handler._read_body() if handler.command == "POST" else None
    max_size = (config.get("filesystem", {}) or {}).get("max_upload_size", 100) * 1024 * 1024
    if body and len(body) > max_size:
        return handler._send_error(413, "request body too large")

    req = urllib.request.Request(
        target_url,
        data=body,
        headers={k: v for k, v in handler.headers.items() if k.lower() not in ("host",)},
        method=handler.command,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            handler.send_response(resp.status)
            handler.send_header("Access-Control-Allow-Origin", "*")
            for k, v in resp.headers.items():
                if k.lower() not in ("transfer-encoding", "access-control-allow-origin"):
                    handler.send_header(k, v)
            handler.end_headers()
            handler.wfile.write(resp.read())
    except urllib.error.HTTPError as e:
        handler.send_response(e.code)
        handler.send_header("Content-Type", "text/plain")
        handler.end_headers()
        body = e.read()
        handler.wfile.write(body if isinstance(body, bytes) else body.encode())
    except Exception as e:
        handler._send_error(502, str(e))


def _handle_notif_api(handler, app_id, rest, path):
    """Handle notification API calls within the app's scope (app_id enforced)."""
    from .notifications import get_notifications, push_notification, delete_notification, clear_notifications

    username = getattr(handler, '_current_user', None)
    if not username:
        return handler._send_error(401, "not authenticated")

    if handler.command == "POST":
        if rest == "api/v1/notify":
            data = handler._json_body()
            if not data:
                return handler._send_error(400, "invalid body")
            data["app_id"] = app_id
            n = push_notification(
                app_id,
                data.get("title", ""),
                data.get("message", ""),
                data.get("severity", "info"),
                username,
            )
            return handler._send_json(n)

        if rest == "api/v1/notifications/delete":
            data = handler._json_body()
            if not data or "id" not in data:
                return handler._send_error(400, "missing id")
            ok = delete_notification(data["id"], username, app_id)
            return handler._send_json({"success": ok})

        if rest == "api/v1/notifications/clear":
            clear_notifications(username, app_id)
            return handler._send_json({"success": True})

    # GET
    if rest == "api/v1/notifications":
        notifs = [n for n in get_notifications(username) if n.get("app_id") == app_id]
        return handler._send_json({"notifications": notifs})

    return handler._send_error(404, f"notification endpoint not found: {rest}")
