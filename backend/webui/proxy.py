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
    app = get_app(app_id)
    if not app:
        return handler._send_error(404, "app not found")
    if app.get("status") != "running":
        return handler._send_error(503, "app not running")
    target_port = app.get("port", 8081)
    rest = parts[3] if len(parts) > 3 else ""
    target_url = f"http://127.0.0.1:{target_port}/{rest}"
    qs = urllib.parse.urlparse(handler.path).query
    if qs:
        target_url += "?" + qs

    req = urllib.request.Request(
        target_url,
        data=handler._read_body() if handler.command == "POST" else None,
        headers={k: v for k, v in handler.headers.items() if k.lower() not in ("host",)},
        method=handler.command,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            handler.send_response(resp.status)
            for k, v in resp.headers.items():
                if k.lower() not in ("transfer-encoding",):
                    handler.send_header(k, v)
            handler.end_headers()
            handler.wfile.write(resp.read())
    except urllib.error.HTTPError as e:
        handler.send_response(e.code)
        handler.end_headers()
        handler.wfile.write(e.read())
    except Exception as e:
        handler._send_error(502, str(e))
