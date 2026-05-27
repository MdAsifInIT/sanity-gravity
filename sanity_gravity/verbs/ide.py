"""``ide`` verb: container-side IDE maintenance via gravity-cli."""
from __future__ import annotations

import os
import subprocess
import sys

from sanity_gravity.cli.io import (
    print_error,
    print_header,
    print_info,
    print_plain,
    run_command,
)
from sanity_gravity.cli.registry import VALID_TAGS
from sanity_gravity.verbs.lifecycle import get_active_projects


def ide_cmd(args):
    """Handle deep IDE maintenance inside the container (via gravity-cli)."""
    project_name = getattr(args, "name", "sanity-gravity")
    subcommand = args.ide_command

    active = get_active_projects()
    
    if getattr(args, "name", None) is None:
        if not active:
            print_error("No active managed projects found.")
            print_plain("Tip: Use --name <project> to specify a project.")
            return
        if len(active) > 1:
            print_error(f"Multiple active projects found: {', '.join(active)}")
            print_plain("Please specify a project with --name.")
            return
        project_name = active[0]
    else:
        project_name = args.name

    active = get_active_projects()
    if project_name not in active:
        print_error(f"Project '{project_name}' is not active or managed.")
        return

    target_variant = None
    container_name = None
    for v in VALID_TAGS:
        cname = f"{project_name}-{v}-1"
        try:
            out = run_command(
                ("docker", "inspect", "-f", "{{.State.Running}}", cname),
                capture=True, check=False,
            )
            if out == "true":
                target_variant = v
                container_name = cname
                break
        except subprocess.CalledProcessError:
            pass

    if not container_name:
        print_error(f"No running containers found for {project_name}.")
        return

    from sanity_gravity.cli.registry import get_registry
    registry = get_registry()
    agent_slug = target_variant.split("-")[0]
    agent_plugin = registry.agents.get(agent_slug)
    
    if not agent_plugin or "ide" not in agent_plugin.provides:
        print_error(f"Agent '{agent_slug}' does not provide an IDE capability.")
        print_error("IDE maintenance commands are not applicable.")
        return

    print_header(f"IDE Maintenance ({project_name})")
    print_info(f"Executing gravity-cli {subcommand} in {container_name}...")

    print_info(
        "Hot-injecting latest gravity-cli and chrome-cleanup for compatibility..."
    )
    # Resolve repo root: this file lives at sanity_gravity/verbs/ide.py,
    # so go three parents up to reach the repo root.
    base_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    cli_src = os.path.join(
        base_dir, "plugins", "agents", "ag", "rootfs", "usr", "local", "bin", "gravity-cli"
    )
    cleanup_src = os.path.join(
        base_dir, "plugins", "agents", "ag", "rootfs", "usr", "local", "bin", "chrome-cleanup.sh"
    )

    inject_cmd_1 = (
        "docker", "cp", cli_src,
        f"{container_name}:/usr/local/bin/gravity-cli",
    )
    inject_cmd_1_b = (
        "docker", "cp", cleanup_src,
        f"{container_name}:/usr/local/bin/chrome-cleanup.sh",
    )
    inject_cmd_2 = (
        "docker", "exec", "-u", "root", container_name,
        "chmod", "+x",
        "/usr/local/bin/gravity-cli", "/usr/local/bin/chrome-cleanup.sh",
    )

    try:
        subprocess.check_call(
            inject_cmd_1, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        subprocess.check_call(
            inject_cmd_1_b, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        subprocess.check_call(
            inject_cmd_2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError:
        print_error(
            "Failed to hot-inject gravity-cli. Container might be highly incompatible."
        )
        sys.exit(1)

    cmd = (
        "docker", "exec", "-it", "-u", "root", container_name,
        "/usr/local/bin/gravity-cli", "ide", subcommand,
    )
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        sys.exit(1)
