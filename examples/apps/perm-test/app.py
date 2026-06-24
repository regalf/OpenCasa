#!/usr/bin/env python3
"""Permission Test app — verifies each permission works at the OS level."""
import http.server, json, os, subprocess, socket, sysconfig, tempfile, platform, mimetypes
from datetime import datetime

HOST = '127.0.0.1'
PORT = int(os.environ.get('OPENCASA_APP_PORT', '18996'))
DIR = os.path.dirname(os.path.abspath(__file__))
HOME = os.environ.get('HOME', '/home/opencasa')
TEST_FILE = os.path.join(HOME, '.opencasa_perm_test')

def _test_network_client():
    targets = [('1.1.1.1', 443), ('8.8.8.8', 443)]
    for host, port in targets:
        try:
            s = socket.create_connection((host, port), timeout=10)
            s.close()
            return {'ok': True, 'detail': f'TCP connect to {host}:{port} OK'}
        except Exception:
            continue
    return {'ok': False, 'detail': 'Could not connect to 1.1.1.1:443 or 8.8.8.8:443'}

def _test_network_server():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((HOST, 0))
        port = s.getsockname()[1]
        s.close()
        return {'ok': True, 'detail': f'bound to port {port} OK'}
    except Exception as e:
        return {'ok': False, 'detail': str(e)[:120]}

def _test_files_read():
    try:
        path = os.path.join(HOME, '.profile') if os.path.exists(os.path.join(HOME, '.profile')) else __file__
        with open(path, 'r') as f:
            f.read(64)
        return {'ok': True, 'detail': f'read {os.path.basename(path)} OK'}
    except Exception as e:
        return {'ok': False, 'detail': str(e)[:120]}

def _test_files_write():
    try:
        with open(TEST_FILE, 'w') as f:
            f.write('ok')
        os.unlink(TEST_FILE)
        return {'ok': True, 'detail': 'wrote and deleted test file OK'}
    except Exception as e:
        try:
            if os.path.exists(TEST_FILE):
                os.unlink(TEST_FILE)
        except: pass
        return {'ok': False, 'detail': str(e)[:120]}

def _test_system_exec():
    try:
        r = subprocess.run(['id', '-un'], capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            return {'ok': True, 'detail': f'user: {r.stdout.strip()}'}
        return {'ok': False, 'detail': f'exit {r.returncode}: {r.stderr.strip()[:80]}'}
    except Exception as e:
        return {'ok': False, 'detail': str(e)[:120]}

def _test_system_monitor():
    try:
        info = {'host': platform.node(), 'python': platform.python_version()}
        has_proc = os.path.isdir('/proc')
        is_bsd = os.path.exists('/bsd')
        info['platform'] = f'{platform.system()} {platform.machine()}'
        info['has_proc'] = has_proc
        info['is_bsd'] = is_bsd
        return {'ok': True, 'detail': json.dumps(info)}
    except Exception as e:
        return {'ok': False, 'detail': str(e)[:120]}

def _test_files_read_blocked():
    try:
        blocked = ['/etc/master.passwd', '/etc/shadow', '/etc/opencasa.json', '/root/.profile']
        for p in blocked:
            if os.path.exists(p):
                with open(p, 'r') as f:
                    f.read(16)
                return {'ok': False, 'detail': f'SHOULD BE BLOCKED: read {p}'}
        return {'ok': True, 'detail': 'blocked paths not accessible (or files do not exist)'}
    except Exception as e:
        return {'ok': True, 'detail': f'correctly blocked: {str(e)[:80]}'}

TESTS = {
    '/api/test/network-client': ('network:client', _test_network_client),
    '/api/test/network-server': ('network:server', _test_network_server),
    '/api/test/files-read': ('files:read', _test_files_read),
    '/api/test/files-write': ('files:write', _test_files_write),
    '/api/test/system-exec': ('system:exec', _test_system_exec),
    '/api/test/system-monitor': ('system:monitor', _test_system_monitor),
    '/api/test/files-read-blocked': ('unveil', _test_files_read_blocked),
}

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split('?')[0].rstrip('/') or '/index.html'
        if path.startswith('/api/'):
            if path in TESTS:
                perm, fn = TESTS[path]
                result = fn()
                result['permission'] = perm
                self._json(result)
            else:
                self._json({'error': 'not found'}, 404)
            return
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
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *a): pass

http.server.HTTPServer((HOST, PORT), Handler).serve_forever()
