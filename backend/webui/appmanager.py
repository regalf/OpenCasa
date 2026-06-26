"""App manager: filesystem-based apps with manifests, permissions, execution, logs, and autostart."""

import json
import logging
import os
import re
import shutil
import signal
import socket
import subprocess
import threading
import time
import zipfile
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
_cache_ts = 0.0
_running = {}
_assigned_ports = {}  # app_id -> port (in-memory auto-assignments)
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
    _detect_app_user()
    scan_all()
    _autostart_web_apps()


def _detect_app_user():
    """Detect app user and set globals. Do NOT auto-create."""
    global _APP_USER_UID, _APP_USER_GID, _APP_USER_HOME
    import pwd
    try:
        pw = pwd.getpwnam(APP_USER)
        _APP_USER_UID = pw.pw_uid
        _APP_USER_GID = pw.pw_gid
        _APP_USER_HOME = pw.pw_dir
        logger.info("app user '%s' found (uid=%d)", APP_USER, _APP_USER_UID)
    except KeyError:
        _APP_USER_UID = None
        _APP_USER_GID = None
        _APP_USER_HOME = None
        logger.warning("app user '%s' NOT found — apps will be disabled. "
                       "Create manually: doas useradd -m %s", APP_USER, APP_USER)


def app_user_ready():
    if _APP_USER_UID is None:
        _detect_app_user()
    return _APP_USER_UID is not None


def _compute_pledge_promises(permissions):
    """Compute pledge(2) promises string from permission list."""
    has_client = 'network:client' in permissions
    has_server = 'network:server' in permissions
    has_exec = 'system:exec' in permissions
    has_fwrite = 'files:write' in permissions

    promises = ['stdio', 'rpath']

    if has_client:
        promises.extend(['inet', 'dns'])
    elif has_server:
        promises.append('inet')

    if has_exec:
        promises.extend(['proc', 'exec'])

    if has_fwrite:
        promises.append('wpath')
        promises.append('cpath')

    seen = set()
    return ' '.join(p for p in promises if not (p in seen or seen.add(p)))


def _needs_network(permissions):
    return 'network:client' in permissions or 'network:server' in permissions


def _enforce_permissions(permissions, app_dir=None):
    """Apply OS-level permission enforcement (pledge+unveil on OpenBSD, unshare on Linux)."""
    if hasattr(os, 'pledge'):
        try:
            promises = _compute_pledge_promises(permissions)
            if hasattr(os, 'unveil'):
                promises += ' unveil'
            os.pledge(promises)
        except OSError:
            pass

    if hasattr(os, 'unveil'):
        try:
            import sysconfig
            for path in sysconfig.get_paths().values():
                if os.path.isdir(path):
                    os.unveil(path, 'r')
            if app_dir and os.path.isdir(app_dir):
                os.unveil(app_dir, 'r')
            if 'files:read' in permissions and _APP_USER_HOME:
                os.unveil(_APP_USER_HOME, 'r')
            if 'files:write' in permissions and _APP_USER_HOME:
                os.unveil(_APP_USER_HOME, 'rwc')
            os.unveil(None, None)
            if hasattr(os, 'pledge'):
                try:
                    os.pledge(_compute_pledge_promises(permissions))
                except OSError:
                    pass
        except Exception:
            pass

    if not _needs_network(permissions):
        try:
            import ctypes
            libc = ctypes.CDLL('libc.so.6', use_errno=True)
            CLONE_NEWNET = 0x40000000
            libc.unshare(CLONE_NEWNET)
        except Exception:
            pass


