# Changelog

## v1.2.0 (2026-06-27)

### Features

- **Update system**: new `backend/webui/updater.py` module with two channels:
  - **Stable**: downloads latest release tarball from GitHub Releases (`check_update()` → `do_update()`)
  - **Nightly**: clones repo branch via `git clone --depth 1` with HTTP tarball fallback; silent checks (no notification badge)
- **Config migration**: on update, `_merge_config_file()` preserves `master_key`, `root_password`, `jwt_secret`, and `update` settings while adding new keys from updated `DEFAULT_CONFIG`
- **Update API**: `GET /api/v1/system/check-update` and `POST /api/v1/system/do-update` (root only, auto-restarts daemon via `os.execv`)
- **Frontend update panel**: sidebar "Updates" button (above notifications) opens a modal with channel/branch selection, check button, changelog display, and update button
- **Version in health/info endpoints**: `GET /api/v1/health` now returns `version`, `GET /api/v1/system/info` includes `version` and `update_config`
- **install-release.sh**: new script for stable release install (`doas sh scripts/install-release.sh`), auto-downloads latest GitHub release or accepts local tarball path
- **install.sh**: newly generated configs now set `update_channel: "nightly"` (repo/tarball installs)
- **make_release.py**: script to create versioned release tarball (`python3 scripts/make_release.py v1.2.0`)
- **extract_changelog.py**: script to extract changelog section for a given version (used by `gh release create`)
- **RELEASE.md**: documentation of the release process

### Documentation

- New `RELEASE.md` with step-by-step release instructions
- Locales: added 18 new keys for the update UI (en.json + it.json)

### Testing

- All 134 existing tests pass unmodified

## v1.1.0 (2026-06-26)

### Security

- **App-scoped notifications**: proxy now intercepts `/app/<id>/api/v1/notif*` and enforces `app_id` from the URL path, preventing apps from reading/modifying notifications of other apps
- Notification API functions (`push`, `list`, `delete`, `clear`) all support optional `app_id` filtering

### Features

- **Per-app resource limits**: new section in the app detail modal to configure CPU max (seconds) and RAM max (MB) for each app individually. Zero means unlimited. Limits are stored per-user in the database. Applied on next start/run
- **mc-server example app**: bareiron Minecraft server manager with 4 tabs (Status, Releases, Config, Output), GitHub release browser, config editor, real-time output polling
- **Release filtering**: `latest` tag skipped in GitHub release fetcher, only proper semver tags shown

### Bug Fixes

- Notification panel position: changed from `top: 0` to `bottom: 0` so the panel grows upward from the bell button instead of overflowing downward
- Config editor input visibility in mc-server: styled inputs with proper dark theme colors
- `_safe_id()` now rejects empty strings
- `set_app_permission()` saves to global key when `username=None` instead of returning `False`
- `files:read` permission marked as purely declarative (no pledge/unveil changes)

### Documentation

- Outdated example apps removed: `disk-usage`, `hello-world`, `system-monitor`
- README, install script, wiki updated to reflect removed apps
- `API.md`, `DEPLOY.md` moved to wiki, removed from repo
- `app_password` removed from `DEFAULT_CONFIG` (unused — password managed by OS)

### Testing

- 134 tests total (was 131): 3 new tests for app-scoped notification filtering

## v1.0.0 (2026-06-24)

Initial release of OpenCasa — a lightweight server management panel for old hardware (PowerPC G3/G4/G5, single-core ARM, legacy x86) with zero external Python dependencies.

### Features

- **Dashboard**: real-time CPU, memory, disk, and network stats via `vmstat`/`/proc` with configurable polling
- **File Manager**: browse, upload, download, create, rename, delete files with inline editor, path restriction, pinned folders, and root bypass
- **App System**: install and run tool/widget/web apps from the UI or via ZIP upload; autostart and port management
- **App Permissions**: OS-level sandboxing via `pledge(2)` + `unveil(2)` (OpenBSD) and `unshare(CLONE_NEWNET)` (Linux); per-user grant/revoke
- **Web App Proxy**: reverse-proxy web apps under `/app/<id>/` with body size limits
- **Notifications**: per-user push notification system with severity levels, slide-out panel, and full CRUD API
- **Authentication**: JWT-based login with configurable session TTL, two-phase login flow, cookie/header/query token
- **Multi-user**: root user from config file + regular users in encrypted database; avatar upload
- **Rate Limiting**: 10 failed login attempts per IP in 5 minutes
- **Encrypted Database**: per-value HMAC-CTR encryption with HMAC-SHA256 integrity verification; auto-recovery on key loss
- **Disk Manager**: list, mount, and unmount filesystems
- **i18n**: English and Italian locale files (190+ keys each)
- **Mobile-friendly**: responsive layout with hamburger menu
- **First-boot Setup Wizard**: guided initial user creation
- **Root Tamper Detection**: detects out-of-band password changes with two-step recovery flow
- **Installer Script**: `scripts/install.sh` — supports OpenBSD and Linux

### Security

- PBKDF2-SHA256 password hashing (100,000 iterations)
- JWT with HMAC-SHA256 signing
- Per-value encryption in SQLite database (HMAC-CTR mode)
- OS-level permission enforcement on OpenBSD (`pledge` + `unveil`)
- Network namespace isolation on Linux (`unshare`)
- Configuration file protected from file manager access
- Rate limiting on login endpoints

### Example Applications

- `calendar` — full calendar web app with dashboard widget
- `hello-web` — minimal test web app
- `whoami` — tool app verifying sandbox user
- `perm-test` — web app testing all 6 permission types
- `notify-test` — web app demonstrating notification API

### Supported Platforms

- OpenBSD/macppc (PowerPC G3/G4/G5, tested on iMac G3 600 MHz)
- Linux (x86_64, aarch64, tested on Fedora 44)
- Any POSIX system with Python 3.8+
