# OpenCasa

Server management panel for **OpenBSD/macppc** (PowerPC G3/G4/G5), inspired by CasaOS.

**Zero compilation, zero dependencies** — pure Python stdlib backend + standalone HTML/JS frontend.

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

## Features

- **Dashboard** — real-time CPU/memory/storage meters, widget grid, installed apps
- **File Manager** — browse, upload, download, create, rename, delete, text editor
- **Apps** — install/uninstall containerized apps (tool, widget, web types) with permission system
- **Notifications** — system and app-level alerts
- **Disk Manager** — mount/unmount removable drives
- **Editor** — built-in textarea editor (no Monaco — too heavy for G3)
- **i18n** — English and Italian (configurable via `ui.language`)
- **Mobile-friendly** — hamburger menu, responsive layout
- **Authentication** — optional JWT-based login with configurable session TTL
- **Web App Proxy** — web-type apps run on their own port, proxied via `/app/<id>/`

## Requirements

- **OpenBSD 7.x** (tested on macppc, works on any arch)
- **Python 3** (from base system or `pkg_add python`)
- ~30 MB disk, ~40 MB RAM at idle

Works on any Unix with Python 3 (Linux, BSD, macOS) via `system.platform: "auto"` or forced `"linux"`/`"openbsd"`.

## Quick Install

```sh
# As root on the target machine:
mkdir -p /usr/local/webui/apps
cp backend/webui.py /usr/local/webui/
cp -r backend/webui /usr/local/webui/
cp frontend/dist/index.html /usr/local/webui/
cp frontend/dist/favicon.svg /usr/local/webui/
cp scripts/webui /etc/rc.d/webui
chmod +x /etc/rc.d/webui
cp opencasa.json.example /etc/opencasa.json

# Generate a JWT secret
openssl rand -hex 32
# Edit /etc/opencasa.json and paste it into jwt_secret

# Enable and start
rcctl enable webui
rcctl start webui
```

Or use the Makefile: `doas make install`

## Configuration

`/etc/opencasa.json`:

| Key | Default | Description |
|-----|---------|-------------|
| `server.host` | `"0.0.0.0"` | Bind address |
| `server.port` | `80` | HTTP port |
| `server.tls` | `false` | Enable HTTPS |
| `server.cert_file` | `""` | TLS certificate path |
| `server.key_file` | `""` | TLS key path |
| `auth.enabled` | `true` | Require login |
| `auth.username` | `"admin"` | Login username |
| `auth.password` | `"admin"` | Login password |
| `auth.jwt_secret` | *(random)* | HMAC key for JWT tokens |
| `auth.session_ttl` | `"24h"` | Token validity duration |
| `filesystem.allowed_prefixes` | `["/home","/var/www","/mnt","/tmp","/opt"]` | File manager access control |
| `filesystem.max_upload_size` | `100` | Max upload size in MB |
| `system.platform` | `"auto"` | Force platform detection (`"auto"`, `"linux"`, `"openbsd"`) |
| `ui.memory_unit` | `"MB"` | Memory display unit (`"MB"` or `"GB"`) |
| `ui.language` | `"en"` | UI language (`"en"` or `"it"`) |
| `apps_dir` | `"/usr/local/webui/apps"` | Apps directory |
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
  "env": {"MY_VAR": "value"}
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

## API

