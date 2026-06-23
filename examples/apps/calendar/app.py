#!/usr/bin/env python3
"""Calendar app — serves static files + widget data."""
import json, os, mimetypes

HOST = '127.0.0.1'
PORT = 18997
DIR = os.path.dirname(os.path.abspath(__file__))

def widget_data():
    from datetime import datetime, timedelta
    now = datetime.now()
    weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    months = ['', 'January', 'February', 'March', 'April', 'May', 'June',
              'July', 'August', 'September', 'October', 'November', 'December']
    wday = weekdays[now.weekday()]
    mname = months[now.month]
    full_date = now.strftime('%B %d, %Y')
    time_str = now.strftime('%H:%M:%S')

    first = now.replace(day=1)
    if first.month == 12:
        nxt = first.replace(year=first.year + 1, month=1)
    else:
        nxt = first.replace(month=first.month + 1)
    last = nxt - timedelta(days=1)
    start_col = first.weekday()
    total = last.day
    cal_lines = ['  ' + mname + ' ' + str(now.year), 'Mo Tu We Th Fr Sa Su']
    line = '   ' * start_col
    for d in range(1, total + 1):
        line += f'[{d:2d}]' if d == now.day else f' {d:2d} '
        if (start_col + d) % 7 == 0 and d < total:
            cal_lines.append(line)
            line = '   '
    if line.strip():
        cal_lines.append(line)

    return {
        'Today': {'label': wday, 'detail': full_date},
        'Time': {'label': time_str},
        'Calendar': {'label': mname + ' ' + str(now.year), 'detail': '\n'.join(cal_lines)},
    }

if os.environ.get('OPENCASA_ACTION') == 'widget':
    print(json.dumps(widget_data()))
else:
    import http.server
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            clean = self.path.split('?')[0].rstrip('/')
            if clean == '':
                clean = '/index.html'
            if clean == '/api/widget':
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(widget_data()).encode())
                return
            safe = os.path.normpath(clean.lstrip('/'))
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
    http.server.HTTPServer((HOST, PORT), H).serve_forever()
