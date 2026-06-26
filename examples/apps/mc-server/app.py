#!/usr/bin/env python3
"""bareiron server manager — start/stop, server.conf editor, output viewer, version manager."""
import http.server, json, os, subprocess, socket, mimetypes, threading, time, urllib.request, urllib.parse, urllib.error, signal, re, resource

HOST = '127.0.0.1'
PORT = int(os.environ.get('OPENCASA_APP_PORT', '18995'))
DIR = os.path.dirname(os.path.abspath(__file__))
HOME = os.environ.get('HOME', '/home/opencasa')
SERVER_DIR = os.path.join(HOME, 'mc-server')

def _find_binary():
    for name in ('bareiron', 'bareiron.exe', 'bareiron-macppc'):
        p = os.path.join(SERVER_DIR, name)
        if os.path.isfile(p):
            return p
    return os.path.join(SERVER_DIR, 'bareiron')
CONF_PATH = os.path.join(SERVER_DIR, 'server.conf')
WORLD_FILE = os.path.join(SERVER_DIR, 'world.bin')
_GH_REPO = 'regalf/bareiron'

_server_proc = None
_server_lock = threading.Lock()
_output_buf = []
_output_lock = threading.Lock()
_MAX_OUTPUT = 500

def _ensure_dir():
    os.makedirs(SERVER_DIR, exist_ok=True)

def _reader_thread(proc):
    """Read stdout from the server process into a ring buffer."""
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        with _output_lock:
            _output_buf.append(line.rstrip('\n\r'))
            if len(_output_buf) > _MAX_OUTPUT:
                _output_buf[:] = _output_buf[-_MAX_OUTPUT:]

def _is_running():
    if _server_proc and _server_proc.poll() is None:
        return True
    return False

def _get_installed_version():
    bp = _find_binary()
    if not os.path.isfile(bp):
        return None
    ver = 'unknown'
    try:
        size = os.path.getsize(bp)
        ver = f'{os.path.basename(bp)} ({size} bytes)'
    except Exception:
        pass
    return ver

def _read_conf():
    props = {}
    if not os.path.isfile(CONF_PATH):
        return props
    try:
        with open(CONF_PATH) as f:
            for line in f:
                raw = line.rstrip('\n')
                stripped = line.strip()
                if not stripped or stripped.startswith('#'):
                    continue
                if '=' not in stripped:
                    continue
                k, _, v = stripped.partition('=')
                props[k.strip()] = {'value': v.strip(), 'raw': raw}
    except Exception:
        pass
    return props


def _read_conf_flat():
    props = {}
    if not os.path.isfile(CONF_PATH):
        return props
    try:
        with open(CONF_PATH) as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith('#') or '=' not in stripped:
                    continue
                k, _, v = stripped.partition('=')
                props[k.strip()] = v.strip()
    except Exception:
        pass
    return props

def _write_conf(new_props):
    lines = []
    if os.path.isfile(CONF_PATH):
        with open(CONF_PATH) as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith('#') or '=' not in stripped:
                    lines.append(line)
                else:
                    k = stripped.split('=', 1)[0].strip()
                    if k in new_props:
                        lines.append(f'{k}={new_props[k]}\n')
                        del new_props[k]
                    else:
                        lines.append(line)
    for k, v in new_props.items():
        lines.append(f'{k}={v}\n')
    with open(CONF_PATH, 'w') as f:
        f.writelines(lines)

def _get_port():
    props = _read_conf_flat()
    return props.get('port', '25565')

def _get_status():
    running = _is_running()
    conf = _read_conf_flat()
    return {
        'running': running,
        'installed': os.path.isfile(_find_binary()),
        'port': conf.get('port', '25565') if not running else _get_port(),
        'motd': conf.get('motd', 'A bareiron server'),
        'gamemode': conf.get('gamemode', '0') if not running else conf.get('gamemode', '0'),
        'world_exists': os.path.isfile(WORLD_FILE),
        'server_dir': SERVER_DIR,
        'config_exists': os.path.isfile(CONF_PATH),
    }

def _start():
    global _server_proc
    with _server_lock:
        if _is_running():
            return {'error': 'server already running'}
        bp = _find_binary()
        if not os.path.isfile(bp):
            _ensure_dir()
            return {'error': 'no bareiron binary — download a release or place bareiron in ' + SERVER_DIR}
        if not os.access(bp, os.X_OK):
            try:
                os.chmod(bp, 0o755)
            except OSError as e:
                return {'error': f'binary not executable: {e}'}
        _output_buf.clear()
        try:
            _server_proc = subprocess.Popen(
                [bp],
                cwd=SERVER_DIR,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                preexec_fn=os.setpgrp,
            )
            t = threading.Thread(target=_reader_thread, args=(_server_proc,), daemon=True)
            t.start()
            time.sleep(0.5)
            if _server_proc.poll() is not None:
                out = '\n'.join(_output_buf[-20:])
                return {'error': f'server exited immediately (rc={_server_proc.returncode})', 'output': out}
            return {'success': True, 'pid': _server_proc.pid}
        except Exception as e:
            return {'error': str(e)[:200]}

