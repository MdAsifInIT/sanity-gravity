# Default is unused; always overridden by --build-arg. Set to suppress Docker warning.
ARG BASE_IMAGE=ubuntu:24.04
FROM ${BASE_IMAGE}

# Codex CLI Agent Layer
# Installs the OpenAI Codex CLI via the official installer. Codex ships as a
# statically-linked musl binary (Rust), so no Node.js or extra runtime is
# pulled in. The installer auto-detects x86_64/aarch64, keeping the layer
# multi-arch; base already provides curl, tar, ca-certificates, and coreutils.
#
# The installer unpacks a versioned "standalone package" under $HOME/.codex and
# only drops a *symlink* into CODEX_INSTALL_DIR. Left at the default $HOME=/root
# (mode 700) that symlink dangles for the non-root sandbox user, so HOME is
# redirected to a world-readable /opt tree; CODEX_INSTALL_DIR then links the
# binary onto the global PATH. `chmod a+rX` makes the package dirs traversable
# for every user. Runtime config/auth still lands in the user's own ~/.codex.
RUN curl -fsSL https://chatgpt.com/codex/install.sh \
        | HOME=/opt/codex CODEX_INSTALL_DIR=/usr/local/bin sh && \
    chmod -R a+rX /opt/codex && \
    test -x /usr/local/bin/codex
