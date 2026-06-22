# OpenCasa REST API

All endpoints return JSON (`Content-Type: application/json`).  
Authentication uses **Bearer JWT** in the `Authorization` header (or `?token=` query parameter).

Base path: `/api/v1`

---

## Authentication

### `GET /api/v1/setup`
Check whether the first-boot setup wizard is needed (no auth required).

**Response `200`:**
```json
{"setup_needed": true}
```

### `POST /api/v1/setup`
Create the first non-root user during initial setup (no auth required).  
Returns `403` if users already exist, `409` if the username is taken.

**Request body:**
```json
{"username": "alice", "password": "s3cret"}
```

**Response `200`:**
```json
{"success": true}
```

### `POST /api/v1/auth/login`
Login and obtain a JWT token. This endpoint does **not** require authentication.

**Request body:**
```json
{"username": "admin", "password": "admin"}
```

**Response `200`:**
```json
{"token": "eyJhbG...", "user": "admin"}
```

**Response `401`:**
```json
{"error": "invalid credentials"}
```

### `GET /api/v1/auth/check`
Verify that the current token is valid.

**Response `200`:**
```json
{"ok": true, "user": "admin", "is_root": true, "avatar": "data:image/..."}
```

### `GET /api/v1/auth/status`
Check if the system is in tamper mode (no auth required).

**Response `200`:**
```json
{"tamper": false}
```

### `POST /api/v1/auth/verify-root-change`
Step 1 of tamper recovery: verify the previous root password (no auth required).

**Request body:**
```json
{"password": "previous-root-password"}
```

**Response `200`:**
```json
{"verified": true}
```

**Response `403`:**
```json
{"error": "incorrect password"}
```

### `POST /api/v1/auth/recovery-password`
Step 2 of tamper recovery: set a new root password after verification (no auth required).

**Request body:**
```json
{"password": "new-root-password"}
```

**Response `200`:**
```json
{"success": true}
```

---

## Users

### `GET /api/v1/users`
List all non-root users (root only).

**Response `200`:**
```json
{"users": ["alice", "bob"]}
```

### `POST /api/v1/users`
Create a new user (root only).

**Request body:**
```json
{"username": "charlie", "password": "s3cret"}
```

**Response `200`:**
```json
{"success": true}
```

**Response `409`:**
```json
{"error": "username already exists"}
```

### `POST /api/v1/users/<username>/delete`
Delete a user by username (root only). You cannot delete yourself.

**Response `200`:**
```json
{"success": true}
```

### `POST /api/v1/users/password`
Change the current user's password. Requires `current_password` for verification.

**Request body:**
```json
{"current_password": "oldpass", "password": "newpass"}
```

**Response `200`:**
```json
{"success": true}
```

**Response `403`:**
```json
{"error": "current password does not match"}
```

### `POST /api/v1/users/check`
Check if a username exists (no auth required). Used by the two-phase login flow.

**Request body:**
```json
{"username": "alice"}
```

**Response `200`:**
```json
{"exists": true, "avatar": "data:image/...", "name": "alice"}
```

### `POST /api/v1/users/avatar`
Set the current user's avatar. Value should be a base64 data URI (`data:image/...;base64,...`).

**Request body:**
```json
{"avatar": "data:image/png;base64,iVBORw0KGgo..."}
```

**Response `200`:**
```json
{"success": true}
```

---

## System

### `GET /api/v1/system/stats`
CPU, memory, uptime.

**Response `200`:**
```json
{
  "cpu": {
    "user": 5.2,
    "nice": 0,
    "sys": 3.1,
    "idle": 91.7,
    "model": "74xx/75xx (PowerPC G5)",
    "freq_mhz": 2000,
    "cores": 2
  },
  "memory": {
    "total": 1073741824,
    "used": 536870912,
    "free": 536870912,
    "buffers": 0,
    "page_size": 4096
  },
  "uptime": 123456,
  "memory_unit": "MB",
  "language": "en"
}
```

- `memory_unit` and `language` come from config (`ui.memory_unit`, `ui.language`).
- On OpenBSD/macppc, memory is calculated from `vmstat -s` (managed − free − inactive).  
  On Linux, from `/proc/meminfo`.
- CPU stats from `vmstat 1 2` (header-based field detection).

### `GET /api/v1/system/info`
Host system information.

**Response `200`:**
```json
{
  "hostname": "powerbook",
  "ostype": "OpenBSD",
  "osrelease": "7.6",
  "osversion": "7.6",
  "machine": "macppc",
  "model": "PowerMac11,2"
}
```

Fields vary by platform. On OpenBSD, values come from sysctl; on Linux, from uname.

### `GET /api/v1/health`
Healthcheck endpoint (no auth required).

**Response `200`:**
```json
{"status": "ok", "timestamp": "2026-06-22T12:00:00+00:00"}
```

