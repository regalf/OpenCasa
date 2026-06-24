# Deploy on OpenBSD/macppc

## Required files

| File | Destination |
|------|-------------|
| `backend/webui.py` | `/usr/local/webui/webui.py` |
| `backend/webui/*.py` | `/usr/local/webui/webui/*.py` |
| `frontend/dist/index.html` | `/usr/local/webui/index.html` |
| `frontend/dist/style.css` | `/usr/local/webui/style.css` |
| `frontend/dist/app.js` | `/usr/local/webui/app.js` |
| `frontend/dist/favicon.svg` | `/usr/local/webui/favicon.svg` |
| `frontend/dist/locales/` | `/usr/local/webui/locales/` |
| `opencasa.json.example` | `/etc/opencasa.json` (rename) |
| `scripts/webui` | `/etc/rc.d/webui` |

## Method 1 — SCP (recommended)

From your development machine:
```sh
scp backend/webui.py user@mac:~/
scp -r backend/webui user@mac:~/webui_pkg/
scp frontend/dist/index.html user@mac:~/
scp frontend/dist/style.css user@mac:~/
scp frontend/dist/app.js user@mac:~/
scp frontend/dist/favicon.svg user@mac:~/
scp -r frontend/dist/locales user@mac:~/
scp opencasa.json.example user@mac:~/
scp scripts/webui user@mac:~/
```

Then on OpenBSD:
```sh
doas mkdir -p /usr/local/webui/apps
doas mv webui.py /usr/local/webui/
doas mv webui_pkg /usr/local/webui/webui
doas mv index.html style.css app.js /usr/local/webui/
doas mv favicon.svg /usr/local/webui/
doas mv locales /usr/local/webui/locales
doas mv webui /etc/rc.d/webui
doas chmod +x /etc/rc.d/webui
doas mv opencasa.json.example /etc/opencasa.json
```

## Method 2 — USB drive

If the Mac has no network, mount a USB drive and copy:
```sh
doas mount /dev/sd0i /mnt
doas mkdir -p /usr/local/webui/apps
doas cp /mnt/webui.py /usr/local/webui/
doas cp -r /mnt/webui /usr/local/webui/webui
doas cp /mnt/index.html /mnt/style.css /mnt/app.js /usr/local/webui/
doas cp /mnt/favicon.svg /usr/local/webui/
doas cp -r /mnt/locales /usr/local/webui/locales
doas cp /mnt/webui_rc /etc/rc.d/webui
doas chmod +x /etc/rc.d/webui
doas cp /mnt/opencasa.json.example /etc/opencasa.json
```

## Method 3 — Direct download (if the Mac has network)

```sh
doas mkdir -p /usr/local/webui/apps /usr/local/webui/webui
ftp -o /usr/local/webui/webui.py http://your-machine/webui.py
ftp -o /usr/local/webui/index.html http://your-machine/index.html
ftp -o /usr/local/webui/style.css http://your-machine/style.css
ftp -o /usr/local/webui/app.js http://your-machine/app.js
ftp -o /usr/local/webui/favicon.svg http://your-machine/favicon.svg
# Download each .py file into /usr/local/webui/webui/
# (or tar -czf webui.tgz backend/webui/ and ftp + tar -xz on OpenBSD)
```

## Quick install (recommended)

```sh
curl -s https://raw.githubusercontent.com/regalf/OpenCasa/main/scripts/install.sh | doas sh
```

This automates all the steps above.

## Configuration

```sh
# Generate a JWT secret
openssl rand -hex 32

# Open the config and paste it into jwt_secret
doas vi /etc/opencasa.json
```

The file `/etc/opencasa.json`:
```json
{
  "server": {"host": "0.0.0.0", "port": 80},
  "auth": {
    "enabled": true,
    "jwt_secret": "your-generated-secret",
    "session_ttl": "24h"
  },
  "filesystem": {
    "allowed_prefixes": ["/home/opencasa"],
    "max_upload_size": 100
  },
  "log": {"level": "info", "file": "/var/log/webui.log"},
  "app_user": "opencasa",
  "apps_autostart": true
}
```

### App user

Create the unprivileged user for running apps (if the install script didn't do it):
```sh
doas useradd -m opencasa
doas passwd opencasa   # optional, set a password
```

## Python on OpenBSD

```sh
# Check if Python is already installed (base system may include it)
python3 --version

# If not, install it
doas pkg_add python
```

## TLS / HTTPS

OpenCasa does not provide HTTPS directly. For production use, terminate TLS with a reverse proxy:

**nginx example:**
```nginx
server {
    listen 443 ssl;
    server_name your-domain.example.com;
    ssl_certificate /etc/ssl/cert.pem;
    ssl_certificate_key /etc/ssl/private/key.pem;
    location / {
        proxy_pass http://127.0.0.1:80;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

**httpd(8) example (OpenBSD):**
```
server "your-domain.example.com" {
    listen on * port 443 tls
    tls certificate "/etc/ssl/cert.pem"
    tls key "/etc/ssl/private/key.pem"
    location "/*" {
        proxy http://127.0.0.1 port 80
    }
}
```

## Startup

```sh
doas rcctl enable webui
doas rcctl start webui

# Status
doas rcctl status webui

# Logs
doas tail -f /var/log/webui.log
```

Open a browser at: `http://IP-OF-MAC`
Default credentials: `admin` / `admin`

## Quick test

```sh
curl http://localhost/                          # frontend
curl -X POST http://localhost/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'  # login
```
