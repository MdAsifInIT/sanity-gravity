# Contributing to Sanity Gravity

Thanks for contributing. This repository is a compact Docker runtime, so changes should stay focused, reproducible, and easy to validate locally.

## Repository Scope

Sanity Gravity currently ships as:

- `Dockerfile`: Ubuntu 24.04 image, pinned Antigravity downloads, runtime packages, KasmVNC install, and executable permissions.
- `docker-compose.yml`: local container runtime, localhost port bindings, environment, capabilities, limits, and workspace mount.
- `rootfs/`: files copied directly into the image root.
- `rootfs/etc/entrypoint.d/`: startup hooks run before `supervisord`.
- `rootfs/etc/shutdown.d/`: graceful shutdown hooks run before supervisor termination.
- `rootfs/etc/supervisor/`: DBus, SSH, and KasmVNC process supervision.
- `rootfs/usr/local/bin/`: entrypoint, KasmVNC startup, cleanup helpers, and `gravity-cli`.
- `rootfs/usr/bin/`: browser wrapper.
- `scripts/create-wrappers.sh`: Antigravity and Antigravity IDE launcher wrapper generation.
- `workspace/`: default bind-mounted development workspace.

## Local Setup

Requirements:

- Docker
- Docker Compose v2

Create `.env`:

```env
HOST_PASSWORD=change-me
BIND_ADDR=127.0.0.1
VNC_PORT=8444
SSH_PORT=2222
SSH_PUBLIC_KEY=
```

Build and run:

```bash
docker compose up -d --build
```

## Validation Checklist

For runtime changes, validate the full lifecycle:

```bash
docker compose config
docker compose build
docker compose up -d --force-recreate
docker ps --filter name=antigravity-ide
```

Check browser desktop access:

```text
https://localhost:8444
```

Check SSH:

```bash
ssh developer@127.0.0.1 -p 2222
```

Check supervised processes:

```bash
docker exec antigravity-ide sh -lc 'ps -eo pid,ppid,user,stat,comm,args | sed -n "1,220p"'
```

Check Antigravity launchers:

```bash
docker exec antigravity-ide sh -lc 'readlink -f /usr/bin/antigravity; readlink -f /usr/bin/antigravity-ide'
docker exec antigravity-ide sh -lc 'DISPLAY=:1 XAUTHORITY=/home/developer/.Xauthority antigravity >/tmp/ag.out 2>/tmp/ag.err &'
docker exec antigravity-ide sh -lc 'DISPLAY=:1 XAUTHORITY=/home/developer/.Xauthority antigravity-ide >/tmp/agide.out 2>/tmp/agide.err &'
docker exec antigravity-ide sh -lc 'pgrep -af "antigravity|Antigravity" || true'
```

Check graceful shutdown:

```bash
docker compose stop
docker compose up -d
```

## Shell Guidelines

- Use Bash for runtime scripts when Bash features are needed.
- Prefer `set -euo pipefail` for new scripts.
- Quote variables unless word splitting is intentional.
- Use `printf` instead of `echo -e`.
- Validate required environment variables with clear errors.
- Make shutdown and cleanup hooks idempotent.
- Avoid blind deletion of lock files; prove they are stale first when practical.
- Keep hook execution bounded with timeouts when adding long-running work.

## Security Guidelines

This project intentionally keeps passwordless `sudo` and Electron `--no-sandbox` for developer ergonomics. Contributions should preserve that workflow while reducing accidental exposure:

- Keep VNC and SSH localhost-bound by default.
- For LAN testing, use `BIND_ADDR=0.0.0.0` and `scripts/setup-lan-firewall.ps1`; do not leave that mode enabled on untrusted networks.
- If remote testing is required on Docker Desktop for Windows, keep Docker localhost-bound and use `scripts/setup-tailscale-portproxy.ps1` from an elevated PowerShell session.
- Do not add broad capabilities unless there is a concrete runtime need.
- Do not expose secrets in logs.
- Do not weaken checksum verification for downloaded artifacts.
- Do not add public network listeners without documenting the threat model.

## Pull Requests

When opening a PR, include:

- What changed.
- Why it changed.
- How you tested build, VNC, SSH, Antigravity launch, and shutdown behavior.
- Any security tradeoff introduced or removed.
