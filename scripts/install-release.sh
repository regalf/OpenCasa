#!/bin/sh
# Install OpenCasa from a release tarball (stable channel).
# Usage: doas sh install-release.sh [tarball-path]
#   tarball-path: path to OpenCasa-vX.Y.Z.tar.gz (optional, default: download from latest GitHub release)

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

DEST_DIR="${DEST_DIR:-/usr/local/webui}"
CONFIG_PATH="${CONFIG_PATH:-/etc/opencasa.json}"
APP_USER="${APP_USER:-opencasa}"

if [ -f /bsd ]; then
  OS="openbsd"
else
  OS="linux"
fi

ensure_root() {
  if [ "$(id -u)" != "0" ]; then
    if command -v doas >/dev/null 2>&1; then
      exec doas sh "$0" "$@"
    elif command -v sudo >/dev/null 2>&1; then
      exec sudo sh "$0" "$@"
    else
      echo "${RED}This script must be run as root.${NC}"
      exit 1
    fi
  fi
}

_cleanup() {
  [ -n "$_tmp_dir" ] && rm -rf "$_tmp_dir"
  [ -n "$_tmp_tar" ] && rm -f "$_tmp_tar"
}
trap _cleanup EXIT

ensure_root "$@"

TARBALL="$1"
_tmp_tar=""

if [ -z "$TARBALL" ]; then
  echo "${CYAN}Downloading latest release from GitHub...${NC}"

  # Use Python for all HTTP — it's the only guaranteed dependency
  _py_download=$(python3 -c "
import json, urllib.request, sys, os

GH = 'https://api.github.com/repos/regalf/OpenCasa'
HEADERS = {'User-Agent': 'OpenCasa-Installer/1.0'}

try:
    req = urllib.request.Request(GH + '/releases?per_page=1', headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
except Exception as e:
    print('FETCH_ERR:' + str(e), file=sys.stderr)
    sys.exit(1)

if isinstance(data, dict) and data.get('message'):
    print('API_ERR:' + data['message'], file=sys.stderr)
    sys.exit(1)

if not isinstance(data, list) or len(data) == 0:
    print('NO_RELEASES', file=sys.stderr)
    sys.exit(1)

release = data[0]
tag = release.get('tag_name', '')
if not tag:
    print('NO_TAG', file=sys.stderr)
    sys.exit(1)

# Try to find a .tar.gz asset
url = ''
for a in release.get('assets', []):
    if a['name'].endswith('.tar.gz'):
        url = a['browser_download_url']
        break

if not url:
    url = f'https://github.com/regalf/OpenCasa/archive/refs/tags/{tag}.tar.gz'

print(tag)
print(url)
" 2>&1)

  _dl_status=$?
  _tag=$(echo "$_py_download" | sed -n '1p')
  _url=$(echo "$_py_download" | sed -n '2p')
  _py_err=$(echo "$_py_download" | tail -n +3)

  if [ $_dl_status -ne 0 ]; then
    _err_msg=$(echo "$_py_err" | grep -E '^FETCH_ERR:|^API_ERR:|^NO_RELEASES|^NO_TAG' | head -1)
    case "$_err_msg" in
      FETCH_ERR:*) echo "${RED}Network error:${NC} ${_err_msg#FETCH_ERR:}" ;;
      API_ERR:*) echo "${RED}GitHub API:${NC} ${_err_msg#API_ERR:}" ;;
      NO_RELEASES) echo "${RED}No releases found on GitHub.${NC}" ;;
      NO_TAG) echo "${RED}Cannot determine latest version.${NC}" ;;
      *) echo "${RED}Failed to fetch release info.${NC}" ;;
    esac
    echo "${YELLOW}Specify tarball manually: doas sh $0 /path/to/OpenCasa-vX.Y.Z.tar.gz${NC}"
    exit 1
  fi

  echo "  Found $_tag"

  _tmp_tar="$(mktemp /tmp/opencasa-release-XXXXXX.tar.gz)"
  echo "  Downloading..."
  python3 -c "
import urllib.request, sys
url = sys.argv[1]
dest = sys.argv[2]
req = urllib.request.Request(url, headers={'User-Agent': 'OpenCasa-Installer/1.0'})
try:
    with urllib.request.urlopen(req, timeout=120) as src, open(dest, 'wb') as dst:
        while True:
            chunk = src.read(65536)
            if not chunk: break
            dst.write(chunk)
except Exception as e:
    print('DL_ERR:' + str(e), file=sys.stderr)
    sys.exit(1)
" "$_url" "$_tmp_tar" || {
    echo "${RED}Download failed${NC}"
    exit 1
  }
  TARBALL="$_tmp_tar"
