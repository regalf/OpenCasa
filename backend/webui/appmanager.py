"""App manager: filesystem-based apps with manifests, permissions, execution, logs, and autostart."""

import json
import logging
import os
import shutil
import signal
import subprocess
import threading
import time
from datetime import datetime, timezone

from . import config

logger = logging.getLogger(__name__)

APPS_DIR = None
APP_USER = None
_APP_USER_UID = None
_APP_USER_GID = None
_APP_USER_HOME = None

_cache = []
_cache_lock = threading.Lock()
_running = {}
_logs = {}
_widget_cache = {}
_widget_lock = threading.Lock()
_MAX_LOG = 50
_WIDGET_INTERVAL = 10


def init():
    global APPS_DIR, APP_USER
    import sys
    pkg = sys.modules.get('.'.join(__name__.split('.')[:-1]))
    data_dir = getattr(pkg, 'DATA_DIR', '/usr/local/webui') if pkg else '/usr/local/webui'
    APPS_DIR = config.get('apps_dir') or os.path.join(data_dir, 'apps')
    os.makedirs(APPS_DIR, exist_ok=True)
    APP_USER = config.get('app_user', 'opencasa')
    _ensure_app_user()
    scan_all()
    _autostart_web_apps()


def _ensure_app_user():
    global _APP_USER_UID, _APP_USER_GID, _APP_USER_HOME
    import pwd
    new_user = False
    try:
        pw = pwd.getpwnam(APP_USER)
        _APP_USER_UID = pw.pw_uid
        _APP_USER_GID = pw.pw_gid
        _APP_USER_HOME = pw.pw_dir
        logger.debug("app user '%s' (uid=%d, home=%s)", APP_USER, _APP_USER_UID, _APP_USER_HOME)
    except KeyError:
        logger.info("creating app user '%s'", APP_USER)
        for cmd in (['useradd', '-m', APP_USER], ['adduser', '-m', APP_USER], ['adduser', APP_USER]):
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                if r.returncode == 0:
                    break
                logger.debug("useradd attempt %s failed: %s", cmd, r.stderr.strip())
            except (FileNotFoundError, subprocess.TimeoutExpired) as e:
                logger.debug("useradd attempt %s: %s", cmd, e)
        else:
            logger.warning("failed to create user '%s' — tried useradd, adduser", APP_USER)
            return
        pw = pwd.getpwnam(APP_USER)
        _APP_USER_UID = pw.pw_uid
        _APP_USER_GID = pw.pw_gid
        _APP_USER_HOME = pw.pw_dir
        logger.info("app user '%s' created (uid=%d, home=%s)", APP_USER, _APP_USER_UID, _APP_USER_HOME)
        new_user = True

    # Set password only on first creation (not every boot)
    if new_user:
        app_pass = config.get('app_password', '')
        if app_pass:
            _set_app_password(app_pass)
        if app_pass == "123456":
            logger.warning("DEFAULT PASSWORD for app user '%s' is '123456' — CHANGE IT in opencasa.json (app_password)", APP_USER)


