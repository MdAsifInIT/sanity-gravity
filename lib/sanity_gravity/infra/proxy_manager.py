import os
import subprocess
import shutil
import time

class ProxyManager:
    """
    Manages the SSH Agent Proxy service.
    
    This class handles the creation, monitoring, and removal of a systemd user service
    that bridges the host's SSH Agent to a fixed path for container consumption.
    """
    def __init__(self):
        self.home = os.path.expanduser("~")
        self.gemini_dir = os.path.join(self.home, ".gemini")
        self.bridge_dir = os.path.join(self.gemini_dir, "bridge")
        self.socket_path = os.path.join(self.bridge_dir, "ssh.sock")
        self.service_name = "sanity-gravity-proxy"
        self.unit_file_path = os.path.join(self.home, ".config/systemd/user", f"{self.service_name}.service")

    def run_command(self, cmd, capture=False, check=True):
        # Argv list/tuple is preferred (shell=False). String form is supported
        # for back-compat but no callers in this module use it any more.
        use_shell = isinstance(cmd, str)
        if capture:
            result = subprocess.run(cmd, shell=use_shell, check=check, capture_output=True, text=True)
            return result.stdout.strip()

        if check:
            subprocess.check_call(cmd, shell=use_shell, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(cmd, shell=use_shell, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def check_prerequisites(self):
        """Checks if socat is installed."""
        if not shutil.which("socat"):
            return False
        return True

    def get_socket_path(self):
        """Returns the fixed socket path."""
        return self.socket_path

    def is_enabled(self):
        """Checks if the proxy service is set up (unit file exists and enabled)."""
        # Simple check: Is the service file there?
        if not os.path.exists(self.unit_file_path):
            return False
        
        # Check if enabled in systemd
        try:
            # shell=False is safer and cleaner
            out = self.run_command(["systemctl", "--user", "is-enabled", self.service_name], capture=True, check=False)
            return out == "enabled"
        except Exception:
            return False

    def get_status(self):
        """Returns status dict: active, socket_exists, agent_reachable, error"""
        status = {
            "setup": self.is_enabled(),
            "active": False,
            "socket_exists": os.path.exists(self.socket_path),
            "agent_reachable": False,
            "error": None
        }

        if status["setup"]:
            # Check Service Status
            try:
                out = self.run_command(["systemctl", "--user", "is-active", self.service_name], capture=True, check=False)
                status["active"] = (out == "active")
            except Exception:
                pass

        # Check Agent Reachability (if socket exists)
        if status["socket_exists"]:
            try:
                # Try to list keys via the bridge socket using specific environment
                env = os.environ.copy()
                env["SSH_AUTH_SOCK"] = self.socket_path
                
                # ssh-add -l returns:
                # 0: Success (Has keys)
                # 1: Success (No keys)
                # 2: Error (Connection Refused / File not found etc)
                
                # We use subprocess.run directly to avoid double execution
                # No need for shell=True here as we are calling a direct binary with env
                res = subprocess.run(
                    ["ssh-add", "-l"], 
                    env=env, 
                    capture_output=True, 
                    text=True, 
                    check=False
                )
                
                if res.returncode in [0, 1]:
                    status["agent_reachable"] = True
                else:
                    # Connection refused usually prints to stderr
                    err_msg = res.stderr.strip() or "Unknown error"
                    status["error"] = f"Agent unreachable (Code {res.returncode}): {err_msg}"
                    
            except Exception as e:
                status["error"] = f"Error verifying agent: {e}"
        
        return status

    def setup(self):
        """Sets up the systemd service."""
        if not self.check_prerequisites():
            raise RuntimeError("socat is not installed. Please install it (e.g. `sudo apt install socat`).")

        # 1. Prepare Directories
        # We need to remove the socket file if it exists (stale) to let socat create it
        if os.path.exists(self.socket_path):
            try:
                if os.path.isdir(self.socket_path):
                    shutil.rmtree(self.socket_path)
                else:
                    os.remove(self.socket_path)
            except Exception as e:
                # If we fail to remove it, it might be root owned (common Docker issue)
                if os.path.isdir(self.socket_path):
                    raise RuntimeError(
                        f"Conflict: '{self.socket_path}' is a directory and cannot be removed.\n"
                        f"This often happens when Docker automatically creates a directory for a missing volume source.\n"
                        f"Please run: sudo rm -rf {self.socket_path}"
                    ) from e
                pass
                
        os.makedirs(self.bridge_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.unit_file_path), exist_ok=True)

        # 2. Create Unit File
        # We rely on inherited environment for SSH_AUTH_SOCK
        # But to be safe, we import environment first?
        # No, better: The ExecStart runs in user session scope.
        # User session scope usually has the variable IF dbus-update-activation-environment ran.
        # If not, we are in trouble.
        # 
        # Robust Strategy: 
        # The service runs a shell script that finds the socket if env is missing?
        # Or we just assume standard desktop environment behavior.
        # 
        # Let's stick to standard approach: inherit env.
        # To ensure socat unlinks previous socket on start, we add `unlink-early`.
        
        socat_bin = shutil.which("socat")
        if not socat_bin:
             raise RuntimeError("socat not found in PATH")
             
        unit_content = f"""[Unit]
Description=SSH Agent Socket Proxy for Sanity Gravity
After=ssh-agent.service

[Service]
ExecStart=/bin/sh -c 'exec {socat_bin} UNIX-LISTEN:{self.socket_path},fork,unlink-early UNIX-CONNECT:$SSH_AUTH_SOCK'
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
"""
        with open(self.unit_file_path, "w") as f:
            f.write(unit_content)

        # 3. Reload and Enable
        # 3. Reload and Enable
        self.run_command(["systemctl", "--user", "daemon-reload"])
        self.run_command(["systemctl", "--user", "enable", self.service_name])
        self.run_command(["systemctl", "--user", "restart", self.service_name])
        
        # Verify and Wait for Socket
        for _ in range(10):
             if os.path.exists(self.get_socket_path()): return
             time.sleep(1)
        
        # If loop finishes, check if service is at least active
        if not self.get_status()["active"]:
             raise RuntimeError("Service failed to start. Check 'systemctl --user status sanity-gravity-proxy'")
        
        raise TimeoutError(f"Service is active but socket failed to appear at {self.get_socket_path()}")

    def remove(self):
        """Removes the systemd service."""
        # Stop and Disable
        if self.is_enabled():
            try:
                self.run_command(
                    ["systemctl", "--user", "disable", "--now", self.service_name],
                    check=False,
                )
            except Exception:
                pass
        
        # Remove Unit File
        # Remove Unit File
        if os.path.exists(self.unit_file_path):
            os.remove(self.unit_file_path)
            self.run_command(["systemctl", "--user", "daemon-reload"])
            
        # Clean Socket
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)
        # Wait for socket to be removed by socat or systemd
        for _ in range(10): # Changed from range(5) to range(10)
             if not os.path.exists(self.get_socket_path()): return
             time.sleep(1)
             
        # If the loop finishes, the socket still exists, so it failed to be removed.
        raise TimeoutError(f"Socket failed to be removed at {self.get_socket_path()}")