def _set_resource_limits(max_memory_mb=None, max_cpu_seconds=None):
    import resource
    mem = max_memory_mb if max_memory_mb is not None else 256
    cpu = max_cpu_seconds if max_cpu_seconds is not None else 30
    if cpu > 0:
        try:
            resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
        except (ValueError, resource.error):
            pass
    else:
        try:
            resource.setrlimit(resource.RLIMIT_CPU, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
        except (ValueError, resource.error):
            pass
    if mem > 0:
        try:
            resource.setrlimit(resource.RLIMIT_AS, (mem * 1024 * 1024, mem * 1024 * 1024))
        except (ValueError, resource.error):
            pass
    else:
        try:
            resource.setrlimit(resource.RLIMIT_AS, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
        except (ValueError, resource.error):
            pass
    nproc = getattr(resource, 'RLIMIT_NPROC', None)
    if nproc is not None:
        try:
            resource.setrlimit(nproc, (10, 10))
        except (ValueError, resource.error):
            pass


def _limits_key(app_id, username=None):
    base = "_app_limits"
    if username:
        return f"{base}:{username}:{app_id}"
    return f"{base}:{app_id}"


def _get_resource_limits(app_id, username=None):
    from . import database as dbmod
    key = _limits_key(app_id, username)
    data = dbmod.get(key)
    if data:
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            pass
    return {}


def set_resource_limits(app_id, limits, username=None):
    from . import database as dbmod
    key = _limits_key(app_id, username)
    dbmod.set(key, json.dumps({
        'max_memory_mb': limits.get('max_memory_mb', 256),
        'max_cpu_seconds': limits.get('max_cpu_seconds', 30),
    }))
    return {'success': True}


def _make_preexec(permissions, app_dir=None, limits=None):
    """Create a preexec_fn closure that drops privileges and enforces permissions."""
    mem = (limits or {}).get('max_memory_mb')
    cpu = (limits or {}).get('max_cpu_seconds')
    def preexec():
        try:
            if _APP_USER_UID is not None and _APP_USER_GID is not None:
                if hasattr(os, 'initgroups'):
                    try: os.initgroups(APP_USER, _APP_USER_GID)
                    except Exception: pass
                try: os.setgid(_APP_USER_GID)
                except Exception: pass
                try: os.setuid(_APP_USER_UID)
                except Exception: pass
            try: os.setpgrp()
            except Exception: pass
            _set_resource_limits(mem, cpu)
            _enforce_permissions(permissions, app_dir)
        except Exception:
            pass
    return preexec


def _safe_id(name):
    return bool(name) and all(c.isalnum() or c in '-_' for c in name)


def scan_all():
    global _cache, _cache_ts
    now = time.time()
    if now - _cache_ts < 3.0 and _cache:
        return _cache
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
            manifest_icon = m.get('icon')
            if manifest_icon:
                icon_path_full = os.path.join(d, manifest_icon)
                icon_val = manifest_icon if os.path.isfile(icon_path_full) else None
            else:
                for ext in ('svg', 'png', 'jpg', 'jpeg', 'gif'):
                    if os.path.isfile(os.path.join(d, f'icon.{ext}')):
                        icon_val = f'icon.{ext}'
                        break
                else:
                    icon_val = None
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
                'open_in': m.get('open_in', 'iframe'),
                'path': d,
                'icon': icon_val,
                'status': 'stopped',
                'pid': 0,
            })
    except OSError as e:
        logger.error("scan apps: %s", e)

    with _cache_lock:
        _cache = apps
        _cache_ts = now
        for pid in list(_running.keys()):
            info = _running[pid]
            for a in _cache:
                if a['id'] == info['app_id'] and _alive(pid):
                    a['status'] = 'running'
                    a['pid'] = pid
                    if 'port' in info:
                        a['port'] = info['port']
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
        apps = [dict(a) for a in _cache]
        used = [p for p in _pool() if any(a.get('port') == p and a['status'] == 'running' for a in apps)]
        return {
            "apps": apps,
            "app_user_ready": app_user_ready(),
            "port_pool": _pool(),
            "used_ports": used,
        }


def icon_path(app_id):
    app = get_app(app_id)
    if not app or not app.get('icon'):
        return None
    p = os.path.join(app['path'], app['icon'])
    return p if os.path.isfile(p) else None


# ── Permission confirmation ──

def _perm_key(app_id, username=None):
    base = "_app_perm_state"
    if username:
        return f"{base}:{username}:{app_id}"
    return f"{base}:{app_id}"


def _get_perm_state(app_id, username=None):
    from . import database as dbmod
    key = _perm_key(app_id, username)
    data = dbmod.get(key)
    if data:
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            pass
    return {}


def _set_perm_state(app_id, username, state):
    from . import database as dbmod
    key = _perm_key(app_id, username)
    dbmod.set(key, json.dumps(state))


def get_permission_state(app_id, username=None):
    state = _get_perm_state(app_id, username)
    app = get_app(app_id)
    if not app:
        return {}
    result = {}
    for p in app['permissions']:
        result[p] = state.get(p, True)
    return result


def _get_granted_permissions(app_id, username=None):
    state = _get_perm_state(app_id, username)
    if state:
        return [p for p, g in state.items() if g]
    app = get_app(app_id)
    if app:
        return app['permissions']
    return []


