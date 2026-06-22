# OpenCasa

**OpenCasa** is a lightweight server management panel inspired by CasaOS, designed for old/low-power hardware (PowerPC G3/G4/G5, single-core ARM, old x86).

**Zero compilation, zero dependencies** — pure Python stdlib backend + standalone HTML/JS frontend. No npm, no node_modules, no CDN, no build step.

```
┌──────────────────────────────────────────────────────────┐
│  OpenCasa  │  Dashboard  │  Files  │  Apps  │  Editor   │
├──────────────────────────────────────────────────────────┤
│  CPU  ████████░░ 52%     Memory  ██████░░░░ 45%         │
│  ─────────────────────────────────────────────────────── │
│  Widgets                          │  Installed Apps      │
│  ┌────────────────────┐           │  ┌────────────────┐  │
│  │ System Monitor     │           │  │ Calendar       │  │
│  │ CPU: 23% │ Mem: 45%│           │  │ Hello Web      │  │
│  └────────────────────┘           │  └────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

## Supported Systems

| System | Status | Notes |
|--------|--------|-------|
| OpenBSD/macppc (G3/G4/G5) | Primary target | Tested on iMac G3 600 MHz, 384 MB RAM |
| Linux (x86_64, arm, etc.) | Works | Uses `/proc/` for stats |
| Any Unix with Python 3 | Should work | BSDs, macOS (not heavily tested) |

Platform detection is automatic via `system.platform: "auto"` in config. Override with `"linux"` or `"openbsd"` if needed.

## Features

- **Dashboard** — real-time CPU/memory/storage/network meters, widget grid, installed apps
- **File Manager** — browse, upload, download, create, rename, delete, inline text editor
- **Apps** — containerized app system (tool, widget, web types) with permission confirmation
- **Notifications** — system and app-level alerts, persisted to disk
- **Web App Proxy** — web-type apps run on their own port, proxied via `/app/<id>/`
- **Disk Manager** — mount/unmount removable drives
- **Multi-user** — root + regular users, configurable root account, PBKDF2 password hashing
- **Encrypted Database** — per-value HMAC-CTR encrypted SQLite key-value store
- **Authentication** — JWT-based login with configurable session TTL, optional (can disable)
- **Rate Limiting** — 10 failed login attempts per IP in 5 minutes
- **i18n** — English and Italian (configurable via `ui.language`)
- **Mobile-friendly** — hamburger menu, responsive layout

## Requirements

- **Python 3** (stdlib only — no pip packages)
- ~30 MB disk, ~40 MB RAM at idle
- For apps: system user `opencasa` (create manually: `doas useradd -m opencasa`)

## Quick Install

```sh
# As root on the target machine:
mkdir -p /usr/local/webui/apps
cp backend/webui.py /usr/local/webui/
cp -r backend/webui /usr/local/webui/
cp frontend/dist/index.html /usr/local/webui/
cp frontend/dist/style.css /usr/local/webui/
cp frontend/dist/app.js /usr/local/webui/
cp frontend/dist/favicon.svg /usr/local/webui/
cp -r frontend/dist/locales /usr/local/webui/locales
cp scripts/webui /etc/rc.d/webui      # OpenBSD
# or: cp scripts/webui.service /etc/systemd/system/  # Linux
chmod +x /etc/rc.d/webui
cp opencasa.json.example /etc/opencasa.json

# On first boot, OpenCasa auto-generates:
#   - Master key for database encryption (displayed on console)
#   - JWT secret (replaces the placeholder)
#   - Random 16-character root password (displayed on console, replaces the default "admin")

