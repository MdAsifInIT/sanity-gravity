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
# STRATEGY CHANGE: We must fully destroy the profile to ensure a clean state.
# Partial cleanup (removing locks) proved insufficient.
AGENT_PROFILE="$HOME/.gemini/antigravity-browser-profile"
if [ -d "$AGENT_PROFILE" ]; then
    echo "$(date): [chrome-cleanup] Removing Agent Profile at $AGENT_PROFILE" >> /tmp/chrome-cleanup.log
    rm -rf "$AGENT_PROFILE"
else
    echo "$(date): [chrome-cleanup] No Agent Profile found at $AGENT_PROFILE" >> /tmp/chrome-cleanup.log
fi

# 4. GPU/Shader Cache (Prevent Crashes on different HW)
rm -rf "$CHROME_CONFIG/ShaderCache"
rm -rf "$CHROME_CONFIG/GrShaderCache"
rm -rf "$CHROME_CONFIG/Default/GPUCache"

# 5. IPC & Shared Memory Debris in /tmp
find /tmp -name ".org.chromium.Chromium*" -user $USER -delete 2>/dev/null || true

echo "$(date): [chrome-cleanup] Cleanup completed for user $USER" >> /tmp/chrome-cleanup.log