### `GET /api/v1/storage`
Filesystem disk usage (via `df -h`).

**Response `200`:**
```json
{
  "filesystems": [
    {
      "device": "sd0a",
      "total": "5.8G",
      "used": "2.3G",
      "avail": "3.2G",
      "capacity": 40.0,
      "mount": "/"
    }
  ]
}
```

### `GET /api/v1/disks`
List available disk devices (root only).

**Response `200`:**
```json
{"disks": [{"device": "sd0", "size": "238.5G", "mount": "/"}, {"device": "sd1i", "size": "28.9G", "mount": "/mnt/usb"}]}
```

### `POST /api/v1/disks/mount`
Mount a filesystem.

**Request body:**
```json
{"device": "/dev/sd1i", "mountpoint": "/mnt/usb", "fstype": "ext2fs"}
```

`fstype` is optional (default: auto/filesystem-dependent).

### `POST /api/v1/disks/umount`
Unmount a filesystem.

**Request body:**
```json
{"mountpoint": "/mnt/usb"}
```

---

## File Manager

All file operations are restricted to `allowed_prefixes` configured in `opencasa.json`  
(default: `/home`, `/var/www`, `/mnt`, `/tmp`, `/opt`).

### `GET /api/v1/files?path=/home/user`
List directory contents.

**Response `200`:**
```json
{
  "path": "/home/user",
  "entries": [
    {
      "name": "Documents",
      "size": 512,
      "is_dir": true,
      "mode": "0o40755",
      "mod_time": "2026-06-21T12:00:00"
    },
    {
      "name": "readme.txt",
      "size": 1234,
      "is_dir": false,
      "mode": "0o100644",
      "mod_time": "2026-06-20T08:30:00"
    }
  ]
}
```

Entries are sorted: directories first, then files, alphabetically.

### `GET /api/v1/files/read?path=/home/user/readme.txt`
Read file contents as text.

**Response `200`:**
```json
{"content": "file contents here..."}
```

### `POST /api/v1/files/write`
Write (or create) a file.

**Request body:**
```json
{"path": "/home/user/readme.txt", "content": "new content"}
```

### `POST /api/v1/files/rename`
Rename or move a file.

**Request body:**
```json
{"path": "/home/user/old.txt", "new_name": "new.txt"}
```

### `POST /api/v1/files/delete`
Delete a file or empty directory.

**Request body:**
```json
{"path": "/home/user/old.txt"}
```

### `POST /api/v1/files/mkdir`
Create a directory.

**Request body:**
```json
{"path": "/home/user/newdir"}
```

### `POST /api/v1/files/upload`
Upload a file (multipart/form-data).

Form fields:
| Field  | Value |
|--------|-------|
| `file` | (binary file data) |
| `path` | Destination path (e.g. `/home/user/file.zip`) |

### `GET /api/v1/files/download?path=/home/user/file.zip`
Download a file. Returns the raw binary with appropriate `Content-Type`.

---

## Apps

Apps are Python scripts organized in folders under `apps_dir` (default: `/usr/local/webui/apps`).  
Each app has a `manifest.json`. Read more about the manifest format in [examples/apps](examples/apps/).

### `GET /api/v1/apps`
List all installed apps.

**Response `200`:**
```json
{
  "apps": [
    {
      "id": "system-monitor",
      "name": "System Monitor",
      "description": "Real-time CPU and memory usage",
      "version": "1.0.0",
      "author": "OpenCasa",
      "entry": "app.py",
      "type": "widget",
      "autostart": false,
      "port": 0,
      "permissions": ["system:monitor"],
      "path": "/usr/local/webui/apps/system-monitor",
      "status": "stopped",
      "pid": 0
    }
  ]
}
```

| App type | Description |
|----------|-------------|
| `tool` | Run on demand; output displayed in the UI |
| `widget` | Like tool, but output is cached for the dashboard |
| `web` | Background process on a port, proxied via `/app/<id>/` |

### `GET /api/v1/apps/<id>`
App details, including the last 5 execution logs.

**Response `200`:**
```json
{
  "app": {
    "id": "system-monitor",
    "name": "System Monitor",
    "description": "Real-time CPU and memory usage",
    "version": "1.0.0",
    "author": "OpenCasa",
    "entry": "app.py",
    "type": "widget",
    "autostart": false,
    "port": 0,
    "permissions": ["system:monitor"],
    "path": "/usr/local/webui/apps/system-monitor",
    "status": "stopped",
    "pid": 0,
    "logs": [
      {
        "timestamp": "2026-06-21T10:30:00+00:00",
        "stdout": "...",
        "stderr": "",
        "returncode": 0
      }
    ]
  }
}
```

### `POST /api/v1/apps/<id>/run`
Execute a `tool` or `widget` app. The script receives `OPENCASA_CONTEXT` environment variable  
with `{app_id, name, permissions, api_url}`. Stdout/stderr are captured.

