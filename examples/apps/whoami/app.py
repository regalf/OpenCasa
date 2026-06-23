import subprocess
import sys

try:
    result = subprocess.run(['whoami'], capture_output=True, text=True, timeout=10)
    user = result.stdout.strip()
    print(f"L'app e' stata avviata dall'utente: {user}")
    if user != 'root':
        print("Le misure di sicurezza FUNZIONANO: l'app NON gira come root.")
    else:
        print("ATTENZIONE: l'app gira come root. Verifica che l'utente 'opencasa' esista.")
except Exception as e:
    print(f"Errore: {e}", file=sys.stderr)
    sys.exit(1)
