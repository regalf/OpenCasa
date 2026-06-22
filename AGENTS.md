# OpenCasa — AI Agent Context

## Project Overview

OpenCasa is a lightweight server management panel for OpenBSD/macppc (PowerPC G3/G4/G5), inspired by CasaOS. Pure Python stdlib backend + Svelte 4 frontend. Zero external dependencies for the backend.

**Target hardware**: 300 MHz–2 GHz PowerPC, 256 MB–1 GB RAM.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3 stdlib (`http.server`), no pip packages |
| Frontend | Svelte 4 + Vite 5 |
| Database | SQLite (encrypted key-value via HMAC-CTR) |
| Auth | Custom HMAC-SHA256 JWT (no libraries) |
| Build | `npm run build` for frontend, no backend build |

## Project Structure

```
backend/
├── webui.py                    # Entry point, imports and calls main()
└── webui/                      # Python package
    ├── __init__.py             # HTTP handler, routing, config, main()
    ├── auth.py                 # JWT + user management (PBKDF2 passwords)
    ├── system.py               # CPU/mem/disk via vmstat/sysctl/proc
    ├── filemanager.py          # File CRUD, upload, download
    ├── appmanager.py           # App lifecycle, widget cache, permissions
    ├── database.py             # Encrypted SQLite KV store
    ├── notifications.py        # JSON notification persistence
    └── proxy.py                # Reverse proxy for web apps (/app/<id>/)
frontend/
├── src/
│   ├── App.svelte              # Root component, nav
│   ├── main.js                 # Svelte mount
│   ├── lib/
│   │   ├── api.js              # API client (fetch wrappers)
│   │   ├── Login.svelte        # Login form
│   │   ├── Dashboard.svelte    # Main dashboard
│   │   ├── FileManager.svelte  # File browser
│   │   └── AppManager.svelte   # App store/management
│   └── widgets/
│       ├── CpuWidget.svelte
│       ├── MemoryWidget.svelte
│       ├── DiskWidget.svelte
│   │   └── AppGrid.svelte
├── dist/                       # Built frontend (committed)
├── locales/                    # en.json, it.json
├── package.json
└── vite.config.js
scripts/
├── webui                       # OpenBSD rc.d script (ksh)
└── webui.service               # systemd unit
examples/apps/                  # Example app manifests + scripts
```

## Known Issues to Fix

### CRITICAL — Security

1. ~~**Hardcoded default JWT secret**~~ `[FIXED]`
2. **Root user bypasses ALL filesystem checks** (`backend/webui/filemanager.py:20-22`)
   - `_check_path()` returns `True` for `_is_root`, allowing reads/writes to `/etc/shadow`, `/root`, etc.
   - **Fix**: Enforce `allowed_prefixes` even for root, or add a separate `root_allowed_prefixes` config. At minimum, block access to sensitive system paths (`/etc/shadow`, `/etc/passwd`, `/root`).
   - **Status**: Design decision — root access is intentional. Skip or document as by-design.

3. **Plaintext root password comparison** (`backend/webui/auth.py:133`)
   - `root_pass == password` compares against plaintext config value.
   - **Fix**: Always hash root password on startup or config load. Store only hashes.
   - **Status**: Design decision — plaintext for backwards compat. Skip or document as by-design.

4. ~~**Proxy has no body size limit**~~ `[FIXED]`
5. ~~**No rate limiting on login**~~ `[FIXED]`
6. ~~**Bare `except: pass` in `_app_preexec`**~~ `[FIXED]`

### HIGH — Bugs

7. **Frontend API client endpoints mismatch backend** (`frontend/src/lib/api.js:51-54`)
   - `registerApp()` → POST `/apps/register` (does not exist in backend)
   - `startApp(id)` → POST `/apps/start` with `{id}` body (backend expects POST `/apps/<id>/start`)
   - `stopApp(id)` → POST `/apps/stop` with `{id}` body (backend expects POST `/apps/<id>/stop`)
   - `appStatus(id)` → GET `/apps/status?id=...` (does not exist; backend has GET `/apps/<id>`)
   - **Fix**: Rewrite these functions to match backend routes:
     ```js
     startApp: (id) => request('POST', `/apps/${id}/start`),
     stopApp: (id) => request('POST', `/apps/${id}/stop`),
     runApp: (id) => request('POST', `/apps/${id}/run`),
     uninstallApp: (id) => request('POST', `/apps/${id}/uninstall`),
     ```
   - Remove `registerApp` and `appStatus` or implement the backend endpoints.

8. ~~**Memory stats overwritten after UVM/vmstat calculation**~~ `[FIXED]`

