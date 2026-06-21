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
_cache = []
_cache_lock = threading.Lock()
_running = {}
_logs = {}
_widget_cache = {}
_widget_lock = threading.Lock()
_MAX_LOG = 50
_WIDGET_INTERVAL = 10


def init():
    global APPS_DIR
    import sys
    pkg = sys.modules.get('.'.join(__name__.split('.')[:-1]))
    data_dir = getattr(pkg, 'DATA_DIR', '/usr/local/webui') if pkg else '/usr/local/webui'
    APPS_DIR = config.get('apps_dir') or os.path.join(data_dir, 'apps')
    os.makedirs(APPS_DIR, exist_ok=True)
    scan_all()
    _autostart_web_apps()


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
            # Check if an icon file exists
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


def run_app(app_id):
    app = get_app(app_id)
    if not app:
        return {'error': 'app not found'}

    ep = os.path.join(app['path'], app['entry'])
    if not os.path.isfile(ep):
        return {'error': f'{app["entry"]} not found'}

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

    try:
        p = subprocess.run(
            ['python3', ep],
            capture_output=True, text=True, timeout=30,
            env=env, cwd=app['path'],
        )
        result = {'stdout': p.stdout, 'stderr': p.stderr, 'returncode': p.returncode}
    except subprocess.TimeoutExpired:
        result = {'stdout': '', 'stderr': 'timeout (30s)', 'returncode': -1}
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
    # Cache miss or stale — run app to generate widget data
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

    try:
        proc = subprocess.Popen(
            ['python3', ep],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env=env, cwd=app['path'],
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
                    proc.terminate()
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
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
