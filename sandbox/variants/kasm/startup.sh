#!/bin/bash
set -e

# Ensure environment variables
# Ensure environment variables
export USER=${USER}
export HOME=${HOME}

# Cleanup locks
# Cleanup locks
rm -f /tmp/.X1-lock /tmp/.X11-unix/X1

# ------------------------------------------------------------------
# Chrome Cleanup Strategy (For Snapshot Support)
# ------------------------------------------------------------------
CHROME_CONFIG="$HOME/.config/google-chrome"

# 1. Standard Locks (Prevent "Profile in use")
rm -f "$CHROME_CONFIG/SingletonLock"
rm -f "$CHROME_CONFIG/SingletonSocket"
rm -f "$CHROME_CONFIG/SingletonCookie"

# 2. Crashpad & Session State (Prevent "Restore Session" bubble / Hangs)
# Snapshots capture these PID-specific files, confusing the new process.
rm -rf "$CHROME_CONFIG/Crashpad" 
rm -rf "$CHROME_CONFIG/Crash Reports"
rm -f "$CHROME_CONFIG/Last Version"  # Sometimes causes migration checks

# 3. Antigravity Agent Profile (CRITICAL: Fixes Agent failure in Snapshots)
# The Agent uses a separate profile which also gets locked/crashed.
AGENT_PROFILE="$HOME/.gemini/antigravity-browser-profile"
rm -f "$AGENT_PROFILE/SingletonLock"
rm -f "$AGENT_PROFILE/SingletonSocket"
rm -f "$AGENT_PROFILE/SingletonCookie"
rm -rf "$AGENT_PROFILE/Crashpad"
rm -rf "$AGENT_PROFILE/Crash Reports"

# 4. GPU/Shader Cache (Prevent Crashes on different HW)
rm -rf "$CHROME_CONFIG/ShaderCache"
rm -rf "$CHROME_CONFIG/GrShaderCache"
rm -rf "$CHROME_CONFIG/Default/GPUCache"

# 4. IPC & Shared Memory Debris in /tmp
# Remove temp files like .org.chromium.Chromium.* belonging to this user
find /tmp -name ".org.chromium.Chromium*" -user $USER -delete 2>/dev/null || true

# Setup VNC Directory
mkdir -p $HOME/.vnc

# Setup Password
# KasmVNC vncpasswd requires username and double entry
echo -e "${HOST_PASSWORD}\n${HOST_PASSWORD}\n" | vncpasswd -u $USER -w
# chmod 600 $HOME/.vnc/passwd

# Setup xstartup for XFCE4
cat > $HOME/.vnc/xstartup <<EOF
#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
exec startxfce4
EOF
chmod +x $HOME/.vnc/xstartup

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
