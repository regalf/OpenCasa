"""
webui — Pannello di Gestione Server per OpenBSD/macppc (G3/G4/G5)
Zero dipendenze esterne, solo stdlib Python.
"""

import argparse
import base64
import json
import logging
import mimetypes
import os
import signal
import sys
import threading
import urllib.parse
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

DEFAULT_CONFIG = {
    "server": {"host": "0.0.0.0", "port": 80},
    "auth": {
        "enabled": True,
        "username": "admin",
        "password": "admin",
        "jwt_secret": "cambiami-con-32-byte-da-openssl-rand",
        "session_ttl": "24h",
    },
    "filesystem": {
        "allowed_prefixes": ["/home", "/var/www", "/mnt", "/tmp", "/opt"],
        "max_upload_size": 100,
    },
    "system": {"platform": "auto"},
    "ui": {"memory_unit": "GB"},
    "log": {"level": "info", "file": "/var/log/webui.log"},
    "apps_autostart": True,
}

config = dict(DEFAULT_CONFIG)
CONFIG_PATH = None

DATA_DIR = "/usr/local/webui"
APPS_FILE = None
NOTIF_FILE = None


def set_data_dir(path):
    global DATA_DIR, APPS_FILE, NOTIF_FILE
    DATA_DIR = path
    APPS_FILE = os.path.join(path, "apps.json")
    NOTIF_FILE = os.path.join(path, "notifications.json")


set_data_dir(DATA_DIR)


def load_config(path):
    global config, CONFIG_PATH
    CONFIG_PATH = path
    try:
        with open(path) as f:
            user = json.load(f)
        deep_merge(config, user)
        logging.info("config loaded from %s", path)
    except FileNotFoundError:
        logging.warning("no config at %s, using defaults", path)
    except json.JSONDecodeError as e:
        logging.error("invalid config: %s", e)


def save_config():
    path = CONFIG_PATH
    if not path:
        return
    tmp = path + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(config, f, indent=2)
        os.replace(tmp, path)
        logging.debug("config saved to %s", path)
    except Exception as e:
        logging.warning("failed to save config: %s", e)


def deep_merge(base, overrides):
    for k, v in overrides.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            deep_merge(base[k], v)
        else:
            base[k] = v


# ── HTTP Handler ──

class OpenCasaHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        logging.info("%s %s", self.client_address[0], format % args)

    def _write(self, data):
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self._write(json.dumps(data).encode())

    def _send_error(self, status, msg):
        self._send_json({"error": msg}, status)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length > 0 else b""

    def _json_body(self):
        body = self._read_body()
        try:
            return json.loads(body)
        except (json.JSONDecodeError, ValueError):
            return None

    def _get_user(self):
        token = ""
        header = self.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            token = header[7:]
        if not token:
            cookie = self.headers.get("Cookie", "")
            for part in cookie.split(";"):
                part = part.strip()
                if part.startswith("opencasa_token="):
                    token = urllib.parse.unquote_plus(part[len("opencasa_token="):])
                    break
        if not token:
            params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            token = params.get("token", "")
        if not token:
            return None
        from .auth import verify_token
        payload = verify_token(token)
        return payload["username"] if payload else None

    def _check_auth(self):
        if not config["auth"]["enabled"]:
            return True
        user = self._get_user()
        if not user:
            self._send_error(401, "unauthorized")
            return False
        return True

    def _serve_static(self, path):
        if path == "/":
            path = "/index.html"
        bases = [
            "frontend/dist",
            "frontend",
            DATA_DIR,
            os.path.join(DATA_DIR, "frontend/dist"),
            os.path.join(DATA_DIR, "frontend"),
        ]
        for base in bases:
            filepath = os.path.join(base, path.lstrip("/"))
            if os.path.isfile(filepath):
                break
        else:
            self._send_error(404, "not found")
            return
        mime, _ = mimetypes.guess_type(filepath)
        self.send_response(200)
        self.send_header("Content-Type", mime or "application/octet-stream")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        with open(filepath, "rb") as f:
            self._write(f.read())

    # ── Router ──

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def _log_request(self):
        logging.debug("%s %s", self.command, self.path)

    def do_GET(self):
        self._log_request()
        path = urllib.parse.urlparse(self.path).path
        params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))

        if path == "/api/v1/auth/login":
            return self._send_error(405, "use POST")

        if not path.startswith("/api/") and not path.startswith("/app/"):
            return self._serve_static(path)

        # Proxy paths skip auth — app already verified as running by proxy
        if path.startswith("/app/") and len(path) > 5:
            from .proxy import handle_app_proxy
            return handle_app_proxy(self, path)

        # Icon — no auth required (<img> tags can't send Bearer token)
        if path.startswith("/api/v1/apps/") and path.endswith("/icon"):
            rest = path[len("/api/v1/apps/"):-len("/icon")].strip("/")
            if rest:
                from .appmanager import icon_path
                ip = icon_path(rest.split("/", 1)[0])
                if ip:
                    import mimetypes
                    mime, _ = mimetypes.guess_type(ip)
                    self.send_response(200)
                    self.send_header("Content-Type", mime or "application/octet-stream")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    with open(ip, "rb") as f:
                        self._write(f.read())
                    return
            return self._send_error(404, "icon not found")

        if not self._check_auth():
            return

        if path == "/api/v1/auth/check":
            return self._send_json({"ok": True, "user": self._get_user()})

        if path == "/api/v1/files" or path == "/api/v1/files/":
            from .filemanager import handle_list_files
            return handle_list_files(self, params.get("path", "/"))

        if path == "/api/v1/files/read":
            from .filemanager import handle_read_file
            return handle_read_file(self, params.get("path", ""))

        if path == "/api/v1/files/download":
            from .filemanager import handle_download
            return handle_download(self, params.get("path", ""))

        if path == "/api/v1/disks":
            from .filemanager import handle_list_disks
            return handle_list_disks(self)

        if path == "/api/v1/storage":
            from .system import get_filesystems
            return self._send_json({"filesystems": get_filesystems()})

        if path == "/api/v1/system/stats":
            from .system import get_system_stats
            return self._send_json(get_system_stats())

        if path == "/api/v1/system/info":
            from .system import get_system_info
            return self._send_json(get_system_info())

        if path == "/api/v1/apps" or path == "/api/v1/apps/":
            from .appmanager import list_apps
            return self._send_json({"apps": list_apps()})

        if path.startswith("/api/v1/apps/"):
            rest = path[len("/api/v1/apps/"):].strip("/")
            if rest:
                parts = rest.split("/", 1)
                app_id = parts[0]
                action = parts[1] if len(parts) > 1 else ""
                from .appmanager import get_app, get_logs, get_widget_data
                if not action:
                    app = get_app(app_id)
                    if not app:
                        return self._send_error(404, "app not found")
                    app["logs"] = get_logs(app_id, 5)
                    return self._send_json({"app": app})
                if action == "logs":
                    return self._send_json({"logs": get_logs(app_id)})
                if action == "widget":
                    data = get_widget_data(app_id)
                    if data is None:
                        return self._send_json({"data": None})
                    return self._send_json({"data": data})

        if path == "/api/v1/notifications":
            from .notifications import notifications, notif_lock
            with notif_lock:
                return self._send_json({"notifications": list(notifications)})

        if path == "/api/v1/db/get" or path == "/api/v1/db/get/":
            from .database import get
            return self._send_json({"value": get(params.get("key", ""))})

        if path == "/api/v1/db/list" or path == "/api/v1/db/list/":
            from .database import list_keys
            return self._send_json({"keys": list_keys(params.get("prefix", ""))})

        if path.startswith("/app/") and len(path) > 5:
            from .proxy import handle_app_proxy
            return handle_app_proxy(self, path)

        return self._send_error(404, f"endpoint not found: {path}")

    def do_POST(self):
        self._log_request()
        path = urllib.parse.urlparse(self.path).path
        params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))

        if path == "/api/v1/auth/login":
            data = self._json_body()
            if not data:
                return self._send_error(400, "invalid body")
            user = data.get("username", "")
            passwd = data.get("password", "")
            if user == config["auth"]["username"] and passwd == config["auth"]["password"]:
                from .auth import make_token
                token = make_token(user)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Set-Cookie", "opencasa_token=" + urllib.parse.quote(token) + "; Path=/; SameSite=Lax; HttpOnly")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
                self.end_headers()
                self._write(json.dumps({"token": token, "user": user}).encode())
                return
            return self._send_error(401, "invalid credentials")

        # Proxy POST skips auth
        if path.startswith("/app/") and len(path) > 5:
            from .proxy import handle_app_proxy
            return handle_app_proxy(self, path)

        if not self._check_auth():
            return

        if path == "/api/v1/files/write":
            from .filemanager import handle_write_file
            return handle_write_file(self)

        if path == "/api/v1/files/rename":
            from .filemanager import handle_rename_file
            return handle_rename_file(self)

        if path == "/api/v1/files/delete":
            from .filemanager import handle_delete_file
            return handle_delete_file(self)

        if path == "/api/v1/files/mkdir":
            from .filemanager import handle_mkdir
            return handle_mkdir(self)

        if path == "/api/v1/files/upload":
            from .filemanager import handle_upload
            return handle_upload(self, params)

        if path == "/api/v1/disks/mount":
            from .system import mount_fs
            data = self._json_body()
            if not data:
                return self._send_error(400, "invalid body")
            r = mount_fs(data.get("device", ""), data.get("mountpoint", ""), data.get("fstype", ""))
            if r.returncode == 0:
                return self._send_json({"success": True})
            return self._send_error(500, r.stderr.strip() or "mount failed")

        if path == "/api/v1/disks/umount":
            from .system import umount_fs
            data = self._json_body()
            if not data:
                return self._send_error(400, "invalid body")
            r = umount_fs(data.get("mountpoint", ""))
            if r.returncode == 0:
                return self._send_json({"success": True})
            return self._send_error(500, r.stderr.strip() or "umount failed")

        if path.startswith("/api/v1/apps/"):
            rest = path[len("/api/v1/apps/"):].strip("/")
            if rest:
                parts = rest.split("/", 1)
                app_id = parts[0]
                action = parts[1] if len(parts) > 1 else ""
                from .appmanager import run_app, start_web_app, stop_web_app, uninstall_app
                if action == "run":
                    return self._send_json(run_app(app_id))
                if action == "start":
                    return self._send_json(start_web_app(app_id))
                if action == "stop":
                    return self._send_json(stop_web_app(app_id))
                if action == "uninstall":
                    return self._send_json(uninstall_app(app_id))

        if path == "/api/v1/notify":
            from .notifications import push_notification
            data = self._json_body()
            if not data:
                return self._send_error(400, "invalid body")
            n = push_notification(
                data.get("app_id", ""),
                data.get("title", ""),
                data.get("message", ""),
                data.get("severity", "info"),
            )
            return self._send_json(n)

        if path == "/api/v1/db/set" or path == "/api/v1/db/set/":
            data = self._json_body()
            if not data or "key" not in data:
                return self._send_error(400, "missing key")
            from .database import set
            set(data["key"], data.get("value", ""))
            return self._send_json({"success": True})

        if path == "/api/v1/db/delete" or path == "/api/v1/db/delete/":
            data = self._json_body()
            if not data or "key" not in data:
                return self._send_error(400, "missing key")
            from .database import delete
            delete(data["key"])
            return self._send_json({"success": True})

        return self._send_error(404, f"endpoint not found: {path}")

    def do_PUT(self):
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/app/") and len(path) > 5:
            from .proxy import handle_app_proxy
            return handle_app_proxy(self, path)
        return self._send_error(404, f"endpoint not found: {path}")

    def do_DELETE(self):
        path = urllib.parse.urlparse(self.path).path

        # Proxy DELETE skips auth
        if path.startswith("/app/") and len(path) > 5:
            from .proxy import handle_app_proxy
            return handle_app_proxy(self, path)

        if not self._check_auth():
            return

        return self._send_error(404, f"endpoint not found: {path}")