def is_app_confirmed(app_id, permissions, username=None):
    if not permissions:
        return True
    state = _get_perm_state(app_id, username)
    if not state:
        from . import database as dbmod
        key = "_app_confirm:" + app_id
        data = dbmod.get(key)
        if data:
            try:
                confirmed = json.loads(data)
                if confirmed.get("permissions") == permissions:
                    new_state = {p: True for p in permissions}
                    if username:
                        _set_perm_state(app_id, username, new_state)
                    dbmod.set(key, "")
                    return True
            except (json.JSONDecodeError, TypeError):
                pass
        return False
    for p in permissions:
        if p not in state:
            return False
    return True


def confirm_app(app_id, permissions, username=None):
    state = {p: True for p in permissions}
    if username:
        _set_perm_state(app_id, username, state)
    _set_perm_state(app_id, None, state)
    return True


def set_app_permission(app_id, permission, granted, username=None):
    state = _get_perm_state(app_id, username)
    state[permission] = granted
    if username:
        _set_perm_state(app_id, username, state)
    _set_perm_state(app_id, None, state)
    return True


# ── Execution ──

def run_app(app_id, username=None):
    app = get_app(app_id)
    if not app:
        return {'error': 'app not found'}

    ep = os.path.join(app['path'], app['entry'])
    if not os.path.isfile(ep):
        return {'error': f'{app["entry"]} not found'}

    if not app_user_ready():
        return {'error': 'app_user_missing', 'app_user': APP_USER}

    # Permission confirmation check — skip if no permissions required
    if app['permissions'] and not is_app_confirmed(app_id, app['permissions'], username):
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
    env['OPENCASA_APP_DIR'] = app['path']
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    if _APP_USER_HOME:
        env['HOME'] = _APP_USER_HOME

    app_cwd = _APP_USER_HOME or app['path']

    granted = _get_granted_permissions(app_id, username)

    try:
        proc = subprocess.Popen(
            ['python3', ep],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env, cwd=app_cwd,
            preexec_fn=_make_preexec(granted, app['path'], _get_resource_limits(app_id, username)),
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


def _count_running():
    """Return number of alive web app processes."""
    alive = 0
    with _cache_lock:
        for pid in list(_running.keys()):
            if not _alive(pid):
                _running.pop(pid, None)
            else:
                alive += 1
    return alive


def _pool():
    """Return the configured port pool list."""
    return config.get('apps', {}).get('port_pool', [])


def _pool_used_ports(exclude_app_id=None):
    """Return set of ports from pool currently used by running apps."""
    pool = set(_pool())
    used = set()
    with _cache_lock:
        for pid, info in _running.items():
            if _alive(pid) and info.get('app_id') != exclude_app_id:
                p = info.get('port')
                if p and p in pool:
                    used.add(p)
    return used


def _port_available(port):
    """Check if a TCP port is available on 127.0.0.1."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.settimeout(1)
        s.bind(('127.0.0.1', port))
        s.close()
        return True
    except (OSError, OverflowError):
        return False


def _port_in_use_by_app(port, exclude=None):
    """Return the app_id of a running app using this port, or None."""
    with _cache_lock:
        for pid, info in list(_running.items()):
            if info.get('port') == port and _alive(pid):
                if exclude is None or info.get('app_id') != exclude:
                    return info.get('app_id')
    return None


def _resolve_port(app_id, manifest_port):
    """Resolve effective port: config override → previously assigned → pool → manifest."""
    overrides = config.get('apps', {}).get('ports', {})
    if app_id in overrides:
        return int(overrides[app_id])
    if app_id in _assigned_ports:
        p = _assigned_ports[app_id]
        if not _port_in_use_by_app(p, exclude=app_id) and _port_available(p):
            return p
    pool = _pool()
    used = _pool_used_ports()
    for p in pool:
        if p not in used and _port_available(p):
            _assigned_ports[app_id] = p
            return p
    if manifest_port:
        return int(manifest_port)
    return None


def start_web_app(app_id, username=None):
    app = get_app(app_id)
    if not app:
        return {'error': 'app not found'}
    if app['type'] != 'web':
        return {'error': 'not a web app'}
    ep = os.path.join(app['path'], app['entry'])
    if not os.path.isfile(ep):
        return {'error': f'{app["entry"]} not found'}
    effective_port = _resolve_port(app_id, app.get('port'))
    if not effective_port:
        return {'error': 'port pool exhausted — no free ports available'}

    conflict = _port_in_use_by_app(effective_port, exclude=app_id)
    if conflict:
        return {'error': f'port {effective_port} already in use by app "{conflict}"'}

    if not _port_available(effective_port):
        return {'error': f'port {effective_port} in use by another process'}

    if not app_user_ready():
        return {'error': 'app_user_missing', 'app_user': APP_USER}

    max_proc = config.get('apps', {}).get('max_processes', 10)
    if _count_running() >= max_proc:
        return {'error': f'max processes ({max_proc}) reached'}

    # Permission confirmation check — skip if no permissions required
    if app['permissions'] and not is_app_confirmed(app_id, app['permissions'], username):
        return {'error': 'permission_required', 'permissions': app['permissions']}

    srv_port = config.get('server', {}).get('port', 80)
    ctx = json.dumps({
        'app_id': app['id'],
        'name': app['name'],
        'permissions': app['permissions'],
        'api_url': f'http://localhost:{srv_port}',
        'port': effective_port,
    })

    env = os.environ.copy()
    env['OPENCASA_CONTEXT'] = ctx
    env['OPENCASA_APP_PORT'] = str(effective_port)
    env['OPENCASA_APP_DIR'] = app['path']
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    if _APP_USER_HOME:
        env['HOME'] = _APP_USER_HOME

    app_cwd = _APP_USER_HOME or app['path']

    granted = _get_granted_permissions(app_id, username)

    try:
        proc = subprocess.Popen(
            ['python3', ep],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env=env, cwd=app_cwd,
            preexec_fn=_make_preexec(granted, app['path'], _get_resource_limits(app_id, username)),
        )
        pid = proc.pid
        with _cache_lock:
            _running[pid] = {
                'app_id': app_id,
                'proc': proc,
                'start_time': time.time(),
                'type': 'web',
                'port': effective_port,
            }
            for a in _cache:
                if a['id'] == app_id:
                    a['status'] = 'running'
                    a['pid'] = pid
                    a['port'] = effective_port
        return {'success': True, 'pid': pid, 'port': effective_port}
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


def set_app_port(app_id, port):
    """Persist a port override for an app. Restart if running."""
    pool = _pool()
    if pool and port not in pool:
        return {'error': f'port {port} not in pool: {pool}'}
    config.setdefault('apps', {}).setdefault('ports', {})[app_id] = port
    from . import save_config
    save_config()
    app = get_app(app_id)
    if app and app['status'] == 'running':
        stop_web_app(app_id)
        r = start_web_app(app_id)
        return r
    return {'success': True, 'port': port}


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


def install_app_from_zip(file_data):
    """Extract a ZIP from raw bytes and install as an app."""
    import tempfile
    if not file_data:
        return {'error': 'no zip file data received'}
    app_dir_name = None
    try:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = os.path.join(tmp, "app.zip")
            with open(zip_path, "wb") as f:
                f.write(file_data)
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                if not names:
                    return {'error': 'empty zip'}
                root = names[0].split("/")[0]
                if not _safe_id(root):
                    return {'error': f'invalid app directory name: {root}'}
                app_dir_name = root
                target = os.path.join(APPS_DIR, root)
                if os.path.exists(target):
                    return {'error': f'app "{root}" already exists'}
                zf.extractall(APPS_DIR)
            mf = os.path.join(target, "manifest.json")
            if not os.path.isfile(mf):
                shutil.rmtree(target, ignore_errors=True)
                return {'error': 'manifest.json not found in zip'}
            try:
                with open(mf) as f:
                    m = json.load(f)
                if not m.get("name"):
                    shutil.rmtree(target, ignore_errors=True)
                    return {'error': 'manifest missing "name" field'}
            except (json.JSONDecodeError, OSError) as e:
                shutil.rmtree(target, ignore_errors=True)
                return {'error': f'invalid manifest.json: {e}'}
            scan_all()
            return {'success': True, 'app_id': root, 'name': m.get("name", root)}
    except (zipfile.BadZipFile, OSError) as e:
        if app_dir_name:
            shutil.rmtree(os.path.join(APPS_DIR, app_dir_name), ignore_errors=True)
        return {'error': str(e)}


def _autostart_web_apps():
    max_proc = config.get('apps', {}).get('max_processes', 10)
    started = 0
    for app in list_apps()["apps"]:
        if started >= max_proc:
            break
        if app['autostart'] and app['type'] == 'web' and app['status'] == 'stopped':
            threading.Thread(target=lambda aid=app['id']: start_web_app(aid), daemon=True).start()
            started += 1