def _set_app_password(password):
    """Set password for APP_USER using passwd via pty (works on Linux, OpenBSD, macOS)."""
    user = APP_USER

    # Try chpasswd (Linux) as a quick path
    try:
        p = subprocess.Popen(['chpasswd'], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        p.communicate(input=f'{user}:{password}'.encode(), timeout=10)
        if p.returncode == 0:
            logger.info("password set for '%s' via chpasswd", user)
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Use passwd via pty (works everywhere including OpenBSD)
    try:
        _set_password_via_pty(user, password)
        logger.info("password set for '%s' via passwd (pty)", user)
        return True
    except Exception as e:
        logger.debug("passwd pty failed: %s", e)

    logger.warning("could not set password for '%s'", user)
    return False


def _set_password_via_pty(user, password):
    """Drive 'passwd user' via a pseudo-terminal to set password non-interactively."""
    import pty, os, select, time, signal

    pid, fd = pty.fork()
    if pid == 0:
        signal.signal(signal.SIGALRM, signal.SIG_DFL)
        os.execvp('passwd', ['passwd', user])
        os._exit(1)

    sent = 0
    buf = b''
    deadline = time.time() + 15
    ok = False

    try:
        while time.time() < deadline:
            r, _, _ = select.select([fd], [], [], 0.3)
            if r:
                try:
                    data = os.read(fd, 4096)
                except OSError:
                    break
                if not data:
                    break
                buf += data
                low = buf.lower()
                if sent == 0 and b'password' in low:
                    os.write(fd, (password + '\n').encode())
                    sent = 1
                    buf = b''
                elif sent == 1 and (b'password' in low or b'again' in low or b're-enter' in low or b'confirm' in low or b'retype' in low):
                    os.write(fd, (password + '\n').encode())
                    sent = 2
                    buf = b''
            # Check if child exited (non-blocking)
            try:
                pid2, status = os.waitpid(pid, os.WNOHANG)
                if pid2:
                    if os.WIFEXITED(status):
                        ok = os.WEXITSTATUS(status) == 0
                    break
            except OSError:
                break

        # If child still running after password sent, give it 2s to process
        if not ok:
            for _ in range(20):
                try:
                    pid2, status = os.waitpid(pid, os.WNOHANG)
                    if pid2:
                        if os.WIFEXITED(status):
                            ok = os.WEXITSTATUS(status) == 0
                        break
                except OSError:
                    break
                time.sleep(0.1)
            else:
                # Child still alive — kill it
                try:
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(0.3)
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass
                os.waitpid(pid, os.WNOHANG)

        return ok
    except:
        try:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
        except:
            pass
        raise


def _set_resource_limits():
    import resource
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    except (ValueError, resource.error):
        pass
    try:
        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
    except (ValueError, resource.error):
        pass
    nproc = getattr(resource, 'RLIMIT_NPROC', None)
    if nproc is not None:
        try:
            resource.setrlimit(nproc, (10, 10))
        except (ValueError, resource.error):
            pass


def _app_preexec():
    if _APP_USER_GID is not None:
        os.setgid(_APP_USER_GID)
    if _APP_USER_UID is not None:
        os.setuid(_APP_USER_UID)
    os.setpgrp()
    _set_resource_limits()


def _safe_id(name):
    return all(c.isalnum() or c in '-_' for c in name)


def scan_all():
    global _cache
    apps = []
    try:
        for entry in sorted(os.listdir(APPS_DIR)):
            d = os.path.join(APPS_DIR, entry)
            if not os.path.isdir(d) or not _safe_id(entry):
                continue
            mf = os.path.join(d, 'manifest.json')
            if not os.path.isfile(mf):
                continue
            try:
                with open(mf) as f:
                    m = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("manifest %s: %s", entry, e)
                continue
            has_icon = any(os.path.isfile(os.path.join(d, f'icon.{ext}')) for ext in ('svg', 'png', 'jpg', 'jpeg', 'gif'))
            apps.append({
                'id': entry,
                'name': m.get('name', entry),
                'description': m.get('description', ''),
                'version': m.get('version', '0.1.0'),
                'author': m.get('author', ''),
                'entry': m.get('entry', 'app.py'),
                'type': m.get('type', 'tool'),
                'autostart': m.get('autostart', False),
                'port': m.get('port', 0),
                'permissions': m.get('permissions', []),
                'has_widget': m.get('has_widget', False),
                'path': d,
                'icon': has_icon,
                'status': 'stopped',
                'pid': 0,
            })
    except OSError as e:
        logger.error("scan apps: %s", e)

    with _cache_lock:
        _cache = apps
        for pid in list(_running.keys()):
            info = _running[pid]
            for a in _cache:
                if a['id'] == info['app_id'] and _alive(pid):
                    a['status'] = 'running'
                    a['pid'] = pid
    return apps


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def get_app(app_id):
    with _cache_lock:
        for a in _cache:
            if a['id'] == app_id:
                return dict(a)
    return None


def list_apps():
    scan_all()
    with _cache_lock:
        return [dict(a) for a in _cache]


def icon_path(app_id):
    app = get_app(app_id)
    if not app:
        return None
    for ext in ('svg', 'png', 'jpg', 'jpeg', 'gif'):
        p = os.path.join(app['path'], f'icon.{ext}')
        if os.path.isfile(p):
            return p
    return None


# ── Permission confirmation ──

def is_app_confirmed(app_id, permissions):
    from . import database as dbmod
    key = "_app_confirm:" + app_id
    data = dbmod.get(key)
    if data:
        try:
            confirmed = json.loads(data)
            if confirmed.get("permissions") == permissions:
                return True
        except (json.JSONDecodeError, TypeError):
            pass
    return False


def confirm_app(app_id, permissions):
    from . import database as dbmod
    key = "_app_confirm:" + app_id
    dbmod.set(key, json.dumps({"permissions": permissions, "confirmed_at": time.time()}))
    return True


# ── Execution ──

def run_app(app_id):
    app = get_app(app_id)
    if not app:
        return {'error': 'app not found'}

    ep = os.path.join(app['path'], app['entry'])
    if not os.path.isfile(ep):
        return {'error': f'{app["entry"]} not found'}

    # Permission confirmation check
    if not is_app_confirmed(app_id, app['permissions']):
        return {'error': 'permission_required', 'permissions': app['permissions']}

    port = config.get('server', {}).get('port', 80)
    ctx = json.dumps({
        'app_id': app['id'],
        'name': app['name'],
        'permissions': app['permissions'],
        'api_url': f'http://localhost:{port}',
    })

    env = os.environ.copy()
    env['OPENCASA_CONTEXT'] = ctx
    env['OPENCASA_ACTION'] = 'widget'
    if _APP_USER_HOME:
        env['HOME'] = _APP_USER_HOME

    try:
        proc = subprocess.Popen(
            ['python3', ep],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env, cwd=app['path'],
            preexec_fn=_app_preexec,
        )
        try:
            stdout, stderr = proc.communicate(timeout=30)
            result = {'stdout': stdout, 'stderr': stderr, 'returncode': proc.returncode}
        except subprocess.TimeoutExpired:
            _kill_process_group(proc.pid)
            stdout, stderr = proc.communicate()
            result = {'stdout': stdout, 'stderr': 'timeout (30s)', 'returncode': -1}
    except Exception as e:
        result = {'stdout': '', 'stderr': str(e), 'returncode': -1}

    _add_log(app_id, result)

    if result['returncode'] == 0:
        try:
            with _widget_lock:
                _widget_cache[app_id] = {'ts': time.time(), 'data': json.loads(result['stdout'])}
        except (json.JSONDecodeError, ValueError):
            pass

    return result


def _kill_process_group(pid):
    try:
        pgid = os.getpgid(pid)
        os.killpg(pgid, signal.SIGTERM)
        time.sleep(0.5)
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except Exception:
        pass


def _add_log(app_id, result):
    entry = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'stdout': result.get('stdout', ''),
        'stderr': result.get('stderr', ''),
        'returncode': result.get('returncode', -1),
    }
    with _cache_lock:
        if app_id not in _logs:
            _logs[app_id] = []
        _logs[app_id].append(entry)
        if len(_logs[app_id]) > _MAX_LOG:
            _logs[app_id] = _logs[app_id][-_MAX_LOG:]


