# Security Policy

Sanity Gravity is a local developer sandbox for running GUI Electron IDEs and agent workflows inside a Docker container. It is designed to reduce host blast radius, not to provide a hardened multi-tenant security boundary.

## Supported Configuration

The supported configuration is the compose setup in this repository:

- VNC bound to `${BIND_ADDR:-127.0.0.1}:${VNC_PORT:-8444}`.
- SSH bound to `${BIND_ADDR:-127.0.0.1}:${SSH_PORT:-2222}`.
- Workspace mounted only at `/home/developer/workspace`.
- Antigravity and Antigravity IDE launched inside the container.

The default `BIND_ADDR` fallback is localhost. LAN access is opt-in with `BIND_ADDR=0.0.0.0` plus Windows Firewall rules scoped to local subnet clients. For Tailscale-only access on Docker Desktop for Windows, the supported approach is to keep Docker localhost-bound and use explicit Windows portproxy/firewall rules for the Tailscale IP. Exposing VNC or SSH directly to the internet is outside the supported threat model.

## Intentional Risk Acceptance

The following are deliberate developer-ergonomics tradeoffs:

- Electron applications run with `--no-sandbox`.
- The `developer` user has passwordless `sudo`.
- SSH password authentication is enabled.
- The workspace bind mount gives container processes read/write access to that host directory.

Treat code running inside this container as able to fully control the container and the mounted workspace.

## Compensating Controls

The default runtime narrows the exposed surface where it can without breaking the development workflow:

- Ports are localhost-bound by default.
- LAN access can be enabled deliberately with `BIND_ADDR=0.0.0.0` and firewall rules scoped to `LocalSubnet`.
- Tailscale access can be added with host-level portproxy rules scoped to the Tailscale IP.
- Docker capabilities are dropped and only required capabilities are added back.
- `pids_limit` is set to reduce process-exhaustion impact.
- Linux core dumps are disabled in compose and PID 1 to prevent host-side WSL dump exhaustion from Electron/native crashes.
- Antigravity tarballs are fetched with retry/fail-fast behavior and SHA256 verification.
- DBus, SSH, and KasmVNC run under `supervisord`.
- Shutdown hooks attempt graceful Electron termination before Docker's final kill window.
- KasmVNC IP blacklisting is disabled because Docker NAT can blacklist legitimate local users; do not pair that setting with public port exposure.

## In Scope

Please report:

- Container escape or host privilege escalation from the default configuration.
- Accidental exposure of host files outside configured bind mounts.
- Runtime bugs that expose VNC or SSH beyond localhost in the default compose file.
- Credential handling bugs that leak `HOST_PASSWORD` or SSH keys.
- Shutdown/startup lifecycle bugs that corrupt mounted workspace data.

## Out Of Scope

The following are expected consequences of the documented threat model:

- Root access inside the container via passwordless `sudo`.
- Electron sandbox warnings or sandbox bypass inside the container.
- Destructive actions against `/home/developer/workspace`.
- Vulnerabilities caused by user-added broad bind mounts, public port mappings, or custom reverse proxies.
- Exposure caused by enabling LAN access on an untrusted network.
- Ubuntu package CVEs that do not change the host/container boundary.

## Reporting

Open a private security advisory if the hosting platform supports it, or contact the maintainer directly. Include:

- Steps to reproduce.
- Host OS and Docker version.
- Whether the default `docker-compose.yml` was modified.
- Impact on host files, host privileges, exposed ports, or credentials.
