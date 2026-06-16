# Sanity Gravity

Sanity Gravity builds a single Ubuntu 24.04 container that runs a full XFCE desktop, KasmVNC, SSH, Google Chrome/Chromium, Antigravity 2.0, and Antigravity IDE. The desktop runs entirely inside Docker and is accessed from the host through a browser.

The repository is intentionally small and direct: one `Dockerfile`, one `docker-compose.yml`, a `rootfs/` overlay, and shell scripts that own startup, shutdown, cleanup, and runtime hardening.

## What It Provides

- Browser-accessible Linux desktop at `https://localhost:8444`.
- SSH access at `127.0.0.1:2222`.
- Antigravity 2.0 and Antigravity IDE installed from pinned tarballs with SHA256 verification.
- XFCE4 desktop launched by KasmVNC under `supervisord`.
- Passwordless `sudo` for the developer user.
- Electron-compatible wrappers that force `--no-sandbox` inside the container.
- Graceful shutdown hooks for Antigravity/Electron processes.
- Local workspace bind mount at `/home/developer/workspace`.

## Requirements

- Docker
- Docker Compose v2

On Windows, Docker Desktop with the WSL2 backend is recommended.

## Configuration

Create or update `.env` before starting the container:

```env
HOST_PASSWORD=change-me
BIND_ADDR=127.0.0.1
VNC_PORT=8444
SSH_PORT=2222
SSH_PUBLIC_KEY=
```

`HOST_PASSWORD` is required. It is used for the Linux `developer` account, KasmVNC login, and SSH password login. The entrypoint rejects empty passwords and passwords containing newline, carriage return, or `:`.

`BIND_ADDR` is the network exposure toggle for Docker's published ports:

```env
BIND_ADDR=127.0.0.1
```

Use `127.0.0.1` for local-only access. Use `0.0.0.0` to allow access from other PCs on the local network, then add firewall rules scoped to local subnet clients:

```env
BIND_ADDR=0.0.0.0
```

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup-lan-firewall.ps1
```

For Tailscale-only access on Docker Desktop for Windows, keep Docker bound to localhost and add Windows portproxy listeners on the Tailscale IP:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup-tailscale-portproxy.ps1
```

Run the PowerShell helper scripts from an elevated PowerShell session. The Tailscale script forwards `100.x.y.z:8444` to `127.0.0.1:8444` and `100.x.y.z:2222` to `127.0.0.1:2222`, with firewall allow rules scoped to the Tailscale address range.

To enable key-based SSH, set `SSH_PUBLIC_KEY` to your public key line:

```env
SSH_PUBLIC_KEY=ssh-ed25519 AAAA... user@host
```

## Start

Build and run:

```bash
docker compose up -d --build
```

Or use the Makefile:

```bash
make start
```

Check status:

```bash
docker ps --filter name=antigravity-ide
docker compose logs -f
```

## Access

Open the desktop:

```text
https://localhost:8444
```

The certificate is self-signed, so the browser will show a certificate warning on first access.

Login:

- User: `developer`
- Password: value of `HOST_PASSWORD`

Connect over SSH:

```bash
ssh developer@127.0.0.1 -p 2222
```

If you changed `SSH_PORT`, use that port instead.

From another Tailscale device, use this host's Tailscale IP or MagicDNS name:

```bash
ssh developer@100.96.98.10 -p 2222
```

And open the desktop with:

```text
https://100.96.98.10:8444
```

From another PC on the same LAN, set `BIND_ADDR=0.0.0.0`, restart the container, run `scripts/setup-lan-firewall.ps1` as Administrator, then connect to this host's LAN IP:

```bash
ssh developer@<host-lan-ip> -p 2222
```

```text
https://<host-lan-ip>:8444
```

## Running Antigravity

Inside the XFCE desktop, launch:

- `Antigravity 2.0`
- `Antigravity IDE`

The desktop launchers call `/usr/bin/antigravity` and `/usr/bin/antigravity-ide`. Those are symlinks into `/opt/antigravity` and `/opt/antigravity-ide`; the generated wrappers resolve the real symlink target before starting the underlying Electron binary.

From an SSH shell, you can also start them in the active VNC display:

```bash
DISPLAY=:1 XAUTHORITY=/home/developer/.Xauthority antigravity
DISPLAY=:1 XAUTHORITY=/home/developer/.Xauthority antigravity-ide
```

## Workspace

The default compose file mounts:

```yaml
./workspace:/home/developer/workspace
```