def get_logs(app_id, limit=20):
    with _cache_lock:
        return (_logs.get(app_id) or [])[-limit:]


def get_widget_data(app_id):
    now = time.time()
    with _widget_lock:
        entry = _widget_cache.get(app_id)
        if entry and now - entry['ts'] < 30:
            return entry['data']
    result = run_app(app_id)
    if result and 'error' not in result and result.get('returncode', -1) == 0:
        with _widget_lock:
            entry = _widget_cache.get(app_id)
            if entry:
                return entry['data']
    return None


def start_web_app(app_id):
    app = get_app(app_id)
    if not app:
        return {'error': 'app not found'}
    if app['type'] != 'web':
        return {'error': 'not a web app'}
    ep = os.path.join(app['path'], app['entry'])
    if not os.path.isfile(ep):
        return {'error': f'{app["entry"]} not found'}
    if not app['port']:
        return {'error': 'no port configured in manifest'}

    # Permission confirmation check
    if not is_app_confirmed(app_id, app['permissions']):
        return {'error': 'permission_required', 'permissions': app['permissions']}

    port = config.get('server', {}).get('port', 80)
    ctx = json.dumps({
        'app_id': app['id'],
        'name': app['name'],
        'permissions': app['permissions'],
        'api_url': f'http://localhost:{port}',
        'port': app['port'],
    })

    env = os.environ.copy()
    env['OPENCASA_CONTEXT'] = ctx
    if _APP_USER_HOME:
        env['HOME'] = _APP_USER_HOME

    try:
        proc = subprocess.Popen(
            ['python3', ep],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env=env, cwd=app['path'],
            preexec_fn=_app_preexec,
        )
        pid = proc.pid
        with _cache_lock:
            _running[pid] = {'app_id': app_id, 'proc': proc, 'start_time': time.time(), 'type': 'web'}
            for a in _cache:
                if a['id'] == app_id:
                    a['status'] = 'running'
                    a['pid'] = pid
        return {'success': True, 'pid': pid}
    except Exception as e:
        return {'error': str(e)}


def stop_web_app(app_id):
    with _cache_lock:
        app = next((a for a in _cache if a['id'] == app_id), None)
        if not app:
            return {'error': 'app not found'}
        pid = app['pid']
        if pid and pid in _running:
            info = _running.pop(pid, None)
            if info:
                proc = info['proc']
                try:
                    _kill_process_group(pid)
                    proc.wait(timeout=2)
                except Exception:
                    pass
        app['status'] = 'stopped'
        app['pid'] = 0
    return {'success': True}


def uninstall_app(app_id):
    app = get_app(app_id)
    if not app:
        return {'error': 'app not found'}
    if app['status'] == 'running':
        stop_web_app(app_id)
    try:
        shutil.rmtree(app['path'])
        with _cache_lock:
            _cache[:] = [a for a in _cache if a['id'] != app_id]
            _logs.pop(app_id, None)
            _widget_cache.pop(app_id, None)
        return {'success': True}
    except OSError as e:
        return {'error': str(e)}


def _autostart_web_apps():
    for app in list_apps():
        if app['autostart'] and app['type'] == 'web' and app['status'] == 'stopped':
            threading.Thread(target=lambda aid=app['id']: start_web_app(aid), daemon=True).start()
