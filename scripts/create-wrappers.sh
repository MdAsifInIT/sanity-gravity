#!/bin/bash
set -euo pipefail

# Sandbox Wrappers for Antigravity & IDE
for APP_DIR in /opt/antigravity /opt/antigravity-ide; do
    if [ ! -d "$APP_DIR" ]; then continue; fi

    # Find the main binary
    BIN=$(find "$APP_DIR" -maxdepth 1 -type f -executable -name "antigravity*" | head -n 1)
    if [ -n "$BIN" ]; then
        mv "$BIN" "${BIN}-bin"

        cat << 'EOF' > "$BIN"
#!/bin/bash
set -euo pipefail

export ELECTRON_DISABLE_SANDBOX=1

resolve_self() {
    local self="$0"
    local dir target

    while [ -L "$self" ]; do
        dir="$(cd -P "$(dirname "$self")" >/dev/null 2>&1 && pwd)"
        target="$(readlink "$self")"
        case "$target" in
            /*) self="$target" ;;
            *) self="$dir/$target" ;;
        esac
    done

    dir="$(cd -P "$(dirname "$self")" >/dev/null 2>&1 && pwd)"
    printf '%s/%s\n' "$dir" "$(basename "$self")"
}

SELF_PATH="$(resolve_self)"
APP_BIN="${SELF_PATH}-bin"

if [ ! -x "$APP_BIN" ]; then
    echo "ERROR: Antigravity runtime binary is missing or not executable: $APP_BIN" >&2
    exit 127
fi

IS_GUI_CHILD=0
for arg in "$@"; do
    if [[ "$arg" == --type=* ]]; then
        IS_GUI_CHILD=1
        break
    fi
done

IS_CLI=0
for arg in "$@"; do
    case "$arg" in
        *cli.js*) IS_CLI=1; break ;;
    esac
done

if [ "${ELECTRON_RUN_AS_NODE:-0}" = "1" ] && [ "$IS_GUI_CHILD" = "0" ] && [ "$IS_CLI" = "1" ]; then
    exec "$APP_BIN" "$@"
fi
unset ELECTRON_RUN_AS_NODE
exec "$APP_BIN" --no-sandbox --disable-dev-shm-usage --disable-zygote --disable-namespace-sandbox "$@"
EOF

        chmod +x "$BIN"
        cp "$BIN" "${BIN}-original"
        chmod +x "${BIN}-original"

        # Create symlink in /usr/bin
        if [[ "$APP_DIR" == *"-ide"* ]]; then
            ln -sf "$BIN" /usr/bin/antigravity-ide
        else
            ln -sf "$BIN" /usr/bin/antigravity
        fi
    fi
done

mkdir -p /usr/share/applications

cat << 'EOF' > /usr/share/applications/antigravity.desktop
[Desktop Entry]
Name=Antigravity 2.0
Exec=/usr/bin/antigravity --no-sandbox --start-maximized --force-device-scale-factor=0.8
Icon=code
Type=Application
Categories=Development;IDE;
EOF

cat << 'EOF' > /usr/share/applications/antigravity-ide.desktop
[Desktop Entry]
Name=Antigravity IDE
Exec=/usr/bin/antigravity-ide --no-sandbox --start-maximized --force-device-scale-factor=0.8
Icon=code
Type=Application
Categories=Development;IDE;
EOF
