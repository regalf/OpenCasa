# Changelog

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
- `system-monitor` — tool app for system monitoring

### Supported Platforms

- OpenBSD/macppc (PowerPC G3/G4/G5, tested on iMac G3 600 MHz)
- Linux (x86_64, aarch64, tested on Fedora 44)
- Any POSIX system with Python 3.8+
