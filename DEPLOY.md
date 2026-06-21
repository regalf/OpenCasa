# Deploy su OpenBSD/macppc

## File necessari (solo questi 4)

| File | Destino sul Mac |
|------|----------------|
| `backend/webui.py` | `/usr/local/webui/webui.py` |
| `backend/webui/*.py` | `/usr/local/webui/webui/*.py` |
| `frontend/dist/index.html` | `/usr/local/webui/index.html` |
| `frontend/dist/favicon.svg` | `/usr/local/webui/favicon.svg` |
| `opencasa.json.example` | `/etc/opencasa.json` (rinominato) |
| `scripts/webui` | `/etc/rc.d/webui` |

## Metodo 1 — Via SCP (consigliato)

Dalla macchina di sviluppo (questa):
```sh
scp backend/webui.py utente@mac:~/
scp -r backend/webui utente@mac:~/webui_pkg/
scp frontend/dist/index.html utente@mac:~/
scp frontend/dist/favicon.svg utente@mac:~/
scp opencasa.json.example utente@mac:~/
scp scripts/webui utente@mac:~/
```

Poi su OpenBSD:
```sh
doas mkdir -p /usr/local/webui/apps
doas mv webui.py /usr/local/webui/
doas mv webui_pkg /usr/local/webui/webui
doas mv index.html /usr/local/webui/
doas mv favicon.svg /usr/local/webui/
doas mv webui /etc/rc.d/webui
doas chmod +x /etc/rc.d/webui
doas mv opencasa.json.example /etc/opencasa.json
```

## Metodo 2 — Via chiavetta USB

Se il Mac non ha rete, monta una USB e copia:
```sh
doas mount /dev/sd0i /mnt
doas mkdir -p /usr/local/webui/apps
doas cp /mnt/webui.py /usr/local/webui/
doas cp -r /mnt/webui /usr/local/webui/webui
doas cp /mnt/index.html /usr/local/webui/
doas cp /mnt/favicon.svg /usr/local/webui/
doas cp /mnt/webui_rc /etc/rc.d/webui
doas chmod +x /etc/rc.d/webui
doas cp /mnt/opencasa.json.example /etc/opencasa.json
```

## Metodo 3 — Download diretto (se il Mac ha rete)

```sh
# Se hai un server HTTP con i file
doas mkdir -p /usr/local/webui/apps /usr/local/webui/webui
ftp -o /usr/local/webui/webui.py http://tua-macchina/webui.py
ftp -o /usr/local/webui/index.html http://tua-macchina/index.html
ftp -o /usr/local/webui/favicon.svg http://tua-macchina/favicon.svg
# Scaricare ogni file .py in /usr/local/webui/webui/
# (oppure tar -czf webui.tgz backend/webui/ e ftp + tar -xz su OpenBSD)
```

## Configurazione

```sh
# Genera un segreto JWT
openssl rand -hex 32

# Aprilo e incollalo in jwt_secret
doas vi /etc/opencasa.json
```

Il file `/etc/opencasa.json`:
```json
{
  "server": {"host": "0.0.0.0", "port": 80},
  "auth": {
    "enabled": true,
    "jwt_secret": "il-segreto-generato-sopra",
    "session_ttl": "24h"
  },
  "filesystem": {
    "allowed_prefixes": ["/home", "/var/www", "/mnt", "/tmp"],
    "max_upload_size": 100
  },
  "log": {"level": "info", "file": "/var/log/webui.log"},
  "apps_autostart": true
}
```

## Python su OpenBSD

```sh
# Verifica se c'è già (base system)
python3 --version

# Se non c'è, installalo
doas pkg_add python
```

## Avvio

```sh
doas rcctl enable webui
doas rcctl start webui

# Stato
doas rcctl status webui

# Log
doas tail -f /var/log/webui.log
```

Apri browser su: `http://IP-DEL-MAC`
Credenziali: `admin` / `admin`

## Test rapido

```sh
curl http://localhost/                          # frontend
curl -X POST http://localhost/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'  # login
```
