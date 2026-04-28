"""``check`` verb: prerequisite (Docker / Compose / daemon) checks."""
from __future__ import annotations

import shutil
import subprocess
import sys

from sanity_gravity.cli.io import (
    print_error,
    print_header,
    print_success,
    run_command,
)


def check_prereqs(args):
    """Check that Docker and Docker Compose are installed and reachable."""
    print_header("Checking Prerequisites")

    if shutil.which("docker"):
        print_success("Docker is installed")
    else:
        print_error("Docker is NOT installed. Please install Docker first.")
        sys.exit(1)

    try:
        run_command(("docker", "compose", "version"), capture=True)
        print_success("Docker Compose is installed")
    except (subprocess.CalledProcessError, FileNotFoundError, SystemExit) as e:
        print_error(f"Docker Compose is NOT installed or not accessible. ({e})")
        sys.exit(1)

    try:
        run_command(("docker", "info"), capture=True)
        print_success("Docker Daemon is running")
    except (subprocess.CalledProcessError, FileNotFoundError, SystemExit) as e:
        print_error(f"Docker Daemon is NOT running. Please start Docker. ({e})")
        sys.exit(1)