def _stop():
    global _server_proc
    with _server_lock:
        if not _is_running():
            return {'error': 'server not running'}
        try:
            if _server_proc:
                pgid = os.getpgid(_server_proc.pid) if hasattr(os, 'getpgid') else None
                _server_proc.terminate()
                try:
                    _server_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    _server_proc.kill()
                    _server_proc.wait(timeout=3)
                _server_proc = None
                if pgid:
                    try:
                        os.killpg(pgid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
            return {'success': True}
        except Exception as e:
            return {'error': str(e)[:200]}

def _get_output(n=100):
    with _output_lock:
        return _output_buf[-n:]

def _fetch_releases():
    url = f'https://api.github.com/repos/{_GH_REPO}/releases?per_page=20'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'OpenCasa-MCServer/1.0', 'Accept': 'application/vnd.github+json'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        return {'error': str(e)[:200], 'releases': []}
    releases = []
    for r in data:
        tag = r.get('tag_name', '')
        if tag == 'latest':
            continue
        rel = {
            'tag': tag,
            'name': r.get('name', ''),
            'published': r.get('published_at', ''),
            'prerelease': r.get('prerelease', False),
            'assets': [],
        }
        for a in r.get('assets', []):
            rel['assets'].append({
                'name': a.get('name', ''),
                'size': a.get('size', 0),
                'url': a.get('browser_download_url', ''),
            })
        releases.append(rel)
    releases.sort(key=lambda x: x['tag'], reverse=True)
    return {'releases': releases, 'latest': releases[0]['tag'] if releases else None}

def _download_release(asset_url, asset_name):
    _ensure_dir()
    path = os.path.join(SERVER_DIR, asset_name)
    try:
        req = urllib.request.Request(asset_url, headers={'User-Agent': 'OpenCasa-MCServer/1.0'})
        with urllib.request.urlopen(req, timeout=300) as resp:
            with open(path + '.tmp', 'wb') as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
        os.rename(path + '.tmp', path)
        os.chmod(path, 0o755)
        return {'success': True, 'path': path, 'size': os.path.getsize(path)}
    except Exception as e:
        if os.path.isfile(path + '.tmp'):
            try:
                os.unlink(path + '.tmp')
            except OSError:
                pass
        return {'error': str(e)[:300]}

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split('?')[0].rstrip('/') or '/index.html'
        if path == '/api/status':
            self._json(_get_status())
        elif path == '/api/config':
            try:
                conf = _read_conf()
                raw_lines = []
                if os.path.isfile(CONF_PATH):
                    with open(CONF_PATH) as f:
                        raw_lines = f.read().splitlines()
                self._json({
                    'exists': os.path.isfile(CONF_PATH),
                    'properties': {k: v['value'] for k, v in conf.items()},
                    'raw': raw_lines,
                })
            except Exception as e:
                self._json({'error': f'failed to read config: {e}', 'exists': False, 'properties': {}}, 500)
        elif path == '/api/output':
            n_str = self._param('lines', '100')
            try:
                n = max(1, min(500, int(n_str)))
            except ValueError:
                n = 100
            self._json({'lines': _get_output(n)})
        elif path == '/api/releases':
            self._json(_fetch_releases())
        elif path == '/api/installed':
            self._json({
                'installed': os.path.isfile(_find_binary()),
                'version': _get_installed_version(),
                'world_exists': os.path.isfile(WORLD_FILE),
            })
        else:
            self._serve_static(path)

    def do_POST(self):
        path = self.path.split('?')[0].rstrip('/')
        if path == '/api/start':
            self._json(_start())
        elif path == '/api/stop':
            self._json(_stop())
        elif path == '/api/restart':
            s = _stop()
            if 'error' in s and 'not running' not in s.get('error', ''):
                self._json(s)
            else:
                time.sleep(0.5)
                self._json(_start())
        elif path == '/api/config':
            content_len = int(self.headers.get('Content-Length', 0))
            if content_len:
                body = json.loads(self.rfile.read(content_len))
                _write_conf(body)
                self._json({'success': True})
            else:
                self._json({'error': 'no config data'})
        elif path == '/api/download':
            content_len = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_len)) if content_len else {}
            asset_url = body.get('url', '')
            asset_name = body.get('name', 'bareiron.exe')
            if not asset_url:
                self._json({'error': 'no url provided'})
            else:
                self._json(_download_release(asset_url, asset_name))
        else:
            self._json({'error': 'not found'}, 404)

    def _param(self, name, default=''):
        qs = self.path.split('?', 1)
        if len(qs) > 1:
            for part in qs[1].split('&'):
                if '=' in part:
                    k, v = part.split('=', 1)
                    if k == name:
                        return urllib.parse.unquote(v)
        return default

    def _serve_static(self, path):
        safe = os.path.normpath(path.lstrip('/'))
        fpath = os.path.join(DIR, safe)
        if not fpath.startswith(DIR) or not os.path.isfile(fpath):
            self.send_response(404)
            self.end_headers()
            return
        ct, _ = mimetypes.guess_type(fpath)
        self.send_response(200)
        self.send_header('Content-Type', ct or 'application/octet-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        with open(fpath, 'rb') as f:
            self.wfile.write(f.read())

    def _json(self, data, code=200):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *a): pass

if __name__ == '__main__':
    _ensure_dir()
    http.server.HTTPServer((HOST, PORT), Handler).serve_forever()
