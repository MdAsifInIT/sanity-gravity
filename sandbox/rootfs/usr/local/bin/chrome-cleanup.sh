#!/bin/bash
# chrome-cleanup.sh
# Shared cleanup logic for Chrome & Antigravity Agent to ensure Snapshot stability.

# 1. Standard Locks (Prevent "Profile in use")
rm -f "$CHROME_CONFIG/SingletonLock"
rm -f "$CHROME_CONFIG/SingletonSocket"
rm -f "$CHROME_CONFIG/SingletonCookie"

# 2. Crashpad & Session State (Prevent "Restore Session" bubble / Hangs)
rm -rf "$CHROME_CONFIG/Crashpad" 
rm -rf "$CHROME_CONFIG/Crash Reports"
rm -f "$CHROME_CONFIG/Last Version"

# 3. Antigravity Agent Profile (CRITICAL: Fixes Agent failure in Snapshots)
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

# 5. IPC & Shared Memory Debris in /tmp
find /tmp -name ".org.chromium.Chromium*" -user $USER -delete 2>/dev/null || true