# Enable and start
rcctl enable webui      # OpenBSD
rcctl start webui
```

Or use `doas make install`.

## Configuration

`/etc/opencasa.json`:

| Key | Default | Description |
|-----|---------|-------------|
| `server.host` | `"0.0.0.0"` | Bind address |
| `server.port` | `80` | HTTP port |
| `auth.enabled` | `true` | Require login |
| `auth.root_user` | `"root"` | Root username (from config, not DB) |
| `auth.root_password` | `"admin"` | Root password (replaced with random 16-char on first boot, then hashed) |
| `auth.jwt_secret` | *(auto-generated)* | HMAC key for JWT tokens |
| `auth.session_ttl` | `"24h"` | Token validity duration |
| `filesystem.allowed_prefixes` | `["/home","/var/www","/mnt","/tmp","/opt"]` | File manager access control |
| `filesystem.max_upload_size` | `100` | Max upload size in MB |
| `system.platform` | `"auto"` | Force platform detection |
| `ui.memory_unit` | `"MB"` | Memory display unit (`"MB"` or `"GB"`) |
| `ui.language` | `"en"` | UI language (`"en"` or `"it"`) |
| `apps_dir` | `"/usr/local/webui/apps"` | Apps directory |
| `app_user` | `"opencasa"` | System user for running apps |
| `master_key` | *(auto-generated)* | Base64 key for encrypted user database |
| `apps_autostart` | `true` | Auto-start web apps on boot |

## App System

Apps are folders in `apps_dir`, each containing a `manifest.json` and scripts.

### App Types

| Type | Description | Lifecycle |
|------|-------------|-----------|
| `tool` | Run on demand, output shown in UI | `subprocess.run()`, 30s timeout |
| `widget` | Like tool, output cached for dashboard | Same as tool + in-memory cache (30s TTL) |
| `web` | Background HTTP server on a port | `subprocess.Popen()`, proxied via `/app/<id>/` |

### Manifest Format

```json
{
  "name": "My App",
  "description": "What it does",
  "version": "1.0.0",
  "author": "You",
  "entry": "app.py",
  "type": "widget",
  "port": 0,
  "autostart": false,
  "permissions": ["system:monitor"],
  "has_widget": true
}
```

Context passed to apps via `OPENCASA_CONTEXT` env var (JSON with `app_id`, `name`, `permissions`, `api_url`).
Web apps receive `OPENCASA_ACTION=widget` when polled for widget data (output JSON and exit instead of starting a server).

### Example Apps

| App | Type | Description |
|-----|------|-------------|
| `system-monitor` | `widget` | Real-time CPU and memory dashboard widget |
| `hello-world` | `tool` | Prints system info on demand |
| `disk-usage` | `tool` | Shows disk usage for all mountpoints |
| `calendar` | `web` (port 18997) | Full calendar web app with dashboard widget support |
| `hello-web` | `web` (port 18998) | Minimal test web app |

Install via `sh examples/apps/install-examples.sh`

### App Permissions

Apps declare required permissions in their manifest. Before first run, the user must confirm via a dialog. Confirmed permissions are stored in the encrypted database. Apps with an empty `permissions` list (e.g. `hello-web`, `calendar`) skip the confirmation and start directly.

### App User

Apps are designed to run as an unprivileged system user (`app_user`, default `opencasa`) for sandboxing. On **Linux**, the backend drops privileges via `os.setuid()`/`os.setgid()`. On **OpenBSD**, privilege dropping is not fully supported — apps currently run as root. Permission enforcement (confirmation dialog, restricted file access) still applies regardless of the running user.

Create the app user manually:
```sh
doas useradd -m opencasa
doas passwd opencasa
```

If the user is missing, the Apps tab shows a warning banner and app execution is blocked.

## Limitations

- **OpenBSD app execution**: apps run as root (privilege dropping via `os.setuid()` is not reliable on all OpenBSD versions/configurations). Permission confirmations are still enforced.
- **No HTTPS in daemon**: terminate behind nginx/haproxy for TLS.
- **No test suite**: backend has no automated tests.
- **No package-lock.json**: frontend dependency versions are not locked (Svelte/Vite build only needed for development, not deployment).
- **Config save is not fully atomic**: uses `os.replace()` which is atomic on most filesystems but not guaranteed on all.

## Database System

User preferences (widget visibility, app settings) are stored in an **encrypted SQLite database** at `DATA_DIR/database/opencasa.db`.

- First boot: `os.urandom(48)` → base64 → written to config as `master_key`
- Startup: PBKDF2-SHA256 derives two 32-byte keys (one-time cost, ~150ms on G3)
- Each value encrypted with HMAC-SHA256 in CTR mode + integrity HMAC tag
- If master key is lost/corrupted, database is detected and regenerated automatically

## API

Complete API reference in [API.md](API.md). Summary:

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/v1/auth/login` | POST | No | Login |
| `/api/v1/auth/check` | GET | Yes | Verify token |
| `/api/v1/setup` | GET/POST | No | First-boot wizard |
| `/api/v1/system/stats` | GET | Yes | CPU, memory, uptime, network |
| `/api/v1/system/info` | GET | Yes | Hostname, kernel, platform |
| `/api/v1/storage` | GET | Yes | Filesystem usage |
| `/api/v1/files/*` | * | Yes | File CRUD + upload/download |
| `/api/v1/apps` | GET | Yes | List apps |
| `/api/v1/apps/<id>/*` | * | Yes | Run, start, stop, confirm, uninstall |
| `/api/v1/users/*` | * | Yes | User management (root only for create/delete) |
| `/api/v1/db/*` | * | Yes | User-scoped encrypted key-value |
| `/api/v1/notifications` | GET | Yes | List notifications |
| `/api/v1/notify` | POST | Yes | Push notification |
| `/app/<id>/<path>` | * | No | Web app proxy |

## Architecture

```
Browser  ◄──── HTTP ────►  webui.py (Python stdlib HTTP server)
                                │
                    ┌───────────┼──────────────┐
                    ▼           ▼              ▼
              auth.py      system.py     appmanager.py
              JWT/HMAC     CPU/mem via    exec/proxy/
                           vmstat/proc    cache/perms
```

## Design for Old Hardware

Optimized for PowerPC G3/G4/G5 (300 MHz–2 GHz, 256 MB–1 GB RAM):

- No compilation — interpreted Python only
- No npm/node/webpack — frontend is a single HTML file
- No CDN — zero network requests after initial load
- No browser framework — vanilla JS, direct DOM manipulation
- No Monaco Editor — textarea instead (Monaco is 15+ MB)
- No icon HTTP requests in sidebar — CSS letter initials
- Targeted DOM updates — avoids full re-render on auto-refresh
- Partial API resilience — one failed endpoint doesn't break the page

## Development

```sh
# Run locally (no root needed)
python3 backend/webui.py -c opencasa.json.example -d . --debug -p 8080

# Or with all apps:
mkdir -p apps && cp -r examples/apps/* apps/
python3 backend/webui.py -c opencasa.json.example -d . --debug -p 8080
```

## Project Structure

```
backend/webui.py          # Entry point
backend/webui/            # Python package
  __init__.py             # HTTP routing, config, main()
  auth.py                 # JWT + user management
  system.py               # CPU/mem/disk/network stats
  filemanager.py          # File CRUD
  appmanager.py           # App lifecycle, cache, permissions
  database.py             # Encrypted SQLite KV store
  notifications.py        # Notification persistence
  proxy.py                # Web app reverse proxy
frontend/dist/            # Built frontend (static files)
  index.html, style.css, app.js, favicon.svg
  locales/                # en.json, it.json
examples/apps/            # Example app manifests + scripts
scripts/webui             # OpenBSD rc.d script
scripts/webui.service     # Linux systemd unit
```

## License

GNU General Public License v3.0
