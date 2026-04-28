"""``snapshot`` verb: docker commit a running container to a new image tag."""
from __future__ import annotations

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
from sanity_gravity.verbs.lifecycle import get_active_projects


def snapshot_cmd(args):
    """Snapshot a running container to a new image."""
    project_name = args.name
    variant = args.variant
    tag = args.tag

    if project_name == "sanity-gravity":
        active = get_active_projects()
        if not active:
            print_error("No active projects found.")
            print("Tip: Use --name <project> to specify a project.")
            return
        if len(active) > 1:
            print_error(f"Multiple active projects found: {', '.join(active)}")
            print("Please specify a project with --name.")
            return
        project_name = active[0]

    container_id = None
    target_variant = None

    if variant:
        target_variant = variant
        container_name = f"{project_name}-{variant}-1"
        out = run_command(
            ("docker", "inspect", container_name), capture=True, check=False,
        )
        if out and out.strip() != "[]":
            container_id = container_name
        else:
            print_error(
                f"Container not found: {container_name}. Please ensure the "
                "environment is running or specify the correct --variant."
            )
            return
    else:
        found_variants = []
        for v in VALID_TAGS:
            cname = f"{project_name}-{v}-1"
            out = run_command(
                ("docker", "inspect", cname), capture=True, check=False,
            )
            if out and out.strip() != "[]":
                found_variants.append(v)

        if not found_variants:
            print_error(f"No containers found for project '{project_name}'.")
            print_info(
                "Tip: This project may not be running yet. "
                "Please run './sanity-cli up' first."
            )
            return
        elif len(found_variants) == 1:
            target_variant = found_variants[0]
            container_id = f"{project_name}-{target_variant}-1"
        else:
            print_info(
                f"Multiple running environments detected: {', '.join(found_variants)}"
            )
            if not sys.stdin.isatty():
                print_error(
                    "Non-interactive mode: please use --variant to "
                    "explicitly specify the environment to snapshot."
                )
                return

            print(f"{Colors.BOLD}Select the environment to snapshot:{Colors.ENDC}")
            for i, v in enumerate(found_variants):
                print(f"  [{i+1}] {v}")

            while True:
                choice = input(
                    f"{Colors.OKBLUE}Enter a number "
                    f"(1-{len(found_variants)}): {Colors.ENDC}"
                ).strip()
                if choice.isdigit() and 1 <= int(choice) <= len(found_variants):
                    target_variant = found_variants[int(choice)-1]
                    container_id = f"{project_name}-{target_variant}-1"
                    break
                print_warning("Invalid input, please try again.")

    print_header(f"Snapshotting {container_id} -> {tag}")

    try:
        run_command(("docker", "commit", container_id, tag))
        print_success(f"Snapshot created: {tag}")
        print(f"\n{Colors.OKBLUE}To use this snapshot:{Colors.ENDC}")
        print(f"  ./sanity-cli up -v {target_variant} --name new-env --image {tag}")

    except Exception as e:
        print_error(f"Snapshot failed: {e}")
