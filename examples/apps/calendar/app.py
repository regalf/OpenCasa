#!/usr/bin/env python3
"""Calendar app — web server + widget data generator."""
import json, os
from datetime import datetime, timedelta

HOST = '127.0.0.1'
PORT = 18997

# ── widget data ──────────────────────────────────────────
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


# ── web server ───────────────────────────────────────────
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
.sub{color:#64748b;font-size:.85rem;margin-top:.2rem}
.nav{display:flex;align-items:center;gap:1rem;margin-bottom:1rem}
.nav-btn{background:#1e293b;border:none;color:#94a3b8;font-size:1.5rem;padding:.2rem .7rem;
  border-radius:6px;cursor:pointer;line-height:1}
.nav-btn:hover{background:#334155;color:#e2e8f0}
.month-label{font-size:1.2rem;font-weight:600;color:#f1f5f9;min-width:12rem;text-align:center}
.weekdays{display:grid;grid-template-columns:repeat(7,1fr);text-align:center;
  color:#64748b;font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;margin-bottom:.3rem}
.days{display:grid;grid-template-columns:repeat(7,1fr);gap:2px}
.day{text-align:center;padding:.5rem .2rem;border-radius:6px;font-size:.95rem;
  cursor:pointer;transition:.1s;position:relative}
.day:hover{background:#334155}
.day.other{color:#475569}
.day.today{background:#f59e0b;color:#0f172a;font-weight:700;border-radius:50%;aspect-ratio:1;
  display:flex;align-items:center;justify-content:center;margin:auto;width:2.2rem}
.day.selected{outline:2px solid #f59e0b;outline-offset:-2px}
.info{margin-top:1rem;background:#1e293b;border-radius:8px;padding:.8rem 1rem;min-height:2rem}
.info .date{color:#f59e0b;font-weight:600}
.info .detail{color:#94a3b8;font-size:.85rem;margin-top:.2rem}
.info .empty{color:#475569;font-style:italic;font-size:.85rem}
</style>
</head>
<body>
<header><h1>Calendar</h1><div><div class="clock" id="clock"></div></div></header>
<div class="nav">
  <button class="nav-btn" onclick="prev()">&#9664;</button>
  <span class="month-label" id="monthLabel"></span>
  <button class="nav-btn" onclick="next()">&#9654;</button>
  <button class="nav-btn" style="font-size:.9rem;padding:.2rem .5rem" onclick="today()">Today</button>
</div>
<div class="weekdays" id="weekdays"></div>
<div class="days" id="days"></div>
<div class="info" id="info"><span class="empty">Click a day for details</span></div>
<script>
// State
let viewYear, viewMonth, selDate = null;
const wd = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
const ms = ['January','February','March','April','May','June','July','August','September','October','November','December'];

function updateClock(){
  const n=new Date();
  const h=String(n.getHours()).padStart(2,'0'),mi=String(n.getMinutes()).padStart(2,'0'),s=String(n.getSeconds()).padStart(2,'0');
  document.getElementById('clock').textContent=h+':'+mi+':'+s;
}

function render(y,m){
  viewYear=y; viewMonth=m;
  document.getElementById('monthLabel').textContent=ms[m]+' '+y;
  // Weekday headers (Sun first)
  document.getElementById('weekdays').innerHTML=wd.map(d=>'<span>'+d+'</span>').join('');
  // Days grid
  const first=new Date(y,m,1).getDay();
  const daysInMonth=new Date(y,m+1,0).getDate();
  const daysInPrev=new Date(y,m,0).getDate();
  const today=new Date();
  const isCurrent=(today.getFullYear()===y && today.getMonth()===m);
  const td=today.getDate();
  let html='';
  // Previous month tail
  for(let i=first-1;i>=0;i--) html+='<div class="day other">'+(daysInPrev-i)+'</div>';
  // Current month
  for(let d=1;d<=daysInMonth;d++){
    const cls='day'+(isCurrent && d===td?' today':'')+(selDate && selDate.getFullYear()===y && selDate.getMonth()===m && selDate.getDate()===d?' selected':'');
    html+='<div class="'+cls+'" onclick="pick('+d+')">'+d+'</div>';
  }
  // Next month head
  const total=first+daysInMonth;
  const rem=(7-total%7)%7;
  for(let i=1;i<=rem;i++) html+='<div class="day other">'+i+'</div>';
  document.getElementById('days').innerHTML=html;
  showInfo();
}

function pick(d){
  selDate=new Date(viewYear,viewMonth,d);
  const days=document.querySelectorAll('.days .day:not(.other)');
  days.forEach(el=>el.classList.remove('selected'));
  if(d>=1 && d<=days.length) days[d-1].classList.add('selected');
  showInfo();
}

function showInfo(){
  const el=document.getElementById('info');
  if(!selDate){el.innerHTML='<span class="empty">Click a day for details</span>';return}
  const d=selDate,dow=wd[d.getDay()];
  el.innerHTML='<div class="date">'+dow+', '+ms[d.getMonth()]+' '+d.getDate()+', '+d.getFullYear()+'</div>'+
    '<div class="detail">Day '+(d.getDate())+' of '+ms[d.getMonth()]+' &middot; Week '+
    d.getWeek()+' &middot; '+(d.getFullYear()===new Date().getFullYear()?'This year':'Year '+d.getFullYear())+'</div>';
}

Date.prototype.getWeek=function(){const d=new Date(Date.UTC(this.getFullYear(),this.getMonth(),this.getDate()));
  d.setUTCDate(d.getUTCDate()+4-(d.getUTCDay()||7));
  const y=Math.ceil((((d-new Date(Date.UTC(d.getUTCFullYear(),0,1)))/864e5)+1)/7);return y};

function prev(){render(viewYear,viewMonth-1<0?(viewYear-1):viewYear,viewMonth-1<0?11:viewMonth-1)}
function next(){render(viewYear,viewMonth+1>11?viewYear+1:viewYear,viewMonth+1>11?0:viewMonth+1)}
function today(){const n=new Date();render(n.getFullYear(),n.getMonth());pick(n.getDate())}

// Init
const n=new Date();
render(n.getFullYear(),n.getMonth());
pick(n.getDate());
updateClock();
setInterval(updateClock,1000);
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
