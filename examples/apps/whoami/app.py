import subprocess
import sys

try:
    result = subprocess.run(['whoami'], capture_output=True, text=True, timeout=10)
    user = result.stdout.strip()
    print(f"App is running as user: {user}")
    if user != 'root':
        print("Security measures WORK: the app is NOT running as root.")
    else:
        print("WARNING: app is running as root. Verify that the 'opencasa' user exists.")
except Exception as e:
    print(f"Errore: {e}", file=sys.stderr)
    sys.exit(1)
