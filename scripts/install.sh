#!/bin/sh
#
# OpenCasa Installer
# Works on OpenBSD and Linux
#
# Usage:
#   Local:  doas sh scripts/install.sh
#   Remote: curl -s https://raw.githubusercontent.com/regalf/OpenCasa/main/scripts/install.sh | doas sh
#

set -u

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

REPO="https://github.com/regalf/OpenCasa"
SRC_DIR="${1:-}"
DEST_DIR="${2:-/usr/local/webui}"
CONFIG_PATH="${3:-/etc/opencasa.json}"
APP_USER="opencasa"

prompt_yes() {
  printf "%s [Y/n] " "$1"
  _ans="y"
  read _ans < /dev/tty 2>/dev/null || true
  case "$_ans" in
    n|N|no|No) return 1 ;;
    *) return 0 ;;
  esac
}

pick_os() {
  if [ -f /bsd ]; then
    _detected="openbsd"
  elif uname -s | grep -qi linux; then
    _detected="linux"
  else
    _detected="unknown"
  fi
  printf "${CYAN}Detected OS:${NC} ${_detected}\n"
  if ! prompt_yes "Is this correct?"; then
    printf "Select OS:\n  1) OpenBSD\n  2) Linux\n  > "
    _choice=""
    read _choice < /dev/tty 2>/dev/null || true
    case "$_choice" in
      1) OS="openbsd" ;;
      2) OS="linux" ;;
      *) printf "${RED}Invalid choice${NC}\n"; exit 1 ;;
    esac
  else
    OS="$_detected"
  fi
}

ensure_root() {
  if [ "$(id -u)" -ne 0 ]; then
    if [ -f "$0" ]; then
      if command -v doas >/dev/null 2>&1; then
        exec doas "$0" "$@"
      elif command -v sudo >/dev/null 2>&1; then
        exec sudo "$0" "$@"
      fi
    fi
    printf "${YELLOW}Re-run with: doas sh %s${NC}\n" "${0:-scripts/install.sh}"
    printf "${YELLOW}Or pipe: curl -s https://raw.githubusercontent.com/regalf/OpenCasa/main/scripts/install.sh | doas sh${NC}\n"
    exit 1
  fi
}

fetch_source() {
  if [ -n "$SRC_DIR" ]; then
    if [ -f "$SRC_DIR/backend/webui.py" ]; then
      return 0
    fi
    printf "${YELLOW}Source dir %s invalid, downloading...${NC}\n" "$SRC_DIR"
  elif [ -f "./backend/webui.py" ]; then
    SRC_DIR="."
    printf "${GREEN}Using local source:${NC} $(pwd)\n"
    return 0
  elif [ -f "../backend/webui.py" ]; then
    SRC_DIR=".."
    printf "${GREEN}Using local source:${NC} $(pwd)\n"
    return 0
  fi

  printf "\n${CYAN}Downloading OpenCasa from GitHub...${NC}\n"
  _tmp=$(mktemp -d /tmp/opencasa-XXXXXX) || exit 1

  if command -v git >/dev/null 2>&1; then
    git clone --depth 1 "${REPO}.git" "$_tmp/repo" 2>/dev/null && {
      SRC_DIR="$_tmp/repo"
      printf "  ${GREEN}✓${NC} Cloned from GitHub\n"
      return 0
    }
    printf "  ${YELLOW}git clone failed, trying archive...${NC}\n"
  fi

  _tar="${REPO}/archive/refs/heads/main.tar.gz"
  if command -v ftp >/dev/null 2>&1; then
    ftp -o - "$_tar" 2>/dev/null | tar xzf - -C "$_tmp" 2>/dev/null || {
      printf "${RED}Download failed.${NC}\n"; rm -rf "$_tmp"; exit 1
    }
  elif command -v curl >/dev/null 2>&1; then
    curl -sL "$_tar" | tar xzf - -C "$_tmp" 2>/dev/null || {
      printf "${RED}Download failed.${NC}\n"; rm -rf "$_tmp"; exit 1
    }
  elif command -v wget >/dev/null 2>&1; then
    wget -qO- "$_tar" | tar xzf - -C "$_tmp" 2>/dev/null || {
      printf "${RED}Download failed.${NC}\n"; rm -rf "$_tmp"; exit 1
    }
  else
    printf "${RED}No download tool found (git/ftp/curl/wget).${NC}\n"
    printf "Clone manually: git clone ${REPO}.git && cd OpenCasa && doas sh scripts/install.sh\n"
    rm -rf "$_tmp"
    exit 1
  fi

  SRC_DIR="$_tmp/OpenCasa-main"
  printf "  ${GREEN}✓${NC} Downloaded to ${SRC_DIR}\n"
}