class ThreadedHTTPServer(HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def process_request(self, request, client_address):
        t = threading.Thread(target=self.finish_request, args=(request, client_address))
        t.daemon = True
        t.start()


# ── Main ──

def main():
    parser = argparse.ArgumentParser(description="OpenCasa Server Manager")
    parser.add_argument("-c", "--config", default="/etc/opencasa.json", help="config path")
    parser.add_argument("-p", "--port", type=int, help="override port")
    parser.add_argument("-d", "--data", default="/usr/local/webui", help="data directory")
    parser.add_argument("--debug", action="store_true", help="enable debug output")
    args = parser.parse_args()

    set_data_dir(args.data)
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, "apps"), exist_ok=True)

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )
    logging.getLogger().handlers[0].flush = lambda: None

    load_config(args.config)
    if not args.debug and config["log"]["file"]:
        fh = logging.FileHandler(config["log"]["file"])
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logging.getLogger().addHandler(fh)

    if not config.get("master_key"):
        config["master_key"] = base64.b64encode(os.urandom(48)).decode()
        save_config()
        logging.info("generated new master key")
        sys.stdout.write(f"\n  ⚠  MASTER KEY (salvala in un posto sicuro):\n")
        sys.stdout.write(f"  ┌{'─'*48}┐\n")
        sys.stdout.write(f"  │ {config['master_key']} │\n")
        sys.stdout.write(f"  └{'─'*48}┘\n")
        sys.stdout.write(f"  Già salvata in {CONFIG_PATH}\n\n")
        sys.stdout.flush()

    from . import database
    try:
        database.init(config["master_key"], os.path.join(DATA_DIR, "database"))
    except Exception as e:
        logging.warning("database init failed, regenerating: %s", e)
        import shutil
        shutil.rmtree(os.path.join(DATA_DIR, "database"), ignore_errors=True)
        database.init(config["master_key"], os.path.join(DATA_DIR, "database"))

    from .appmanager import init as appmanager_init
    from .notifications import load_notifications
    appmanager_init()
    load_notifications()

    host = config["server"]["host"]
    port = args.port or config["server"]["port"]

    print(r"""
    ╔══════════════════════════════════╗
    ║        ___                      ║
    ║       / _ \ _ __   ___  _ __    ║
    ║      | | | | '_ \ / _ \| '_ \   ║
    ║      | |_| | |_) | (_) | |_) |  ║
    ║       \___/| .__/ \___/| .__/   ║
    ║            |_|         |_|      ║
    ║          OpenCasa v1.0          ║
    ║  Server Manager for OpenBSD     ║
    ╚══════════════════════════════════╝""")

    server = ThreadedHTTPServer((host, port), OpenCasaHandler)
    server.socket.settimeout(1.0)
    logging.info("webui starting on %s:%d", host, port)
    print(f"  → http://{host}:{port}\n")

    running = True

    def _stop(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    while running:
        try:
            server.handle_request()
        except KeyboardInterrupt:
            break
    server.server_close()
    logging.info("webui stopped")
