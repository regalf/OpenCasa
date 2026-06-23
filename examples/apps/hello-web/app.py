#!/usr/bin/env python3
"""Hello Web app — serves static files + API endpoints."""
import http.server, json, os, time, random, platform, mimetypes
from datetime import datetime

HOST = '127.0.0.1'
PORT = 18998
DIR = os.path.dirname(os.path.abspath(__file__))

counter = 0

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split('?')[0].rstrip('/') or '/index.html'
        if path.startswith('/api/'):
            if path == '/api/info':
                self._json({'host': platform.node(), 'python': platform.python_version(),
                            'time': datetime.now().strftime('%H:%M:%S'), 'uptime': f'{time.monotonic()/3600:.1f}h'})
            elif path == '/api/counter':
                self._json({'value': counter})
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

    def do_POST(self):
        global counter
        if self.path == '/api/counter':
            counter += 1
            self._json({'value': counter})
        elif self.path == '/api/echo':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length) if length else b'{}'
            try:
                d = json.loads(body)
                msg = d.get('msg', '')
            except:
                msg = ''
            self._json({'echo': msg, 'len': len(msg)})
        else:
            self._json({'error': 'not found'}, 404)

    def _json(self, data, code=200):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *a): pass

http.server.HTTPServer((HOST, PORT), Handler).serve_forever()