9. **API.md is incomplete** (`API.md`)
   - Missing endpoints: `POST /api/v1/setup`, `GET/POST /api/v1/users`, `POST /api/v1/users/password`, `POST /api/v1/users/avatar`, `POST /api/v1/users/<id>/delete`, `POST /api/v1/apps/<id>/confirm`, `POST /api/v1/apps/<id>/run`.
   - **Fix**: Document all routes from `__init__.py` router.

### MEDIUM — Code Quality

10. ~~**README contradicts build system**~~ `[FIXED]`

11. ~~**`save_notifications()` called inside lock**~~ `[FIXED]`

12. ~~**`os.geteuid() != 0` check prevents non-root development**~~ `[FIXED]`

13. ~~**Proxy missing `Access-Control-Allow-Origin` header**~~ `[FIXED]`

14. **`_send_json` doesn't handle large payloads** (`backend/webui/__init__.py:107-114`)
    - `json.dumps(data).encode()` loads entire response into memory.
    - **Fix**: For large responses (file downloads, app lists), consider streaming.

15. ~~**No input validation on `app_id`**~~ `[FIXED]`

16. **Config saved with `os.replace` is not atomic on all filesystems** (`backend/webui/__init__.py:78-84`)
    - On crash during save, config could be corrupted.
    - **Fix**: Write to `.tmp`, fsync, then rename. Or accept the risk and document it.

### LOW — Improvements

17. **No test suite** — No unit or integration tests exist.
18. **No `package-lock.json`** — Frontend dependency versions are not locked.
19. **Widget cache TTL is 30s** (`appmanager.py:308`) but dashboard polls every 5s — wasted calls.
20. **`notifications.py:32`** — Notification ID uses `strftime("%H%M%S.%f")` which can collide on rapid pushes.

### NEW — Frontend / Backend Integration Bugs

21. **`AppManager.svelte:32-42` — `unregister()` calls inesistent endpoint**
    - `DELETE /api/v1/apps/register` does not exist in the backend.
    - **Fix**: Replace with `api.uninstallApp(id)` which calls `POST /api/v1/apps/<id>/uninstall`.

22. **`api.js` missing functions required by AppManager**
    - Missing: `runApp(id)`, `uninstallApp(id)`, `getAppLogs(id)`, `confirmApp(id)`, `changePassword(newPass)`, `getUserList()`.
    - **Fix**: Add these wrappers to `api.js` matching backend routes.

23. **`AppManager.svelte:71` — `app.command` displayed but backend sends `app.entry`**
    - The manifest field is `entry`, not `command`. Template shows wrong field.
    - **Fix**: Change `{app.command}` to `{app.entry}` in the template.

### NEW — Backend Robustness

24. **`system.py:11-17` — `_run()` has no stdout size limit**
    - A command producing large output (e.g. accidental `cat` on huge file) fills memory.
    - **Fix**: Add `r.stdout[:1024*1024]` truncation or use `subprocess.run(..., stdout=subprocess.PIPE)` with explicit max.

25. **`database.py:37` — `check_same_thread=False` without init guard**
    - `init()` could be called from a different thread than `get/set()` callers.
    - **Fix**: Add a `_init_thread` variable set in `init()`, assert same thread or use a proper lock for init.

26. **`__init__.py:319-338` — GET `/apps/<id>` missing `app_id` validation**
    - `app_id` from URL is passed directly to `get_app()` without `_safe_id()` check.
    - **Fix**: Add `if not _safe_id(app_id): return self._send_error(400, "invalid app id")` before calling `get_app`.

27. **`proxy.py:25` — Porta default `8081` hardcoded**
    - If manifest has no `port`, proxy silently uses 8081 instead of returning error.
    - **Fix**: Return `{'error': 'no port configured in manifest'}` when `app.get("port")` is 0 or falsy.

28. **`filemanager.py:90` — `handle_upload` boundary parse can raise IndexError**
    - `content_type.split("boundary=", 1)[1].strip()` fails if `boundary=` is missing.
    - **Fix**: Wrap in try/except or check with `if "boundary=" not in content_type:`.

29. **`__init__.py:562-574` — Change password without current password verification**
    - Any logged-in user can change password without proving they know the current one.
    - **Fix**: Require `"current_password"` field and verify it before allowing change.

30. **`system.py:300-301` — `/bin/cat` hardcoded for reading `/proc/net/dev`**
    - `/bin/cat` may not exist on all Linux distros.
    - **Fix**: Replace with `open("/proc/net/dev")` read directly in Python.

31. **`appmanager.py:171-174` — `scan_all()` called on every `list_apps()`**
    - Every GET `/apps` scans the filesystem, even for repeated requests within seconds.
    - **Fix**: Add a TTL cache (e.g. 5s) to `scan_all()` — skip rescan if `_cache_ts` is recent.