Complete API reference in [API.md](API.md). Summary:

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/v1/auth/login` | POST | No | Login → JWT |
| `/api/v1/auth/check` | GET | Yes | Verify token |
| `/api/v1/system/stats` | GET | Yes | CPU, memory, uptime |
| `/api/v1/system/info` | GET | Yes | Hostname, kernel, platform |
| `/api/v1/storage` | GET | Yes | Filesystem usage |
| `/api/v1/files` | GET | Yes | List directory |
| `/api/v1/files/read` | GET | Yes | Read file |
| `/api/v1/files/write` | POST | Yes | Write/create file |
| `/api/v1/files/upload` | POST | Yes | Upload file (multipart) |
| `/api/v1/files/download` | GET | Yes | Download file |
| `/api/v1/apps` | GET | Yes | List apps |
| `/api/v1/apps/<id>/run` | POST | Yes | Run tool/widget |
| `/api/v1/apps/<id>/start` | POST | Yes | Start web app |
| `/api/v1/apps/<id>/stop` | POST | Yes | Stop web app |
| `/api/v1/apps/<id>/widget` | GET | Yes | Get cached widget data |
| `/api/v1/apps/<id>/icon` | GET | No | App icon image |
| `/api/v1/apps/<id>/uninstall` | POST | Yes | Delete app |
| `/api/v1/notifications` | GET | Yes | List notifications |
| `/api/v1/notify` | POST | Yes | Push notification |
| `/app/<id>/<path>` | * | No | Web app proxy |

## Architecture

```
┌─────────────────┐     HTTP      ┌──────────────┐
│  Browser         │◄────────────►│  webui.py     │
│  (index.html)    │              │  (Python      │
│  Pure JS/HTML    │              │   stdlib      │
│  No frameworks   │              │   HTTP server)│
└─────────────────┘              └──────┬───────┘
                                        │
                          ┌─────────────┼──────────────┐
                          ▼             ▼              ▼
                   ┌──────────┐  ┌──────────┐  ┌──────────┐
                   │ auth.py  │  │system.py │  │appmanager│
                   │ JWT HMAC │  │CPU/mem   │  │.py       │
                   └──────────┘  │vmstat    │  │ exec/    │
                                 │/proc     │  │ proxy/   │
                                 └──────────┘  │ cache    │
                                               └──────────┘
```

- **Backend**: Pure Python stdlib `http.server` — modular in `backend/webui/` (auth, system, filemanager, appmanager, notifications, proxy)
- **Frontend**: Single `index.html` with inline CSS/JS — no build step, no frameworks, no CDN dependencies
- **Web apps**: Python subprocesses, proxied by the backend

## Design for Old Hardware

OpenCasa is optimized for PowerPC G3/G4/G5 (300 MHz–2 GHz, 256 MB–1 GB RAM):

- **No compilation** — interpreted Python only
- **No npm/node/webpack** — frontend is a single HTML file
- **No CDN** — zero network requests after initial load
- **No browser-side framework** — vanilla JS, direct DOM manipulation
- **No Monaco Editor** — replaced with textarea (Monaco is 15+ MB)
- **No icon HTTP requests** in sidebar — uses CSS letter initials instead
- **Widgets load after dashboard** — non-blocking `.then()`
- **Targeted DOM updates** — `updateDashboardValues()` avoids full re-render on auto-refresh
- **Partial API resilience** — one failed endpoint doesn't break the page

## Development

```sh
# Run locally (no root needed)
python3 backend/webui.py -c opencasa.json.example -d . --debug

# Open browser
open http://localhost:80
```

### Project Structure

```
├── backend/
│   ├── webui.py              # HTTP server entry point
│   └── webui/                # Python package
│       ├── __init__.py       # Request routing + handlers
│       ├── auth.py           # JWT authentication
│       ├── system.py         # CPU/memory/platform info
│       ├── filemanager.py    # File operations
│       ├── appmanager.py     # App lifecycle + widget cache
│       ├── notifications.py  # Notification storage
│       └── proxy.py          # Web app HTTP proxy
├── frontend/
│   └── dist/
│       ├── index.html        # Single-page frontend
│       └── locales/          # Translation files
├── examples/
│   └── apps/                 # Example app manifests & scripts
├── scripts/webui             # OpenBSD rc.d script
├── API.md                    # Full API reference
├── DEPLOY.md                 # Deployment instructions
├── Makefile                  # Install helper
└── opencasa.json.example     # Configuration template
```

## License

MIT