cleanup() {
  if echo "$SRC_DIR" | grep -q '/tmp/opencasa-'; then
    rm -rf "$SRC_DIR"
  fi
}

banner() {
  cat << 'EOF'
  ___                   ___                 
 / _ \ _ __   ___ ___ / __| __ __ _  ___ ___
| | | | '_ \ / _ / __| (__ _/ _| ' \/ -_|_-<
| |_| | |_) |  __\__ \___| (_|_|_|_\___/__/
 \___/| .__/ \___|___/                      
      |_|                                   
EOF
  printf "  ${CYAN}OpenCasa Installer${NC}\n\n"
}

show_summary() {
  cat << EOF

${BOLD}Installation Summary${NC}
  OS:          ${OS}
  Destination: ${DEST_DIR}
  Config:      ${CONFIG_PATH}
  App user:    ${APP_USER}

Files to install:
  ${DEST_DIR}/webui.py
  ${DEST_DIR}/webui/*.py
  ${DEST_DIR}/index.html
  ${DEST_DIR}/style.css
  ${DEST_DIR}/app.js
  ${DEST_DIR}/favicon.svg
  ${DEST_DIR}/locales/
  ${CONFIG_PATH}
  $( [ "$OS" = "openbsd" ] && echo "/etc/rc.d/webui" || echo "/etc/systemd/system/webui.service" )
EOF
}

install_files() {
  printf "\n${BOLD}Installing files...${NC}\n"
  mkdir -p "$DEST_DIR/webui" "$DEST_DIR/locales" "$DEST_DIR/apps"

  cp "$SRC_DIR/backend/webui.py" "$DEST_DIR/webui.py" && printf "  ${GREEN}✓${NC} webui.py\n" || printf "  ${RED}✗${NC} webui.py\n"
  cp "$SRC_DIR/backend/webui/"*.py "$DEST_DIR/webui/" && printf "  ${GREEN}✓${NC} webui/*.py\n" || printf "  ${RED}✗${NC} webui/*.py\n"
  cp "$SRC_DIR/frontend/dist/index.html" "$DEST_DIR/" && printf "  ${GREEN}✓${NC} index.html\n" || printf "  ${RED}✗${NC} index.html\n"
  cp "$SRC_DIR/frontend/dist/style.css" "$DEST_DIR/" && printf "  ${GREEN}✓${NC} style.css\n" || printf "  ${RED}✗${NC} style.css\n"
  cp "$SRC_DIR/frontend/dist/app.js" "$DEST_DIR/" && printf "  ${GREEN}✓${NC} app.js\n" || printf "  ${RED}✗${NC} app.js\n"
  cp "$SRC_DIR/frontend/dist/favicon.svg" "$DEST_DIR/" && printf "  ${GREEN}✓${NC} favicon.svg\n" || printf "  ${RED}✗${NC} favicon.svg\n"
  cp "$SRC_DIR/frontend/dist/locales/"*.json "$DEST_DIR/locales/" && printf "  ${GREEN}✓${NC} locales/*.json\n" || printf "  ${RED}✗${NC} locales/*.json\n"
  chmod -R 755 "$DEST_DIR/webui" "$DEST_DIR/webui.py"
}

setup_config() {
  if [ -f "$CONFIG_PATH" ]; then
    printf "\n${YELLOW}Config already exists at %s${NC}\n" "$CONFIG_PATH"
    if ! prompt_yes "Overwrite?"; then
      printf "  ${YELLOW}Keeping existing config.${NC}\n"
      return
    fi
  fi
  _jwt=$( (command -v openssl >/dev/null && openssl rand -hex 32) || (command -v python3 >/dev/null && python3 -c "import secrets; print(secrets.token_hex(32))") || echo "CHANGE-ME-$(date +%s)" )
  sed "s/JWT_SECRET_PLACEHOLDER/${_jwt}/" "$SRC_DIR/opencasa.json.example" > "$CONFIG_PATH" 2>/dev/null || cp "$SRC_DIR/opencasa.json.example" "$CONFIG_PATH"
  chmod 600 "$CONFIG_PATH"
  printf "  ${GREEN}✓${NC} %s created\n" "$CONFIG_PATH"
}

setup_service() {
  printf "\n${BOLD}Setting up service...${NC}\n"
  if [ "$OS" = "openbsd" ]; then
    cp "$SRC_DIR/scripts/webui" /etc/rc.d/webui
    chmod 755 /etc/rc.d/webui
    printf "  ${GREEN}✓${NC} /etc/rc.d/webui\n"
    if prompt_yes "Enable and start webui now?"; then
      rcctl enable webui && rcctl start webui && printf "  ${GREEN}✓${NC} Service started\n" || printf "  ${RED}✗${NC} Service start failed\n"
    fi
  else
    cp "$SRC_DIR/scripts/webui.service" /etc/systemd/system/webui.service
    chmod 644 /etc/systemd/system/webui.service
    systemctl daemon-reload
    printf "  ${GREEN}✓${NC} /etc/systemd/system/webui.service\n"
    if prompt_yes "Enable and start webui now?"; then
      systemctl enable --now webui && printf "  ${GREEN}✓${NC} Service started\n" || printf "  ${RED}✗${NC} Service start failed\n"
    fi
  fi
}

check_python() {
  printf "\n${BOLD}Checking Python...${NC}\n"
  if command -v python3 >/dev/null 2>&1; then
    printf "  %s " "$(python3 --version 2>&1)"
    printf "${GREEN}✓${NC}\n"
  elif command -v python >/dev/null 2>&1; then
    _py=$(command -v python)
    printf "  %s " "$(${_py} --version 2>&1)"
    if [ "$OS" = "openbsd" ]; then
      printf "${YELLOW}→ symlinking to python3${NC}\n"
      ln -sf "$_py" /usr/local/bin/python3 2>/dev/null || printf "  ${YELLOW}Symlink failed, create manually${NC}\n"
    else
      printf "${YELLOW}→ symlinking to python3${NC}\n"
      ln -sf "$_py" /usr/local/bin/python3 2>/dev/null || printf "  ${YELLOW}Symlink failed, create manually${NC}\n"
    fi
  else
    printf "  ${RED}✗ Python not found!${NC}\n"
    if [ "$OS" = "openbsd" ]; then
      printf "  Install: doas pkg_add python\n"
    else
      printf "  Install: apt install python3 / yum install python3\n"
    fi
    if ! prompt_yes "Continue anyway?"; then
      exit 1
    fi
  fi
}

setup_app_user() {
  printf "\n${BOLD}App user (${APP_USER})...${NC}\n"
  if id "$APP_USER" >/dev/null 2>&1; then
    printf "  ${GREEN}✓${NC} User %s exists\n" "$APP_USER"
    return
  fi
  printf "  ${YELLOW}User %s not found.${NC}\n" "$APP_USER"
  if prompt_yes "Create ${APP_USER} user?"; then
    if [ "$OS" = "openbsd" ]; then
      useradd -m "$APP_USER" && printf "  ${GREEN}✓${NC} Created\n" || printf "  ${RED}✗${NC} Failed\n"
    else
      useradd -m -s /usr/sbin/nologin "$APP_USER" 2>/dev/null || useradd -m "$APP_USER" && printf "  ${GREEN}✓${NC} Created\n" || printf "  ${RED}✗${NC} Failed\n"
    fi
  else
    printf "  ${YELLOW}Skipped. Create manually: useradd -m %s${NC}\n" "$APP_USER"
  fi
}

show_creds() {
  if [ -f "$CONFIG_PATH" ]; then
    _rp=$(python3 -c "
import json
with open('$CONFIG_PATH') as f:
    c = json.load(f)
print(c.get('auth',{}).get('root_user','root'))
print(c.get('auth',{}).get('root_password','admin'))
" 2>/dev/null)
    _ru=$(echo "$_rp" | head -1)
    _rpw=$(echo "$_rp" | tail -1)
    printf "\n${CYAN}========================================${NC}\n"
    printf "  ${BOLD}OpenCasa is ready!${NC}\n"
    printf "  URL:      http://$(hostname)/\n"
    printf "  User:     ${BOLD}%s${NC}\n" "$_ru"
    printf "  Password: ${YELLOW}%s${NC}\n" "$_rpw"
    printf "${CYAN}========================================${NC}\n"
  fi
}

# ---- main ----
banner
pick_os
ensure_root
fetch_source
trap cleanup EXIT

show_summary
if ! prompt_yes "Proceed with installation?"; then
  printf "${YELLOW}Aborted.${NC}\n"
  exit 0
fi

check_python
install_files
setup_config
setup_app_user
setup_service
show_creds
