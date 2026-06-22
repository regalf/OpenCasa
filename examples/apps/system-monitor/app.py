import json, os, subprocess, platform

def get_cpu():
    try:
        is_bsd = os.path.exists('/bsd') or platform.system() == 'OpenBSD'
        if is_bsd:
            out = subprocess.run(['vmstat', '1', '2'], capture_output=True, text=True, timeout=3)
            lines = out.stdout.strip().split('\n')
            if len(lines) >= 3:
                parts = lines[-1].split()
                if len(parts) >= 17:
                    us = int(parts[16])
                    sys = int(parts[17]) if len(parts) > 17 else 0
                    idl = int(parts[18]) if len(parts) > 18 else (100 - us - sys)
                    return {'used': us + sys, 'idle': idl}
        else:
            with open('/proc/stat') as f:
                line = f.readline()
            parts = line.split()
            if parts[0] == 'cpu' and len(parts) >= 5:
                user = int(parts[1])
                nice = int(parts[2])
                sys = int(parts[3])
                idle = int(parts[4])
                total = user + nice + sys + idle
                used_pct = round((user + nice + sys) / total * 100, 1)
                idle_pct = round(idle / total * 100, 1)
                return {'used': used_pct, 'idle': idle_pct}
    except: pass
    return {'used': 0, 'idle': 100}

def get_mem():
    try:
        is_bsd = os.path.exists('/bsd') or platform.system() == 'OpenBSD'
        if is_bsd:
            out = subprocess.run(['vmstat', '-s'], capture_output=True, text=True, timeout=3)
            managed = active = free = 0
            for line in out.stdout.split('\n'):
                parts = line.strip().split()
                if not parts or not parts[0].isdigit(): continue
                val = int(parts[0])
                text = ' '.join(parts[1:])
                if 'pages managed' in text: managed = val
                elif 'pages free' in text: free = val
                elif 'pages active' in text: active = val
            if managed:
                used = managed - free
                pct = round(used / managed * 100, 1)
                return {'used_pct': pct, 'total_mb': round(managed / 256, 1), 'used_mb': round(used / 256, 1), 'free_mb': round(free / 256, 1)}
        else:
            with open('/proc/meminfo') as f:
                data = {}
                for line in f:
                    parts = line.split(':')
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val = parts[1].strip().split()[0]
                        data[key] = int(val)
            total = data.get('MemTotal', 0) // 1024
            free = data.get('MemFree', 0) // 1024
            used = total - free
            pct = round(used / total * 100, 1) if total else 0
            return {'used_pct': pct, 'total_mb': total, 'used_mb': used, 'free_mb': free}
    except: pass
    return {'used_pct': 0, 'total_mb': 0, 'used_mb': 0, 'free_mb': 0}

def get_uptime():
    try:
        with open('/proc/uptime') as f:
            secs = float(f.read().split()[0])
            days = int(secs // 86400)
            secs %= 86400
            hrs = int(secs // 3600)
            mins = int(secs % 3600 // 60)
            return f'{days}d {hrs}h {mins}m'
    except:
        try:
            out = subprocess.run(['uptime'], capture_output=True, text=True, timeout=3)
            return out.stdout.strip().split(',')[0].strip()
        except: pass
    return ''

cpu = get_cpu()
mem = get_mem()
upt = get_uptime()

out = {'System': f'CPU {cpu["used"]}%  Mem {mem["used_pct"]}% ({mem["free_mb"]}M free)'}
if upt:
    out['Uptime'] = upt

print(json.dumps(out))
