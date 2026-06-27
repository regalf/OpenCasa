"""Update system for OpenCasa.

Supports two channels:
  - stable: download tarball from GitHub Releases
  - nightly: git clone/pull from a specified branch

Config merge: new keys from updated DEFAULT_CONFIG are added while preserving
existing values (master_key, root_password, etc.).
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import urllib.error

GH_REPO = "regalf/OpenCasa"
GH_API = f"https://api.github.com/repos/{GH_REPO}"
GH_RAW = f"https://raw.githubusercontent.com/{GH_REPO}"
TMP_PREFIX = "opencasa-update-"


def _get_local_version():
    from . import __version__
    return __version__


def _get_config():
    from . import config
    return config


def _save_config():
    from . import save_config
    save_config()


def check_update(channel="stable", branch="main"):
    """Check if an update is available.

    Returns dict with keys:
      available (bool), latest_version (str or None),
      current_version (str), changelog (str or None),
      channel (str), silent (bool)
    """
    current = _get_local_version()
    result = {
        "available": False,
        "latest_version": None,
        "current_version": current,
        "changelog": None,
        "channel": channel,
        "silent": False,
    }

    if channel == "nightly":
        result["silent"] = True
        try:
            # Compare local HEAD hash with remote
            local_hash = _git("rev-parse", "HEAD")
            remote_hash = _git_ls_remote(branch)
            if remote_hash and local_hash:
                result["available"] = local_hash.strip() != remote_hash.strip()
                result["latest_version"] = f"nightly-{remote_hash[:7]}"
                result["changelog"] = _fetch_nightly_changelog(branch, local_hash.strip())
            elif remote_hash:
                result["available"] = True
                result["latest_version"] = "nightly"
            return result
        except Exception as e:
            logging.warning("nightly update check failed: %s", e)
            return result

    # stable channel
    try:
        req = urllib.request.Request(
            f"{GH_API}/releases/latest",
            headers={"User-Agent": "OpenCasa/Update/1.0", "Accept": "application/vnd.github.v3+json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())

        latest = data.get("tag_name", "")
        if latest and _compare_versions(latest, current) > 0:
            result["available"] = True
            result["latest_version"] = latest
            result["changelog"] = _fetch_changelog(latest)
    except Exception as e:
        logging.warning("stable update check failed: %s", e)

    return result


def do_update(channel="stable", branch="main"):
    """Download and apply update.

    Returns dict with keys: success (bool), message (str),
    needs_restart (bool).
    """
    if os.geteuid() != 0:
        return {"success": False, "message": "root required", "needs_restart": False}

    from . import DATA_DIR, CONFIG_PATH

    tmpdir = None
    try:
        logging.info("starting %s update (branch=%s)", channel, branch)
        tmpdir = tempfile.mkdtemp(prefix=TMP_PREFIX)

        if channel == "nightly":
            _update_nightly(tmpdir, branch)
            new_source = tmpdir
        else:
            version = _download_stable(tmpdir)
            new_source = tmpdir

        # Backup config
        config_backup = None
        if CONFIG_PATH and os.path.isfile(CONFIG_PATH):
            with open(CONFIG_PATH) as f:
                config_backup = f.read()

        # Remove any residual .git from previous buggy updates before backup+merge
        _git_dst = os.path.join(DATA_DIR, ".git")
        if os.path.isdir(_git_dst):
            shutil.rmtree(_git_dst, ignore_errors=True)

        # Backup current installation
        backup_dir = DATA_DIR.rstrip("/") + ".bak"
        if os.path.isdir(backup_dir):
            shutil.rmtree(backup_dir)
        if os.path.isdir(DATA_DIR):
            shutil.copytree(DATA_DIR, backup_dir, symlinks=True)

        # Copy only essential files — flat layout matching the installer
        # backend/webui.py → DATA_DIR/webui.py
        _src = os.path.join(new_source, "backend", "webui.py")
        if os.path.isfile(_src):
            shutil.copy2(_src, os.path.join(DATA_DIR, "webui.py"))

        # backend/webui/*.py → DATA_DIR/webui/
        _src = os.path.join(new_source, "backend", "webui")
        _dst = os.path.join(DATA_DIR, "webui")
        if os.path.isdir(_src):
            os.makedirs(_dst, exist_ok=True)
            for _f in os.listdir(_src):
                if _f.endswith(".py"):
                    shutil.copy2(os.path.join(_src, _f), os.path.join(_dst, _f))

        # frontend/dist/* (files) → DATA_DIR/ (flat)
        _src = os.path.join(new_source, "frontend", "dist")
        if os.path.isdir(_src):
            for _f in os.listdir(_src):
                _fp = os.path.join(_src, _f)
                if os.path.isfile(_fp):
                    shutil.copy2(_fp, os.path.join(DATA_DIR, _f))
                elif _f == "locales":
                    shutil.copytree(_fp, os.path.join(DATA_DIR, "locales"),
                                    symlinks=True, dirs_exist_ok=True)

        # scripts/* → DATA_DIR/scripts/
        _src = os.path.join(new_source, "scripts")
        _dst = os.path.join(DATA_DIR, "scripts")
        if os.path.isdir(_src):
            shutil.copytree(_src, _dst, symlinks=True, dirs_exist_ok=True)

        logging.info("file merge complete")

        # Purge stale bytecache so Python picks up new .py files
        _purge_pycache(DATA_DIR)

        # Merge config: add new keys while preserving existing values
        if config_backup:
            _merge_config_file(CONFIG_PATH)

        # Set update channel in config
        cfg = _get_config()
        cfg.setdefault("update", {})["channel"] = channel
        if channel == "nightly":
            cfg["update"]["branch"] = branch
        _save_config()

        return {
            "success": True,
            "message": f"Updated to {'nightly' if channel == 'nightly' else version}",
            "needs_restart": True,
        }

    except Exception as e:
        logging.exception("update failed")
        return {"success": False, "message": str(e), "needs_restart": False}
    finally:
        if tmpdir and os.path.isdir(tmpdir):
            shutil.rmtree(tmpdir, ignore_errors=True)


def _merge_config_file(config_path):
    """Merge existing config with new defaults, preserving critical keys."""
    from . import DEFAULT_CONFIG, deep_merge

    if not config_path or not os.path.isfile(config_path):
        return

    try:
        with open(config_path) as f:
            old = json.load(f)
    except (json.JSONDecodeError, OSError):
        return

    # Save critical values
    preserved = {
        "master_key": old.get("master_key", ""),
        "auth": {
            "root_password": old.get("auth", {}).get("root_password", ""),
            "jwt_secret": old.get("auth", {}).get("jwt_secret", ""),
        },
        "update": old.get("update", {}),
    }

    # Start fresh from new defaults
    new_config = json.loads(json.dumps(DEFAULT_CONFIG))
    # Apply old values on top (preserves user customizations)
    deep_merge(new_config, old)
    # Restore critical values (in case deep_merge lost them)
    if preserved["master_key"]:
        new_config["master_key"] = preserved["master_key"]
    if preserved["auth"]["root_password"]:
        new_config["auth"]["root_password"] = preserved["auth"]["root_password"]
    if preserved["auth"]["jwt_secret"]:
        new_config["auth"]["jwt_secret"] = preserved["auth"]["jwt_secret"]
    if preserved["update"]:
        new_config["update"] = preserved["update"]

    # Write atomically
    tmp = config_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(new_config, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, config_path)


def _purge_pycache(root):
    """Recursively remove all __pycache__ directories under root."""
    for dirpath, dirnames, _ in os.walk(root, topdown=False):
        for d in dirnames:
            if d == "__pycache__":
                path = os.path.join(dirpath, d)
                try:
                    shutil.rmtree(path)
                except OSError:
                    pass


def _merge_dirs(src, dst, preserve=None):
    """Recursively copy src to dst, skipping preserved dirs at top level."""
    preserve = preserve or []
    for entry in os.listdir(src):
        if entry in preserve:
            continue
        s = os.path.join(src, entry)
        d = os.path.join(dst, entry)
        if os.path.isdir(s):
            if os.path.isdir(d):
                shutil.copytree(s, d, symlinks=True, dirs_exist_ok=True)
            else:
                shutil.copytree(s, d, symlinks=True)
        else:
            shutil.copy2(s, d)


def _download_stable(tmpdir):
    """Download latest stable release tarball from GitHub."""
    req = urllib.request.Request(
        f"{GH_API}/releases/latest",
        headers={"User-Agent": "OpenCasa/Update/1.0", "Accept": "application/vnd.github.v3+json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())

    version = data["tag_name"]
    tarball_url = None
    for asset in data.get("assets", []):
        name = asset.get("name", "")
        if name.endswith(".tar.gz") and version in name:
            tarball_url = asset["browser_download_url"]
            break

    if not tarball_url:
        # Fallback to GitHub-generated tarball
        tarball_url = f"{GH_API}/tarball/{version}"

    tarball_path = os.path.join(tmpdir, "release.tar.gz")
    _download_file(tarball_url, tarball_path)

    with tarfile.open(tarball_path, "r:gz") as tar:
        top = None
        for member in tar.getmembers():
            if top is None:
                parts = member.name.split("/", 1)
                top = parts[0]
                if len(parts) > 1:
                    member.name = parts[1]
                else:
                    member.name = ""
            else:
                prefix = top + "/"
                if member.name.startswith(prefix):
                    member.name = member.name[len(prefix):]
            tar.extract(member, tmpdir)

    return version


def _update_nightly(tmpdir, branch):
    """Clone repo at given branch into tmpdir."""
    url = f"https://github.com/{GH_REPO}.git"
    try:
        subprocess.check_call(
            ["git", "clone", "--depth", "1", "--branch", branch, url, tmpdir],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=120,
        )
        logging.info("nightly update: git clone succeeded")
    except (subprocess.CalledProcessError, FileNotFoundError):
        logging.info("nightly update: git unavailable, using http fallback")
        # Fallback: download tarball of branch
        tarball_url = f"{GH_API}/tarball/{branch}"
        tarball_path = os.path.join(os.path.dirname(tmpdir), "branch.tar.gz")
        _download_file(tarball_url, tarball_path)
        with tarfile.open(tarball_path, "r:gz") as tar:
            top = None
            for member in tar.getmembers():
                if top is None:
                    parts = member.name.split("/", 1)
                    top = parts[0]
                    if len(parts) > 1:
                        member.name = parts[1]
                    else:
                        member.name = ""
                else:
                    prefix = top + "/"
                    if member.name.startswith(prefix):
                        member.name = member.name[len(prefix):]
                tar.extract(member, tmpdir)
        os.unlink(tarball_path)


def _download_file(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "OpenCasa/Update/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)


def _fetch_changelog(version):
    """Fetch CHANGELOG.md section for given version from raw GitHub."""
    try:
        url = f"{GH_RAW}/main/CHANGELOG.md"
        req = urllib.request.Request(url, headers={"User-Agent": "OpenCasa/Update/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode()

        marker = f"## {version}"
        start = content.find(marker)
        if start == -1:
            return None
        end = content.find("\n## ", start + len(marker))
        return content[start:end].strip() if end != -1 else content[start:].strip()
    except Exception:
        return None


def _fetch_nightly_changelog(branch, local_hash):
    """Get commits since local HEAD."""
    try:
        url = f"{GH_API}/compare/{local_hash}...HEAD"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "OpenCasa/Update/1.0", "Accept": "application/vnd.github.v3+json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        commits = data.get("commits", [])
        if not commits:
            return None

        lines = [f"## Commits since last update ({len(commits)} total)"]
        for c in commits:
            msg = c.get("commit", {}).get("message", "").split("\n")[0]
            sha = c.get("sha", "")[:7]
            lines.append(f"- {sha} {msg}")
        return "\n".join(lines)
    except Exception:
        return None


def _git(*args):
    """Run git command, return stdout."""
    try:
        return subprocess.check_output(["git"] + list(args), stderr=subprocess.DEVNULL, timeout=30).decode()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _git_ls_remote(branch):
    """Get HEAD hash of remote branch."""
    try:
        out = subprocess.check_output(
            ["git", "ls-remote", f"https://github.com/{GH_REPO}.git", f"refs/heads/{branch}"],
            stderr=subprocess.DEVNULL,
            timeout=30,
        ).decode()
        if out:
            return out.split()[0]
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return None


def _compare_versions(v1, v2):
    """Compare two semver tags (v1.2.3). Returns >0 if v1 > v2."""
    def parse(v):
        v = v.lstrip("v")
        parts = v.split(".")
        return tuple(int(p) if p.isdigit() else 0 for p in parts[:3])
    p1, p2 = parse(v1), parse(v2)
    if p1 > p2:
        return 1
    if p1 < p2:
        return -1
    return 0


CHECK_INTERVAL = 21600  # 6 hours

def start_auto_update_daemon():
    """Background thread: checks for updates and applies them if auto_update is enabled."""
    import threading

    def _loop():
        while True:
            try:
                cfg = _get_config().get("update", {})
                if cfg.get("auto_update", False):
                    channel = cfg.get("channel", "stable")
                    branch = cfg.get("branch", "main")
                    result = check_update(channel=channel, branch=branch)
                    if result.get("available"):
                        logging.info("auto-update: update available, starting 5min countdown")
                        _send_auto_notif("info", "Auto-Update",
                                         "An update is available. The system will update automatically in 5 minutes.")
                        time.sleep(240)  # 4 min
                        _send_auto_notif("info", "Auto-Update",
                                         "The update will be applied in 1 minute. The panel will restart shortly after.")
                        time.sleep(60)   # 1 min
                        logging.info("auto-update: applying update now")
                        do_update(channel=channel, branch=branch)
            except Exception:
                logging.exception("auto-update daemon error")
            time.sleep(CHECK_INTERVAL)

    t = threading.Thread(target=_loop, daemon=True)
    t.start()


def _send_auto_notif(severity, title, message):
    """Send a notification to all users."""
    try:
        from .notifications import push_notification
        from .auth import list_users
        from . import config
        root_user = config.get("auth", {}).get("root_user", "root")
        usernames = {root_user}
        for u in list_users():
            usernames.add(u["username"])
        for uname in usernames:
            try:
                push_notification("system", title, message, severity, uname)
            except Exception:
                pass
    except Exception as e:
        logging.warning("auto-update notification failed: %s", e)
