#!/usr/bin/env bash
# Sets up the slicer server on a Debian/Ubuntu machine, the same way it was done by hand:
#   1. installs Python's venv tool
#   2. downloads OrcaSlicer (same version as the presets in orca-data were made with) and unpacks it
#   3. makes the venv and installs requirements.txt
#   4. test-slices models/cube.stl
#   5. installs and starts the systemd service "orca-slicer" (starts at boot, restarts if it crashes)
#
# Usage (run from anywhere, as your normal user, not root; it asks for sudo where needed):
#   bash setup.sh "http://localhost:5173,https://domain.com,https://www.domain.com"
# The argument is the comma-separated list of sites allowed to call the server (CORS), no spaces.
# Running it again is safe: finished steps are skipped, the service file is rewritten.

set -euo pipefail

ORCA_VERSION="2.5.1"
PORT="8000"
ALLOWED_ORIGINS="${1:-http://localhost:5173}"

SERVER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORCA_DIR="$HOME/orcaslicer-$ORCA_VERSION"
ORCA_PATH="$ORCA_DIR/AppRun"
SERVICE_FILE="/etc/systemd/system/orca-slicer.service"

if [ "$(id -u)" -eq 0 ]; then
    echo "Run this as your normal user, not with sudo: the server shouldn't run as root." >&2
    exit 1
fi

case "$(uname -m)" in
    x86_64)  ORCA_FILE="OrcaSlicer_Linux_AppImage_Ubuntu2404_V$ORCA_VERSION.AppImage" ;;
    aarch64) ORCA_FILE="OrcaSlicer_Linux_AppImage_Ubuntu2404_aarch64_V$ORCA_VERSION.AppImage" ;;
    *) echo "No OrcaSlicer download for this CPU ($(uname -m))." >&2; exit 1 ;;
esac
ORCA_URL="https://github.com/OrcaSlicer/OrcaSlicer/releases/download/v$ORCA_VERSION/$ORCA_FILE"

echo "== 1/5 System packages"
sudo apt-get update -qq
sudo apt-get install -y -qq python3-venv wget

echo "== 2/5 OrcaSlicer $ORCA_VERSION"
if [ -x "$ORCA_PATH" ]; then
    echo "already in $ORCA_DIR"
else
    # Unpacked instead of run as an AppImage, so it doesn't need FUSE
    TMP_DIR="$(mktemp -d)"
    wget -q --show-progress -O "$TMP_DIR/$ORCA_FILE" "$ORCA_URL"
    chmod +x "$TMP_DIR/$ORCA_FILE"
    (cd "$TMP_DIR" && "./$ORCA_FILE" --appimage-extract > /dev/null)
    mv "$TMP_DIR/squashfs-root" "$ORCA_DIR"
    rm -rf "$TMP_DIR"
    echo "unpacked to $ORCA_DIR"
fi

echo "== 3/5 Python packages"
# A venv copied over from Windows doesn't work on Linux: start fresh if there's no Linux one
[ -x "$SERVER_DIR/.venv/bin/python" ] || { rm -rf "$SERVER_DIR/.venv"; python3 -m venv "$SERVER_DIR/.venv"; }
"$SERVER_DIR/.venv/bin/pip" install -q -r "$SERVER_DIR/requirements.txt"

echo "== 4/5 Test slice (models/cube.stl, PLA 0.2 mm 20%)"
ORCA_PATH="$ORCA_PATH" "$SERVER_DIR/.venv/bin/python" "$SERVER_DIR/slice.py" -f PLA -l 0.2 -i 20 -m "$SERVER_DIR/models/cube.stl"

echo "== 5/5 Service"
sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Orca slicer server
After=network.target

[Service]
User=$USER
WorkingDirectory=$SERVER_DIR
Environment=ORCA_PATH=$ORCA_PATH
Environment=ALLOWED_ORIGINS=$ALLOWED_ORIGINS
ExecStart=$SERVER_DIR/.venv/bin/uvicorn main:app --host 0.0.0.0 --port $PORT
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable -q orca-slicer
sudo systemctl restart orca-slicer
sleep 2
systemctl --no-pager --lines=0 status orca-slicer

echo
echo "Done. The server listens on port $PORT, allowed sites: $ALLOWED_ORIGINS"
echo "Try http://$(hostname -I | awk '{print $1}'):$PORT/docs from another PC on the network."
