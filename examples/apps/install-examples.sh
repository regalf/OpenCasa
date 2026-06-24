#!/bin/sh
# Copy example apps to OpenCasa apps directory
# Run as root: sh install-examples.sh
APPS_DIR="${1:-/usr/local/webui/apps}"
echo "Installing example apps to $APPS_DIR"
for app in calendar hello-world disk-usage system-monitor hello-web whoami perm-test notify-test; do
    cp -r "$(dirname "$0")/$app" "$APPS_DIR/"
    echo "  installed $app"
done
echo "Done. Restart OpenCasa: rcctl restart webui"