Edit files on the host in `workspace/`, or change the bind mount to point at another local project directory.

Example:

```yaml
volumes:
  - C:\Users\you\Documents\Code:/home/developer/workspace
```

Restart after changing mounts:

```bash
docker compose down
docker compose up -d
```

## Runtime Lifecycle

Startup flow:

1. Docker starts `/usr/local/bin/entrypoint.sh` as PID 1.
2. The entrypoint creates or updates the `developer` user, password, sudoers entry, SSH key, runtime directories, and hook permissions.
3. Executable scripts in `/etc/entrypoint.d/` run before supervision starts.
4. `supervisord` starts DBus, SSH, and KasmVNC.
5. KasmVNC starts Xvnc and the XFCE session.

Shutdown flow:

1. PID 1 catches `TERM`/`INT`.
2. Executable scripts in `/etc/shutdown.d/` run with per-hook timeouts.
3. The Antigravity shutdown hook asks GUI windows to quit, waits briefly, then sends `TERM` to remaining Antigravity processes.
4. PID 1 forwards `TERM` to `supervisord`, which stops DBus, SSH, and KasmVNC as process groups.

## Security Model

This is a developer sandbox, not a hostile multi-tenant boundary.

Intentional tradeoffs:

- Electron runs with `--no-sandbox`.
- The `developer` user has passwordless `sudo`.
- SSH password login is enabled for local developer convenience.

Compensating controls:

- VNC and SSH are bound to `127.0.0.1` by default.
- LAN access is opt-in with `BIND_ADDR=0.0.0.0` and Windows Firewall rules scoped to local subnet clients.
- Tailscale-only access on Windows is provided by explicit portproxy and firewall rules, not by broad Docker port exposure.
- Compose drops all Linux capabilities and adds back only the small set needed for this runtime.
- `pids_limit` is set to reduce fork-bomb blast radius.
- Antigravity downloads are checksum-verified at build time.
- KasmVNC brute-force IP blacklisting is disabled because Docker NAT can collapse clients to the same bridge IP and lock out legitimate local sessions. Keep the service localhost-bound unless you add a stronger external access layer.

Do not expose `8444` or `22` directly to the internet. LAN access is intentionally broader than localhost, so use a strong `HOST_PASSWORD`, prefer SSH keys, and keep the firewall scoped to `LocalSubnet`.

## Troubleshooting

Kasm page loads but says it cannot connect:

```bash
docker exec antigravity-ide sh -lc 'tail -n 120 /var/log/kasmvnc.err; tail -n 120 /home/developer/.vnc/*.log'
```

Verify websocket access:

```bash
docker ps --filter name=antigravity-ide
```

Antigravity does not launch:

```bash
docker exec antigravity-ide sh -lc 'readlink -f /usr/bin/antigravity; readlink -f /usr/bin/antigravity-ide'
docker exec antigravity-ide sh -lc 'pgrep -af "antigravity|Antigravity" || true'
```

SSH does not connect:

```bash
docker ps --filter name=antigravity-ide
docker exec antigravity-ide sh -lc 'ps -ef | grep "[s]shd"; netstat -ltnp | grep ":22 " || true'
```

Tailscale forwarding does not connect:

```powershell
netsh interface portproxy show v4tov4
Get-NetFirewallRule -DisplayName "Sanity Gravity *"
Test-NetConnection -ComputerName 100.96.98.10 -Port 8444
Test-NetConnection -ComputerName 100.96.98.10 -Port 2222
```

LAN access does not connect:

```powershell
Get-NetFirewallRule -DisplayName "Sanity Gravity *"
Test-NetConnection -ComputerName <host-lan-ip> -Port 8444
Test-NetConnection -ComputerName <host-lan-ip> -Port 2222
```

Reset the environment:

```bash
docker compose down
docker compose up -d --build
```

## Repository Layout

```text
Dockerfile                  Image build, pinned downloads, runtime packages
docker-compose.yml          Local runtime configuration and port bindings
rootfs/etc/entrypoint.d/    Startup hooks
rootfs/etc/shutdown.d/      Shutdown hooks
rootfs/etc/supervisor/      Supervisor configuration
rootfs/usr/local/bin/       Entrypoint, Kasm startup, cleanup, gravity-cli
rootfs/usr/bin/             Browser wrapper
scripts/create-wrappers.sh  Antigravity launcher/wrapper generation copied into image
scripts/*.ps1               Windows host networking helpers, excluded from image builds
workspace/                  Default host-mounted workspace
```
