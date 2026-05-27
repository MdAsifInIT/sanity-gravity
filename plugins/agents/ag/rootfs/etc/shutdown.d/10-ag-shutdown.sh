#!/bin/bash

echo "[shutdown] Closing Antigravity gracefully..."
FOUND=0
for wid in $(su - "$USER_NAME" -c 'DISPLAY=:1 xdotool search --class Antigravity' 2>/dev/null); do
    NAME=$(su - "$USER_NAME" -c "DISPLAY=:1 xdotool getwindowname $wid" 2>/dev/null)
    case "$NAME" in
        *" - Antigravity"*|"Antigravity"|"Launchpad")
            su - "$USER_NAME" -c "DISPLAY=:1 xdotool key --window $wid ctrl+q" 2>/dev/null
            FOUND=1
            ;;
    esac
done

if [ "$FOUND" = 1 ]; then
    for i in $(seq 1 20); do
        pgrep -f antigravity-bin > /dev/null 2>&1 || break
        sleep 1
    done
    echo "[shutdown] Antigravity exited after ${i}s"
fi
