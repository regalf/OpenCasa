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

  _dl() { curl -sL "$1" 2>/dev/null || wget -qO- "$1" 2>/dev/null || ftp -o - "$1" 2>/dev/null; }
  _dl_file() { curl -sL "$1" -o "$2" 2>/dev/null || wget -q "$1" -O "$2" 2>/dev/null || ftp -o "$2" "$1" 2>/dev/null; }

  _json=$(_dl "https://api.github.com/repos/regalf/OpenCasa/releases/latest") || {
    echo "${RED}Failed to fetch latest release info. Specify tarball path manually.${NC}"
    exit 1
  }

  _tag=$(echo "$_json" | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'])" 2>/dev/null || echo "")
  if [ -z "$_tag" ]; then
    echo "${RED}Failed to parse latest release tag. Specify tarball path manually.${NC}"
    exit 1
  fi

  _url=$(echo "$_json" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for a in d.get('assets', []):
    if a['name'].endswith('.tar.gz'):
        print(a['browser_download_url'])
        break
" 2>/dev/null || echo "https://github.com/regalf/OpenCasa/releases/download/$_tag/OpenCasa-$_tag.tar.gz")

  _tmp_tar="$(mktemp /tmp/opencasa-release-XXXXXX.tar.gz)"
  echo "  Downloading $_tag..."
  _dl_file "$_url" "$_tmp_tar" || {
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