fi

if [ ! -f "$TARBALL" ]; then
  echo "${RED}File not found: $TARBALL${NC}"
  exit 1
fi

echo "${CYAN}Extracting...${NC}"
_tmp_dir="$(mktemp -d /tmp/opencasa-extract-XXXXXX)"
tar xzf "$TARBALL" -C "$_tmp_dir"
_src="$(ls -d "$_tmp_dir"/*/ 2>/dev/null | head -1)"
if [ -z "$_src" ]; then
  _src="$_tmp_dir"
fi

echo "${CYAN}Installing files to $DEST_DIR...${NC}"
mkdir -p "$DEST_DIR/webui" "$DEST_DIR/locales" "$DEST_DIR/apps"

cp "$_src/backend/webui.py" "$DEST_DIR/webui.py" 2>/dev/null && echo "  ${GREEN}ok${NC} webui.py" || echo "  ${RED}fail${NC} webui.py"
cp "$_src/backend/webui/"*.py "$DEST_DIR/webui/" 2>/dev/null && echo "  ${GREEN}ok${NC} webui/*.py" || echo "  ${RED}fail${NC} webui/*.py"
cp "$_src/frontend/dist/index.html" "$DEST_DIR/" 2>/dev/null && echo "  ${GREEN}ok${NC} index.html" || echo "  ${RED}fail${NC} index.html"
cp "$_src/frontend/dist/style.css" "$DEST_DIR/" 2>/dev/null && echo "  ${GREEN}ok${NC} style.css" || echo "  ${RED}fail${NC} style.css"
cp "$_src/frontend/dist/app.js" "$DEST_DIR/" 2>/dev/null && echo "  ${GREEN}ok${NC} app.js" || echo "  ${RED}fail${NC} app.js"
cp "$_src/frontend/dist/favicon.svg" "$DEST_DIR/" 2>/dev/null && echo "  ${GREEN}ok${NC} favicon.svg" || echo "  ${RED}fail${NC} favicon.svg"
cp "$_src/frontend/dist/locales/"*.json "$DEST_DIR/locales/" 2>/dev/null && echo "  ${GREEN}ok${NC} locales/*.json" || echo "  ${RED}fail${NC} locales/*.json"

# Config
if [ ! -f "$CONFIG_PATH" ]; then
  echo "${CYAN}Creating config...${NC}"
  _jwt=$( (command -v openssl >/dev/null && openssl rand -hex 32) || (command -v python3 >/dev/null && python3 -c "import secrets; print(secrets.token_hex(32))") || echo "CHANGE-ME-$(date +%s)")
  sed "s/JWT_SECRET_PLACEHOLDER/${_jwt}/" "$_src/opencasa.json.example" > "$CONFIG_PATH" 2>/dev/null || cp "$_src/opencasa.json.example" "$CONFIG_PATH"
  chmod 600 "$CONFIG_PATH"
  echo "  ${GREEN}ok${NC}"
else
  echo "${YELLOW}Config $CONFIG_PATH exists, keeping.${NC}"
fi

# App user
if ! id "$APP_USER" >/dev/null 2>&1; then
  echo "${YELLOW}User $APP_USER not found. Create manually: useradd -m $APP_USER && passwd $APP_USER${NC}"
fi

# Git
if ! command -v git >/dev/null 2>&1; then
  echo "${YELLOW}git not found — recommended for nightly updates.${NC}"
  if [ "$OS" = "openbsd" ]; then
    echo "  Install: doas pkg_add git"
  elif command -v apt >/dev/null 2>&1; then
    apt install -y git 2>/dev/null && echo "  ${GREEN}git installed${NC}" || echo "  ${YELLOW}Install manually: apt install git${NC}"
  elif command -v apk >/dev/null 2>&1; then
    apk add git 2>/dev/null && echo "  ${GREEN}git installed${NC}" || echo "  ${YELLOW}Install manually: apk add git${NC}"
  elif command -v yum >/dev/null 2>&1; then
    yum install -y git 2>/dev/null && echo "  ${GREEN}git installed${NC}" || echo "  ${YELLOW}Install manually: yum install git${NC}"
  else
    echo "  ${YELLOW}Install git manually.${NC}"
  fi
fi

echo ""
echo "${GREEN}${BOLD}OpenCasa installed from release!${NC}"
echo ""
echo "  ${BOLD}First run:${NC}"
echo "    python3 $DEST_DIR/webui.py -c $CONFIG_PATH -d $DEST_DIR"
echo ""
echo "  ${BOLD}Start service:${NC}"
if [ "$OS" = "openbsd" ]; then
  echo "    rcctl start webui"
else
  echo "    systemctl start webui"
fi
