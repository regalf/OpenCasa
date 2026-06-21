import json, os, platform, datetime

ctx = json.loads(os.environ.get('OPENCASA_CONTEXT', '{}'))

print(f"""Hello from {ctx.get('name', 'unknown')}!
App ID: {ctx.get('app_id', '?')}
Permissions: {', '.join(ctx.get('permissions', []))}
API URL: {ctx.get('api_url', '?')}

System: {platform.system()} {platform.release()}
Host: {platform.node()}
Python: {platform.python_version()}
Time: {datetime.datetime.now().isoformat()}
""")
