#!/bin/bash
set -euo pipefail

# Validate that supervisor provided required environment
: "${USER:?ERROR: USER not set by supervisor}"
: "${HOME:?ERROR: HOME not set by supervisor}"
export USER HOME

# Generate SSL certificate if missing (moved from Dockerfile for per-container uniqueness)
if [ ! -f /etc/ssl/certs/ssl-cert-snakeoil.pem ]; then
    sudo make-ssl-cert generate-default-snakeoil --force-overwrite
fi

cleanup_x11_lock() {
    local lock_file="/tmp/.X1-lock"
    local socket_file="/tmp/.X11-unix/X1"
    local lock_pid=""

    if [ -f "$lock_file" ]; then
        lock_pid=$(tr -d '[:space:]' < "$lock_file" 2>/dev/null || true)
        if [[ "$lock_pid" =~ ^[0-9]+$ ]] && kill -0 "$lock_pid" 2>/dev/null; then
            echo "Refusing to remove live X11 lock $lock_file owned by PID $lock_pid" >&2
            exit 1
        fi
        rm -f -- "$lock_file"
    fi

    if [ -S "$socket_file" ] || [ -e "$socket_file" ]; then
        rm -f -- "$socket_file"
    fi
}

cleanup_x11_lock

# ------------------------------------------------------------------
# Chrome Cleanup Strategy (For Snapshot Support)
# ------------------------------------------------------------------
# Source the shared cleanup script
if [ -f "/usr/local/bin/chrome-cleanup.sh" ]; then
    source /usr/local/bin/chrome-cleanup.sh
else
    echo "Warning: chrome-cleanup.sh not found!"
fi

# Setup VNC Directory
mkdir -p "$HOME/.vnc"

# Docker NAT collapses browser clients to the bridge gateway IP, so Kasm's
# IP blacklist can lock out every browser session. SSH/VNC are localhost-bound
# by compose; keep password auth, but disable Kasm's per-IP blacklist here.
cat > "$HOME/.vnc/kasmvnc.yaml" <<EOF
security:
  brute_force_protection:
    blacklist_threshold: 0
    blacklist_timeout: 0
EOF

# Setup Password
# KasmVNC vncpasswd requires username and double entry
case "$HOST_PASSWORD" in
    *[$'\n\r':]*|"")
        echo "ERROR: invalid HOST_PASSWORD" >&2
        exit 1
        ;;
esac
printf '%s\n%s\n\n' "$HOST_PASSWORD" "$HOST_PASSWORD" | vncpasswd -u "$USER" -w
# chmod 600 "$HOME/.vnc/passwd"

# Setup xstartup for XFCE4
cat > "$HOME/.vnc/xstartup" <<EOF
#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
exec startxfce4
EOF
chmod +x "$HOME/.vnc/xstartup"

echo "Starting KasmVNC on port 8444..."
# Start KasmVNC
# -select-de xfce might be needed if xstartup isn't used, but xstartup is standard.
exec /usr/bin/vncserver :1 \
    -depth 24 \
    -geometry 1920x1080 \
    -websocketPort 8444 \
    -httpd /usr/share/kasmvnc/www \
    -select-de xfce \
    -fg
