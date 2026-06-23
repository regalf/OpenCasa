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
  printf "%s [Y/n] " "$1" >&2
  _py_ans="y"
  read _py_ans < /dev/tty 2>/dev/null || true
  case "$_py_ans" in
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
   █████   ██████   ███████  ██   ██   █████    █████    █████    █████
  ██   ██  ██   ██  ██       ███  ██  ██       ██   ██  ██       ██   ██
  ██   ██  ██████   ██████   ████ ██  ██       ███████   █████   ███████
  ██   ██  ██       ██       ██ ████  ██       ██   ██       ██  ██   ██
   █████   ██       ███████  ██  ███   █████   ██   ██   █████   ██   ██
EOF
  printf "\n  ${CYAN}OpenCasa${NC} — Server Management Panel\n\n"
}

INSTALL_EXAMPLES=""

show_summary() {
  _apps="${DEST_DIR}/apps/ (empty)"
  [ -n "$INSTALL_EXAMPLES" ] && _apps="${DEST_DIR}/apps/ (${INSTALL_EXAMPLES})"
  cat << EOF

${BOLD}Installation Summary${NC}
  OS:              ${OS}
  Destination:     ${DEST_DIR}
  Config:          ${CONFIG_PATH}
  App user:        ${APP_USER}
  Example apps:    ${INSTALL_EXAMPLES:-none}

Files to install:
  ${DEST_DIR}/webui.py
  ${DEST_DIR}/webui/*.py
  ${DEST_DIR}/index.html
  ${DEST_DIR}/style.css
  ${DEST_DIR}/app.js
  ${DEST_DIR}/favicon.svg
  ${DEST_DIR}/locales/
  ${_apps}
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

install_example_apps() {
  [ -z "$INSTALL_EXAMPLES" ] && return
  printf "\n${BOLD}Installing example apps...${NC}\n"
  _apps_src="$SRC_DIR/examples/apps"
  if [ -d "$_apps_src" ]; then
    for _app_dir in "$_apps_src"/*/; do
      _app_name=$(basename "$_app_dir")
      mkdir -p "$DEST_DIR/apps/$_app_name"
      cp -r "$_app_dir"* "$DEST_DIR/apps/$_app_name/"
      printf "  ${GREEN}✓${NC} apps/%s\n" "$_app_name"
    done
    chmod -R 755 "$DEST_DIR/apps"
  else
    printf "  ${YELLOW}No example apps found at %s${NC}\n" "$_apps_src"
  fi
}

setup_config() {
  if [ -f "$CONFIG_PATH" ]; then
    printf "\n${YELLOW}Config already exists at %s${NC}\n" "$CONFIG_PATH"
    prompt_yes "Overwrite?" || {
      printf "  ${YELLOW}Keeping existing config.${NC}\n"
      return
    }
  fi
  _jwt=$( (command -v openssl >/dev/null && openssl rand -hex 32) || (command -v python3 >/dev/null && python3 -c "import secrets; print(secrets.token_hex(32))") || echo "CHANGE-ME-$(date +%s)" )
  _tmpcf=$(mktemp /tmp/opencasa-conf-XXXXXX) 2>/dev/null || _tmpcf="$CONFIG_PATH"
  sed "s/JWT_SECRET_PLACEHOLDER/${_jwt}/" "$SRC_DIR/opencasa.json.example" > "$_tmpcf" 2>/dev/null || cp "$SRC_DIR/opencasa.json.example" "$_tmpcf"
  chmod 600 "$_tmpcf"
  [ "$_tmpcf" != "$CONFIG_PATH" ] && mv "$_tmpcf" "$CONFIG_PATH"
  printf "  ${GREEN}✓${NC} %s created\n" "$CONFIG_PATH"
}

setup_service() {
  printf "\n${BOLD}Setting up service...${NC}\n"
  if [ "$OS" = "openbsd" ]; then
    cp "$SRC_DIR/scripts/webui" /etc/rc.d/webui
    chmod 755 /etc/rc.d/webui
    rcctl enable webui
    printf "  ${GREEN}✓${NC} /etc/rc.d/webui (enabled)\n"
  else
    cp "$SRC_DIR/scripts/webui.service" /etc/systemd/system/webui.service
    chmod 644 /etc/systemd/system/webui.service
    systemctl daemon-reload
    systemctl enable webui
    printf "  ${GREEN}✓${NC} /etc/systemd/system/webui.service (enabled)\n"
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
  if ! id "$APP_USER" >/dev/null 2>&1; then
    printf "  ${YELLOW}User %s not found.${NC}\n" "$APP_USER"
    if prompt_yes "Create ${APP_USER} user?"; then
      if [ "$OS" = "openbsd" ]; then
        useradd -m "$APP_USER" || { printf "  ${RED}✗${NC} Failed\n"; return; }
      else
        useradd -m -s /usr/sbin/nologin "$APP_USER" 2>/dev/null || useradd -m "$APP_USER" || { printf "  ${RED}✗${NC} Failed\n"; return; }
      fi
      printf "  ${GREEN}✓${NC} Created\n"
    else
      printf "  ${YELLOW}Skipped. Create manually: useradd -m %s${NC}\n" "$APP_USER"
      return
    fi
  fi
  printf "  ${GREEN}✓${NC} User %s exists\n" "$APP_USER"
  if prompt_yes "Set a password for ${APP_USER}?"; then
    passwd "$APP_USER"
  fi
}

show_creds() {
  printf "\n${CYAN}========================================${NC}\n"
  printf "  ${BOLD}OpenCasa is ready!${NC}\n"
  printf "${YELLOW}"
  printf "  FIRST START (generates root password + master key):\n"
  printf "${NC}\n"
  printf "    ${BOLD}doas python3 /usr/local/webui/webui.py -c /etc/opencasa.json -d /usr/local/webui${NC}   (OpenBSD)\n    ${BOLD}sudo python3 /usr/local/webui/webui.py -c /etc/opencasa.json -d /usr/local/webui${NC}   (Linux)\n"
  printf "\n  Save the master key shown — if lost, the database is lost!\n"
  printf "\n${YELLOW}  Then stop it (Ctrl+C) and start the service:\n"
  printf "${NC}\n"
  if [ "$OS" = "openbsd" ]; then
    printf "    ${BOLD}rcctl start webui${NC}\n"
  else
    printf "    ${BOLD}systemctl start webui${NC}\n"
  fi
  printf "${CYAN}========================================${NC}\n"
}

# ---- main ----
banner
pick_os
ensure_root
fetch_source
trap cleanup EXIT

printf "\n${BOLD}Example apps${NC}\n"
printf "  OpenCasa ships with example apps (calendar, system monitor, hello-world, ...)\n"
if prompt_yes "Install example apps to ${DEST_DIR}/apps/?"; then
  INSTALL_EXAMPLES="yes"
fi

show_summary
if ! prompt_yes "Proceed with installation?"; then
  printf "${YELLOW}Aborted.${NC}\n"
  exit 0
fi

check_python
install_files
install_example_apps
setup_config
setup_app_user
setup_service
show_creds
