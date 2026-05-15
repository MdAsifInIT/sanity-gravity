"""``upgrade`` verb: migrate legacy containers to the managed-label model."""
from __future__ import annotations

import subprocess

from sanity_gravity.cli.colors import Colors
from sanity_gravity.cli.io import (
    get_uid_gid_user,
    print_error,
    print_header,
    print_info,
    print_plain,
    print_success,
    print_warning,
    run_command,
)
from sanity_gravity.cli.registry import VALID_TAGS
from sanity_gravity.core.command import CommandBuilder
from sanity_gravity.compose.generators import generate_git_compose
from sanity_gravity.verbs.lifecycle import (
    COMPOSE_FILE,
    get_active_projects,
    get_legacy_projects,
    get_managed_projects,
    get_project_env,
)
from sanity_gravity.verbs.up import is_port_in_use


def upgrade(args):
    """Upgrade legacy containers to managed containers."""
    import sys

    legacy = get_legacy_projects()

    target = getattr(args, "name", "sanity-gravity")
    if target != "sanity-gravity":
        if target in legacy:
            legacy = [target]
        else:
            print_error(f"Project '{target}' is not identified as a legacy container.")
            if legacy:
                print_plain(f"Detected legacy projects: {', '.join(legacy)}")
            return

    if not legacy:
        print_success("All system components are up to date.")
        return

    print_header("Found Legacy Containers")
    for p in legacy:
        print_plain(f" - {p}")

    print_plain(
        f"\n{Colors.WARNING}This will recreate the containers to apply new "
        f"management labels.{Colors.ENDC}"
    )
    print_plain(
        "Data in volumes will be preserved, but running processes will be "
        "interrupted."
    )

    if sys.stdin.isatty():
        choice = input(
            f"{Colors.BOLD}Proceed with upgrade? [y/N]: {Colors.ENDC}"
        ).lower().strip()
        if choice != 'y':
            print_info("Upgrade cancelled.")
            return
    else:
        print_warning("Non-interactive mode: Auto-proceeding with upgrade.")

    host_uid, host_gid, host_user = get_uid_gid_user()

    for p in legacy:
        try:
            print_info(f"Upgrading {p}...")

            cmd = (
                "docker", "ps", "-a",
                "--filter", f"label=com.docker.compose.project={p}",
                "--format", '{{.Label "com.docker.compose.service"}}',
            )
            services_out = run_command(cmd, capture=True, check=False)
            if not services_out:
                print_error(f"Could not determine services for {p}. Skipping.")
                continue

            services = set(services_out.splitlines())

            env_vars = get_project_env(p)

            if "HOST_USER" not in env_vars:
                env_vars["HOST_USER"] = host_user
            if "HOST_UID" not in env_vars:
                env_vars["HOST_UID"] = str(host_uid)
            if "HOST_GID" not in env_vars:
                env_vars["HOST_GID"] = str(host_gid)

            username = env_vars["HOST_USER"]

            if "SSH_HOST_PORT" not in env_vars:
                if p != "sanity-gravity" or is_port_in_use(2222):
                    env_vars["SSH_HOST_PORT"] = "0"

            if "KASM_PORT" not in env_vars:
                if p != "sanity-gravity" or is_port_in_use(8444):
                    env_vars["KASM_PORT"] = "0"

            if "VNC_PORT" not in env_vars:
                if p != "sanity-gravity" or is_port_in_use(5901):
                    env_vars["VNC_PORT"] = "0"

            if "NOVNC_PORT" not in env_vars:
                if p != "sanity-gravity" or is_port_in_use(6901):
                    env_vars["NOVNC_PORT"] = "0"

            for s in services:
                if s in VALID_TAGS:
                    print_info(f"Recreating {p} ({s})...")

                    container_name = f"{p}-{s}-1"

                    compose_files = [COMPOSE_FILE]

                    git_compose = generate_git_compose(username)
                    if git_compose:
                        compose_files.append(git_compose)

                    try:
                        cmd_find = (
                            "docker", "ps", "-a", "-q",
                            "--filter", f"label=com.docker.compose.project={p}",
                            "--filter", f"label=com.docker.compose.service={s}",
                        )
                        cid = run_command(cmd_find, capture=True, check=False)
                        if cid:
                            run_command(("docker", "rm", "-f", cid), check=False)
                    except subprocess.CalledProcessError:
                        pass

                    cb = CommandBuilder("docker", "compose", "-p", p)
                    for cf in compose_files:
                        cb.opt("-f", cf)
                    cb.positional("up", "-d", "--force-recreate", s)
                    run_command(cb.build(), env=env_vars)
        except Exception as e:
            print_error(f"Failed to upgrade {p}: {e}")

    print_success("Upgrade complete.")
    # Late import to avoid circular dep with status module.
    from sanity_gravity.verbs.status import status
    status(args)