**Response `200` (success):**
```json
{
  "stdout": "Hello from System Monitor!\nCPU: 23%\n",
  "stderr": "",
  "returncode": 0
}
```

**Response `200` (error):**
```json
{"error": "app.py not found"}
```

Timeout: 30 seconds.

### `POST /api/v1/apps/<id>/start`
Start a `web` type app as a background process. The app's script must listen on the port  
declared in `manifest.json` (`port` field).

**Response `200`:**
```json
{"success": true, "pid": 12345}
```

### `POST /api/v1/apps/<id>/stop`
Stop a running `web` app.

**Response `200`:**
```json
{"success": true}
```

### `GET /api/v1/apps/<id>/logs`
Get execution logs for an app (last 20 entries by default).

**Response `200`:**
```json
{
  "logs": [
    {
      "timestamp": "2026-06-21T10:30:00+00:00",
      "stdout": "...",
      "stderr": "",
      "returncode": 0
    }
  ]
}
```

### `GET /api/v1/apps/<id>/widget`
Get cached output for a `widget` app. Updated every time the app is run.

**Response `200` (data available):**
```json
{
  "data": {"cpu": 23, "memory": {"used_pct": 45.0, "label": "45%", "detail": "256M free / 512M total"}}
}
```

**Response `200` (no data):**
```json
{"data": null}
```

### `GET /api/v1/apps/<id>/icon`
Serve the app's icon file (`icon.svg`, `icon.png`, etc.). Returns raw image with correct `Content-Type`.  
**Response `404`** if no icon file exists.

### `POST /api/v1/apps/<id>/confirm`
Confirm the permissions required by an app. Stores the permission list hash in the  
user's database so subsequent `run`/`start` calls skip the permission prompt.

**Response `200`:**
```json
{"success": true}
```

### `POST /api/v1/apps/<id>/uninstall`
Delete the app folder from disk. The app must be stopped first.

**Response `200`:**
```json
{"success": true}
```

### Web App Proxy

When a `web` type app is running, its web interface is accessible at:

```
/app/<id>/<path>
```

The backend proxies requests to `http://127.0.0.1:<port>/<path>`.  
Requests without authentication are **not** proxied; authentication is required.

---

## Notifications

### `GET /api/v1/notifications`
List all notifications.

**Response `200`:**
```json
{
  "notifications": [
    {
      "app_id": "system-monitor",
      "title": "CPU high",
      "message": "CPU usage exceeded 80%",
      "severity": "warning",
      "timestamp": "2026-06-21T10:30:00+00:00"
    }
  ]
}
```

### `POST /api/v1/notify`
Push a new notification.

**Request body:**
```json
{
  "app_id": "my-app",
  "title": "Something happened",
  "message": "Details here",
  "severity": "info"
}
```

`severity` can be `info`, `warning`, or `error`.

---

## Static Files

Requests to `/` and any non-API path serve static files from the frontend directory.  
Lookup order:

1. `frontend/dist/`
2. `frontend/`
3. `DATA_DIR/` (default: `/usr/local/webui`)
4. `DATA_DIR/frontend/dist/`
5. `DATA_DIR/frontend/`

---

## Error Responses

All errors follow the format:

```json
{"error": "description"}
```

Common HTTP status codes:

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad request (invalid body, missing params) |
| 401 | Unauthorized (missing or invalid token) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Resource not found |
| 405 | Method not allowed |
| 409 | Conflict (e.g. username taken) |
| 413 | Request entity too large (upload/proxy body exceeds limit) |
| 429 | Too many requests (rate-limited login) |
| 500 | Internal server error |
| 502 | Bad gateway (proxy upstream failure) |
| 503 | Service unavailable (web app not running) |

---

## User Database

An encrypted key-value store for persisting user preferences on the server.
Data is encrypted per-value using HMAC-CTR with a key derived from the
`master_key` in the config. Integrity is verified with HMAC-SHA256.

### `GET /api/v1/db/get?key=mykey`

Get a stored value by key.

**Response `200`:**
```json
{"value": "the-stored-value"}
```
`null` if the key does not exist.

### `POST /api/v1/db/set`

Set a key-value pair.

**Request body:**
```json
{"key": "widget_myapp", "value": "true"}
```

**Response `200`:**
```json
{"success": true}
```

### `POST /api/v1/db/delete`

Delete a key.

**Request body:**
```json
{"key": "widget_myapp"}
```

**Response `200`:**
```json
{"success": true}
```

### `GET /api/v1/db/list?prefix=widget_`

List all keys with an optional prefix filter.

**Response `200`:**
```json
{"keys": ["widget_myapp", "widget_otherapp"]}
```

---

## CORS

All API responses include:

```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
Access-Control-Allow-Headers: Content-Type, Authorization
```

Preflight `OPTIONS` requests are handled at `/api/v1/...`.
