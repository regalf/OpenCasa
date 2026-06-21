import json, os, subprocess, shutil

ctx = json.loads(os.environ.get('OPENCASA_CONTEXT', '{}'))

def size_fmt(n):
    for unit in ('B', 'K', 'M', 'G', 'T'):
        if n < 1024: return f'{n:.1f}{unit}'
        n /= 1024
    return f'{n:.1f}P'

result = []
try:
    total, used, free = shutil.disk_usage('/')
    result.append({'mount': '/', 'total': size_fmt(total), 'used': size_fmt(used), 'free': size_fmt(free), 'pct': round(used/total*100, 1)})
except: pass

for mount in ['/home', '/var', '/tmp', '/usr']:
    try:
        if os.path.ismount(mount):
            total, used, free = shutil.disk_usage(mount)
            result.append({'mount': mount, 'total': size_fmt(total), 'used': size_fmt(used), 'free': size_fmt(free), 'pct': round(used/total*100, 1)})
    except: pass

print(json.dumps(result, indent=2))
