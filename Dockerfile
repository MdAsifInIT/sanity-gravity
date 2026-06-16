# Pinned: ubuntu:24.04 as of 2026-03-30
# Stage 1: Downloader
FROM ubuntu:24.04@sha256:186072bba1b2f436cbb91ef2567abca677337cfc786c86e107d25b7072feef0c AS downloader

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates tar && rm -rf /var/lib/apt/lists/*

ARG AG_VERSION=2.1.4-6481382726303744
ARG AGIDE_VERSION=2.0.4-6381998290370560
ARG AG_SHA256=4ffb032a0410d22fe50cbdf66d72f5bd78bebef058229dc0524b4bdf069a659a
ARG AGIDE_SHA256=66337d45f2472ce5e89f394e77aec74909aa1be0bb33c9f73299a95f458e6770

RUN mkdir -p /opt/antigravity /opt/antigravity-ide && \
    curl -fL --retry 3 -o /tmp/antigravity.tar.gz \
      "https://storage.googleapis.com/antigravity-public/antigravity-hub/${AG_VERSION}/linux-x64/Antigravity.tar.gz" && \
    echo "${AG_SHA256}  /tmp/antigravity.tar.gz" | sha256sum -c - && \
    tar -xzf /tmp/antigravity.tar.gz -C /opt/antigravity --strip-components=1 && \
    curl -fL --retry 3 -o /tmp/antigravity-ide.tar.gz \
      "https://edgedl.me.gvt1.com/edgedl/release2/j0qc3/antigravity/stable/${AGIDE_VERSION}/linux-x64/Antigravity%20IDE.tar.gz" && \
    echo "${AGIDE_SHA256}  /tmp/antigravity-ide.tar.gz" | sha256sum -c - && \
    tar -xzf /tmp/antigravity-ide.tar.gz -C /opt/antigravity-ide --strip-components=1 && \
    rm -f /tmp/antigravity.tar.gz /tmp/antigravity-ide.tar.gz

# Stage 2: Runtime
FROM ubuntu:24.04@sha256:186072bba1b2f436cbb91ef2567abca677337cfc786c86e107d25b7072feef0c

ENV DEBIAN_FRONTEND=noninteractive
ENV LC_ALL=C.UTF-8

# Single consolidated package layer
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    supervisor sudo vim-tiny curl wget git zsh net-tools locales tzdata ca-certificates openssh-server \
    xfce4 xfce4-terminal xfce4-taskmanager xfce4-screenshooter xfce4-notifyd xfce4-clipman-plugin \
    xfce4-whiskermenu-plugin thunar-archive-plugin dbus dbus-x11 x11-utils x11-xserver-utils x11-apps \
    xdotool mesa-utils fonts-noto-cjk \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Setup Locales
RUN locale-gen en_US.UTF-8

# Setup SSH Config
RUN mkdir /var/run/sshd && \
    sed -i 's/^#*PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config && \
    sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config

# Architecture-Agnostic Browser Installation
RUN arch=$(dpkg --print-architecture); \
    if [ "$arch" = "amd64" ]; then \
        apt-get update && apt-get install -y --no-install-recommends gnupg && \
        mkdir -p /etc/apt/keyrings && \
        wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg && \
        echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
        apt-get update && apt-get install -y --no-install-recommends google-chrome-stable; \
    else \
        apt-get update && apt-get install -y --no-install-recommends software-properties-common && \
        add-apt-repository -y ppa:xtradeb/apps && \
        apt-get update && apt-get install -y --no-install-recommends chromium && \
        apt-get remove --purge -y software-properties-common && apt-get autoremove -y; \
        ln -sf /usr/bin/chromium /usr/bin/google-chrome && \
        ln -sf /usr/bin/chromium /usr/bin/google-chrome-stable; \
    fi && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy Unified Rootfs & Script Helpers (Including Chrome Wrapper)
COPY rootfs/ /
COPY scripts/create-wrappers.sh /tmp/scripts/create-wrappers.sh

# Universal Browser Wrapper Setup
RUN chmod +x /usr/bin/google-chrome-safe && \
    ln -sf /usr/bin/google-chrome-safe /usr/bin/google-chrome && \
    ln -sf /usr/bin/google-chrome-safe /usr/bin/google-chrome-stable && \
    ln -sf /usr/bin/google-chrome-safe /usr/bin/x-www-browser && \
    for f in /usr/share/applications/google-chrome.desktop /usr/share/applications/chromium-browser.desktop /usr/share/applications/chromium.desktop; do \
        if [ -f "$f" ]; then \
            sed -i 's|Exec=[^ ]*|Exec=/usr/bin/google-chrome|g' "$f"; \
        fi; \
    done

# Copy Antigravity & IDE from Downloader
COPY --from=downloader /opt/antigravity /opt/antigravity
COPY --from=downloader /opt/antigravity-ide /opt/antigravity-ide

# Setup Antigravity Wrappers
RUN chmod +x /tmp/scripts/create-wrappers.sh && \
    /tmp/scripts/create-wrappers.sh && \
    rm -rf /tmp/scripts

# Install KasmVNC
ENV KASM_VERSION=1.4.0
RUN arch=$(dpkg --print-architecture); \
    KASM_DEB="kasmvncserver_noble_${KASM_VERSION}_${arch}.deb" && \
    curl -L -O "https://github.com/kasmtech/KasmVNC/releases/download/v${KASM_VERSION}/${KASM_DEB}" && \
    if [ "$arch" = "amd64" ]; then \
        echo "12bac6014149c5fdee75f0d403785aaa3e5dd4ea222de73253a5d4181bc9567e  ${KASM_DEB}" | sha256sum -c -; \
    else \
        echo "120d9462cb5e917cad91a23f6cb0b780c06f701def40e900b29f996979200638  ${KASM_DEB}" | sha256sum -c -; \
    fi && \
    apt-get update && apt-get install -y "./${KASM_DEB}" ssl-cert && \
    rm "${KASM_DEB}" && \
    rm -f /etc/ssl/private/ssl-cert-snakeoil.key /etc/ssl/certs/ssl-cert-snakeoil.pem && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Final cleanup layer
RUN rm -rf /usr/share/doc/* /usr/share/info/* /usr/share/lintian/* /usr/share/man/* \
    /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Ensure executables
RUN mkdir -p /etc/entrypoint.d /etc/shutdown.d && \
    find /usr/local/bin /usr/bin /etc/entrypoint.d /etc/shutdown.d -type f \
      \( -name "*.sh" -o -name "gravity-cli" -o -name "google-chrome-safe" \) \
      -exec chmod 0755 {} \;

EXPOSE 8444
EXPOSE 22

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -k -s -o /dev/null -u "${USER_NAME:-developer}:${HOST_PASSWORD}" https://localhost:8444/ || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]