32. **`proxy.py:50-53` — HTTPError handler sends empty body**
    - `e.read()` returns bytes but `handler.wfile.write(e.read())` doesn't set Content-Type.
    - **Fix**: Add `Content-Type: text/plain` header and decode bytes to string.

## API Routes Reference

### Auth
| Method | Path | Auth | Body |
|--------|------|------|------|
| POST | `/api/v1/auth/login` | No | `{username, password}` |
| GET | `/api/v1/auth/check` | Yes | — |
| GET | `/api/v1/setup` | No | — |
| POST | `/api/v1/setup` | No | `{username, password}` |

### Users
| Method | Path | Auth | Root |
|--------|------|------|------|
| GET | `/api/v1/users` | Yes | Yes |
| POST | `/api/v1/users` | Yes | Yes |
| POST | `/api/v1/users/check` | No | — |
| POST | `/api/v1/users/password` | Yes | — |
| POST | `/api/v1/users/avatar` | Yes | — |
| POST | `/api/v1/users/<username>/delete` | Yes | Yes |

### System
| Method | Path | Auth |
|--------|------|------|
| GET | `/api/v1/system/stats` | Yes |
| GET | `/api/v1/system/info` | Yes |
| GET | `/api/v1/storage` | Yes |
| POST | `/api/v1/disks/mount` | Yes |
| POST | `/api/v1/disks/umount` | Yes |
| GET | `/api/v1/disks` | Yes |

### Files
| Method | Path | Auth |
|--------|------|------|
| GET | `/api/v1/files?path=` | Yes |
| GET | `/api/v1/files/read?path=` | Yes |
| GET | `/api/v1/files/download?path=` | Yes |
| POST | `/api/v1/files/write` | Yes |
| POST | `/api/v1/files/rename` | Yes |
| POST | `/api/v1/files/delete` | Yes |
| POST | `/api/v1/files/mkdir` | Yes |
| POST | `/api/v1/files/upload` | Yes |

### Apps
| Method | Path | Auth |
|--------|------|------|
| GET | `/api/v1/apps` | Yes |
| GET | `/api/v1/apps/<id>` | Yes |
| GET | `/api/v1/apps/<id>/widget` | Yes |
| GET | `/api/v1/apps/<id>/icon` | **No** |
| GET | `/api/v1/apps/<id>/logs` | Yes |
| POST | `/api/v1/apps/<id>/run` | Yes |
| POST | `/api/v1/apps/<id>/start` | Yes |
| POST | `/api/v1/apps/<id>/stop` | Yes |
| POST | `/api/v1/apps/<id>/confirm` | Yes |
| POST | `/api/v1/apps/<id>/uninstall` | Yes |
| `*` | `/app/<id>/<path>` | Yes (proxy) |

### Database (user-scoped)
| Method | Path | Auth |
|--------|------|------|
| GET | `/api/v1/db/get?key=` | Yes |
| POST | `/api/v1/db/set` | Yes |
| POST | `/api/v1/db/delete` | Yes |
| GET | `/api/v1/db/list?prefix=` | Yes |

### Notifications
| Method | Path | Auth |
|--------|------|------|
| GET | `/api/v1/notifications` | Yes |
| POST | `/api/v1/notify` | Yes |

## Config File

Located at `/etc/opencasa.json`. See `opencasa.json.example` for defaults.

Key fields:
- `auth.jwt_secret` — **must** be changed from default before production use
- `auth.root_password` — stored in plaintext in config (backwards compat)
- `filesystem.allowed_prefixes` — restricts file manager access
- `apps_dir` — where app folders live (default: `/usr/local/webui/apps`)
- `app_user` — Unix user for running app subprocesses (default: `opencasa`)
- `master_key` — auto-generated, used for DB encryption

## Development

```bash
# Backend
python3 backend/webui.py -c opencasa.json.example -d . --debug

# Frontend
cd frontend && npm install && npm run dev
```

## Running Tests

No test framework is configured. If adding tests, use `pytest` (would need to add to dependencies).

## Conventions

- Backend: pure stdlib Python, no external packages. Thread-safe via `threading.Lock`.
- Frontend: Svelte 4, no UI framework, dark theme (#0f172a base).
- All API responses are JSON with `Content-Type: application/json`.
- CORS: `Access-Control-Allow-Origin: *` on all responses.
- File paths validated against `allowed_prefixes` (root bypasses this — known issue).
- Apps run as unprivileged user (`app_user`) with resource limits (CPU 30s, RAM 256MB, 10 processes).
