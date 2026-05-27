#!/bin/bash

# Cleanup Stale Antigravity Runtime Locks (Safely)
# Instead of deleting entire directories (which breaks TLS/CSRF states),
# we only remove the actual Singleton locks that prevent startup.
echo "Cleaning up stale Antigravity/Chrome locks..."
find /home/"$USER_NAME"/.config/Antigravity -name "Singleton*" -delete 2>/dev/null || true
find /home/"$USER_NAME"/.gemini/antigravity-browser-profile -name "Singleton*" -delete 2>/dev/null || true

# Fix Chrome symlink for ARM64 (Chromium compatibility)
if [ ! -f "/opt/google/chrome/google-chrome" ]; then
    mkdir -p /opt/google/chrome
    ln -sf /usr/bin/google-chrome /opt/google/chrome/google-chrome
fi
