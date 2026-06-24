#!/usr/bin/env python3
"""Notify Test — simple static file server."""
import http.server, json, os, mimetypes

HOST = '127.0.0.1'
PORT = int(os.environ.get('OPENCASA_APP_PORT', '19015'))
DIR = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split('?')[0].rstrip('/') or '/index.html'
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

    def log_message(self, *a): pass


http.server.HTTPServer((HOST, PORT), Handler).serve_forever()
