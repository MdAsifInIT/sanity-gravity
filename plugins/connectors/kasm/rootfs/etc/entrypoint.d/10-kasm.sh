#!/bin/bash

# Add to ssl-cert group if exists (for KasmVNC)
if getent group ssl-cert >/dev/null; then
    usermod -aG ssl-cert "$USER_NAME"
fi
