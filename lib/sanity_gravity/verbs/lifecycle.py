"""``down`` / ``stop`` / ``start`` / ``restart`` / ``clean`` verbs.

Plus the project-discovery helpers (managed/legacy/active project lists)
and ``get_project_env`` — shared with ``upgrade`` and ``sync_config``.
"""
from __future__ import annotations

import os
import subprocess
import sys

from sanity_gravity.cli.colors import Colors
from sanity_gravity.cli.io import (
    print_error,
    print_header,
    print_info,
    print_success,
    print_warning,
    run_command,
)
from sanity_gravity.cli.registry import VALID_TAGS
from sanity_gravity.core.command import CommandBuilder


COMPOSE_FILE = "docker-compose.yml"


def get_managed_projects():
    """Return projects managed by this tool (have the specific label)."""
    try:
        cmd = (
            "docker", "ps", "-a",
            "--filter", "label=sanity.gravity.managed=true",
            "--format", '{{.Label "com.docker.compose.project"}}',
        )
        output = run_command(cmd, capture=True, check=False)
        if not output:
            return []
        return sorted(list(set(output.splitlines())))
    except (subprocess.CalledProcessError, SystemExit) as e:
        print_warning(f"Could not list managed projects: {e}")
        return []


def get_legacy_projects():
    """Return projects that match our variants but lack the managed label."""
    try:
        cmd = (
            "docker", "ps", "-a",
            "--format",
            '{{.Label "com.docker.compose.project"}}|'
            '{{.Label "com.docker.compose.service"}}',
        )
        output = run_command(cmd, capture=True, check=False)

        candidates = set()
        if output:
            for line in output.splitlines():
                parts = line.split('|')
                if len(parts) == 2:
                    project, service = parts
                    if project and service in VALID_TAGS:
                        candidates.add(project)

        managed = set(get_managed_projects())
        return sorted(list(candidates - managed))
    except (subprocess.CalledProcessError, SystemExit) as e:
        print_warning(f"Could not list legacy projects: {e}")
        return []


def get_active_projects():
    """Return active Sanity-Gravity project names (Strict Mode)."""
    return get_managed_projects()


def get_project_env(project_name):
    """Retrieve environment variables from a running container of the project."""
    for service in VALID_TAGS:
        container_name = f"{project_name}-{service}-1"

        try:
            subprocess.check_call(
                ("docker", "inspect", container_name),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            continue

        try:
            out = run_command(
                ("docker", "inspect", "-f",
                 "{{range .Config.Env}}{{println .}}{{end}}",
                 container_name),
                capture=True, check=False,
            )
            if not out:
                continue

            env_map = {}
            for line in out.splitlines():
                if "=" in line:
                    key, val = line.split("=", 1)
                    if key in ["SSH_HOST_PORT", "KASM_PORT", "VNC_PORT",
                               "NOVNC_PORT", "HOST_UID", "HOST_GID",
                               "HOST_USER", "HOST_PASSWORD", "VNC_PW"]:
                        env_map[key] = val

            if env_map:
                return env_map
        except (subprocess.CalledProcessError, ValueError, SystemExit):
            continue

    return {}


def _project_compose_files():
    """Find the compose files for a project (config/ first, legacy fallback)."""
    config_dir = "config"
    compose_files = []
    if os.path.exists(config_dir):
        for f in os.listdir(config_dir):
            if (
                f.startswith("docker-compose.")
                and f.endswith(".yml")
                and not f.endswith(".git.yml")
                and not f.endswith(".resources.yml")
            ):
                compose_files.append(os.path.join(config_dir, f))

    if not compose_files:
        compose_files = [COMPOSE_FILE]
    return compose_files


def run_compose_cmd(args, action, check_existence=False):
    """Helper to run docker compose commands with recovered environment."""
    project_name = args.name

    if check_existence:
        active_projects = get_active_projects()
        if project_name not in active_projects:
            print_warning(f"Project '{project_name}' not found.")
            if active_projects:
                print(f"Active projects: {', '.join(active_projects)}")
                print(
                    f"{Colors.OKBLUE}Tip: Use --name <project> to specify a project.{Colors.ENDC}"
                )
            else:
                print("No active Sanity-Gravity projects found.")
            return

    env_map = get_project_env(project_name)

    print_header(f"{action.capitalize()}ing Sandbox ({project_name})")

    compose_files = _project_compose_files()
    cb = CommandBuilder("docker", "compose", "-p", project_name)
    for cf in compose_files:
        cb.opt("-f", cf)
    cb.positional(action)
    run_command(cb.build(), env=env_map)

    if action == "down":
        print_success("All containers removed.")
    elif action == "stop":
        print_success("Containers stopped (data preserved).")
    elif action == "start":
        print_success("Containers started.")
    elif action == "restart":
        print_success("Containers restarted.")


def down(args):
    """Stop and remove all sandbox containers (docker compose down)."""
    run_compose_cmd(args, "down", check_existence=True)


def stop(args):
    """Stop sandbox containers without removing them (docker compose stop)."""
    run_compose_cmd(args, "stop")


def start(args):
    """Start existing stopped containers (docker compose start)."""
    run_compose_cmd(args, "start")


def restart(args):
    """Restart sandbox containers (docker compose restart)."""
    run_compose_cmd(args, "restart")


def clean(args):
    """Deep cleanup: remove containers, volumes, local images and orphans."""
    project_name = args.name
    print_header(f"Deep Cleaning Sandbox ({project_name})")

    compose_files = _project_compose_files()
    cb = CommandBuilder("docker", "compose", "-p", project_name)
    for cf in compose_files:
        cb.opt("-f", cf)
    cb.positional("down", "-v", "--rmi", "local", "--remove-orphans")
    cmd = cb.build()

    if not args.force:
        print(
            f"{Colors.WARNING}CAUTION: This will destroy ALL data in volumes "
            f"for project '{project_name}'.{Colors.ENDC}"
        )
        if sys.stdin.isatty():
            choice = input(
                f"{Colors.BOLD}Proceed with deep clean? [y/N]: {Colors.ENDC}"
            ).lower().strip()
            if choice != 'y':
                print_info("Cleanup cancelled.")
                return

    run_command(cmd)
    print_success("Deep cleanup complete.")
