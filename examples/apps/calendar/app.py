#!/usr/bin/env python3
"""Calendar app — web server + widget data generator."""
import json, os
from datetime import datetime, timedelta

HOST = '127.0.0.1'
PORT = 18997

def widget_data():
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

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Calendar — OpenCasa</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
  background:#0f172a;color:#e2e8f0;padding:1.2rem;min-height:100vh}
header{display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem}
h1{color:#f59e0b;font-size:1.3rem}
.clock{font-size:1.8rem;font-weight:300;color:#e2e8f0;font-variant-numeric:tabular-nums;letter-spacing:.05em}
.nav{display:flex;align-items:center;gap:1rem;margin-bottom:1rem}
.nav-btn{background:#1e293b;border:none;color:#94a3b8;font-size:1.5rem;padding:.2rem .7rem;
  border-radius:6px;cursor:pointer;line-height:1}
.nav-btn:hover{background:#334155;color:#e2e8f0}
.nav-today{background:#1e293b;border:none;color:#94a3b8;font-size:.9rem;padding:.2rem .6rem;
  border-radius:6px;cursor:pointer;line-height:1}
.nav-today:hover{background:#334155;color:#e2e8f0}
.month-label{font-size:1.2rem;font-weight:600;color:#f1f5f9;min-width:12rem;text-align:center}
.weekdays{display:grid;grid-template-columns:repeat(7,1fr);text-align:center;
  color:#64748b;font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;margin-bottom:.3rem}
.days{display:grid;grid-template-columns:repeat(7,1fr);gap:2px}
.day{text-align:center;padding:.5rem .2rem;border-radius:6px;font-size:.95rem;
  cursor:pointer;transition:.1s;position:relative}
.day:hover{background:#334155}
.day.other{color:#475569}
.day.today{background:#f59e0b;color:#0f172a;font-weight:700}
.day.selected{outline:2px solid #f59e0b;outline-offset:-2px}
.info{margin-top:1rem;background:#1e293b;border-radius:8px;padding:.8rem 1rem;min-height:2rem}
.info .date{color:#f59e0b;font-weight:600}
.info .detail{color:#94a3b8;font-size:.85rem;margin-top:.2rem}
.info .empty{color:#475569;font-style:italic;font-size:.85rem}
</style>
</head>
<body>
<header><h1>Calendar</h1><div class="clock" id="clock"></div></header>
<div class="nav">
  <button class="nav-btn" id="btnPrev">&#9664;</button>
  <span class="month-label" id="monthLabel"></span>
  <button class="nav-btn" id="btnNext">&#9654;</button>
  <button class="nav-today" id="btnToday">Today</button>
</div>
<div class="weekdays" id="weekdays"></div>
<div class="days" id="days"></div>
<div class="info" id="info"></div>
<script>
(function(){
  var curYear, curMonth, selDate = null;
  var wd = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
  var ms = ['January','February','March','April','May','June',
            'July','August','September','October','November','December'];

  function updateClock(){
    var n = new Date();
    var h = String(n.getHours()).padStart(2,'0');
    var mi = String(n.getMinutes()).padStart(2,'0');
    var s = String(n.getSeconds()).padStart(2,'0');
    document.getElementById('clock').textContent = h + ':' + mi + ':' + s;
  }

  function isoWeek(d){
    var dt = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
    dt.setUTCDate(dt.getUTCDate() + 4 - (dt.getUTCDay() || 7));
    var y = dt.getUTCFullYear();
    var start = new Date(Date.UTC(y, 0, 1));
    return Math.ceil((((dt - start) / 864e5) + 1) / 7);
  }

  function monthDays(y, m){
    return new Date(y, m + 1, 0).getDate();
  }

  function render(y, m){
    if (m < 0){ m = 11; y--; }
    if (m > 11){ m = 0; y++; }
    curYear = y; curMonth = m;

    document.getElementById('monthLabel').textContent = ms[m] + ' ' + y;

    var wdHtml = '';
    for (var i = 0; i < 7; i++) wdHtml += '<span>' + wd[i] + '</span>';
    document.getElementById('weekdays').innerHTML = wdHtml;

    var first = new Date(y, m, 1).getDay();
    var dim = monthDays(y, m);
    var prevDim = monthDays(y, m - 1);
    var today = new Date();
    var isTodayMonth = (today.getFullYear() === y && today.getMonth() === m);
    var todayNum = today.getDate();
    var html = '';
    var cell = 0;

    for (var i = first - 1; i >= 0; i--){
      html += '<div class="day other" data-day="' + (prevDim - i) + '" data-other="1">' + (prevDim - i) + '</div>';
      cell++;
    }
    for (var d = 1; d <= dim; d++){
      var cls = 'day';
      if (isTodayMonth && d === todayNum) cls += ' today';
      if (selDate && selDate.getFullYear() === y && selDate.getMonth() === m && selDate.getDate() === d) cls += ' selected';
      html += '<div class="' + cls + '" data-day="' + d + '">' + d + '</div>';
      cell++;
    }
    var rem = (7 - (cell % 7)) % 7;
    for (var i = 1; i <= rem; i++){
      html += '<div class="day other" data-day="' + i + '" data-other="1">' + i + '</div>';
    }
    document.getElementById('days').innerHTML = html;
    showInfo();
  }

  function pickDay(d, other){
    other = other || false;
    if (other){
      if (d > 28){
        render(curYear, curMonth + 1);
        selectDay(d);
      } else {
        render(curYear, curMonth - 1);
        selectDay(d);
      }
      return;
    }
    selectDay(d);
  }

  function selectDay(d){
    selDate = new Date(curYear, curMonth, d);
    var els = document.querySelectorAll('#days .day');
    for (var i = 0; i < els.length; i++) els[i].classList.remove('selected');
    var target = document.querySelector('#days .day[data-day="' + d + '"]:not(.other)');
    if (target) target.classList.add('selected');
    showInfo();
  }

  function showInfo(){
    var el = document.getElementById('info');
    if (!selDate){
      el.innerHTML = '<span class="empty">Click a day for details</span>';
      return;
    }
    var d = selDate;
    var dow = wd[d.getDay()];
    var week = isoWeek(d);
    var yearLabel = (d.getFullYear() === new Date().getFullYear()) ? 'This year' : 'Year ' + d.getFullYear();
    el.innerHTML = '<div class="date">' + dow + ', ' + ms[d.getMonth()] + ' ' + d.getDate() + ', ' + d.getFullYear() + '</div>' +
      '<div class="detail">Day ' + d.getDate() + ' of ' + ms[d.getMonth()] + ' \u00B7 Week ' + week + ' \u00B7 ' + yearLabel + '</div>';
  }

  function prevMonth(){ render(curYear, curMonth - 1); }
  function nextMonth(){ render(curYear, curMonth + 1); }
  function goToday(){
    var n = new Date();
    render(n.getFullYear(), n.getMonth());
    selDate = null;
    selectDay(n.getDate());
  }

  document.getElementById('btnPrev').addEventListener('click', prevMonth);
  document.getElementById('btnNext').addEventListener('click', nextMonth);
  document.getElementById('btnToday').addEventListener('click', goToday);

  document.getElementById('days').addEventListener('click', function(e){
    var target = e.target;
    if (!target.classList.contains('day')) return;
    var d = parseInt(target.getAttribute('data-day'), 10);
    var other = target.hasAttribute('data-other');
    pickDay(d, other);
  });

  var n = new Date();
  render(n.getFullYear(), n.getMonth());
  selectDay(n.getDate());
  updateClock();
  setInterval(updateClock, 1000);
})();
</script>
</body>
</html>"""

if os.environ.get('OPENCASA_ACTION') == 'widget':
    print(json.dumps(widget_data()))
else:
    import http.server
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ('/','/app/calendar/','/api/widget'):
                if self.path == '/api/widget':
                    self.send_response(200)
                    self.send_header('Content-Type','application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(widget_data()).encode())
                else:
                    self.send_response(200)
                    self.send_header('Content-Type','text/html; charset=utf-8')
                    self.send_header('Cache-Control','no-cache')
                    self.end_headers()
                    self.wfile.write(PAGE.encode())
            else:
                self.send_response(404)
                self.end_headers()
        def log_message(self,*a): pass
    http.server.HTTPServer((HOST,PORT),H).serve_forever()
