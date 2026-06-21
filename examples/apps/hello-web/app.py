#!/usr/bin/env python3
import http.server, json, os, time, random, platform
from datetime import datetime

HOST = '127.0.0.1'
PORT = 18998

import os, json
_ctx = json.loads(os.environ.get('OPENCASA_CONTEXT', '{}'))
APP_BASE = '/app/' + _ctx.get('app_id', '') if _ctx.get('app_id') else ''

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Hello Web</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
  background:#0f172a;color:#e2e8f0;padding:1.2rem}
h1{color:#38bdf8;font-size:1.3rem;margin-bottom:.5rem}
.card{background:#1e293b;border-radius:8px;padding:.8rem 1rem;margin:.5rem 0}
.card .val{font-size:1.3rem;font-weight:700}
.card .lbl{font-size:.8rem;color:#64748b}
.row{display:flex;gap:.5rem;align-items:center;margin:.4rem 0}
.btn{background:#0ea5e9;color:#fff;border:none;padding:.4rem .8rem;border-radius:5px;cursor:pointer;font-size:.9rem}
.btn:hover{background:#0284c7}
input{background:#0f172a;border:1px solid #334155;color:#e2e8f0;padding:.4rem .6rem;border-radius:5px;font-size:.9rem;flex:1}
.dim{color:#64748b;font-size:.85rem}
#msg{color:#22c55e;margin:.4rem 0}
</style>
</head>
<body>
<h1>Hello Web</h1>
<p class="dim">This app runs in its own tab via iframe.</p>

<div class="card">
  <div class="lbl">Counter (server-side)</div>
  <div class="val" id="counter">0</div>
  <button class="btn" onclick="inc()">+1</button>
</div>

<div class="card">
  <div class="lbl">Type a message</div>
  <div class="row">
    <input id="msgInput" placeholder="write something..." />
    <button class="btn" onclick="sendMsg()">Send</button>
  </div>
  <div id="msg"></div>
</div>

<div class="card">
  <div class="lbl">Server info</div>
  <div id="info"></div>
</div>

<script>
const BASE = '""" + APP_BASE + r"""';
async function inc(){
  const r=await fetch(BASE+'/api/counter',{method:'POST'});
  const d=await r.json();
  document.getElementById('counter').textContent=d.value;
}
async function sendMsg(){
  const val=document.getElementById('msgInput').value;
  const r=await fetch(BASE+'/api/echo',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({msg:val})});
  const d=await r.json();
  document.getElementById('msg').textContent='You said: '+d.echo+' (length: '+d.len+')';
}
async function loadInfo(){
  const r=await fetch(BASE+'/api/info');
  const d=await r.json();
  const html= Object.entries(d).map(([k,v])=>'<div class="row"><span class="lbl">'+esc(k)+'</span><span>'+esc(v)+'</span></div>').join('');
  document.getElementById('info').innerHTML=html;
}
function esc(s){return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
loadInfo();
</script>
</body>
</html>"""

counter = 0

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path.startswith('/hello-web'):
            self._serve_page()
        elif self.path == '/api/info':
            self._json({'host': platform.node(), 'python': platform.python_version(),
                        'time': datetime.now().strftime('%H:%M:%S'), 'uptime': f'{time.monotonic()/3600:.1f}h'})
        elif self.path == '/api/counter':
            self._json({'value': counter})
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'404')
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
            except: msg = ''
            self._json({'echo': msg, 'len': len(msg)})
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'404')
    def _serve_page(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(PAGE.encode())
    def _json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    def log_message(self, *a): pass

http.server.HTTPServer((HOST, PORT), Handler).serve_forever()
