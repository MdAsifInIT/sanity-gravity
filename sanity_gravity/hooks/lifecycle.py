"""Builtin hooks for lifecycle verbs (``down``, ``stop``, ``start``,
``restart``, ``clean``).

Phase split:
- ``DOWN_BEFORE`` — for ``down``: verify the project exists; for ``clean``:
  prompt for confirmation. Always: resolve compose files + recover env.
- ``DOWN_DOCKER`` — enqueue the ``docker compose <action>`` Action.
- ``DOWN_AFTER`` — emit the success message keyed off the action verb.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from sanity_gravity.cli.colors import Colors
from sanity_gravity.core.command import CommandBuilder
from sanity_gravity.core.eventbus import EventBus, get_default_bus
from sanity_gravity.domain.phase import Phase
from sanity_gravity.effects.actions import RunSubprocess


COMPOSE_FILE = "docker-compose.yml"


def _project_compose_files() -> list[str]:
    """Find the compose files for a project (config/ first, legacy fallback)."""
    config_dir = "config"
    out: list[str] = []
    if os.path.exists(config_dir):
        for f in os.listdir(config_dir):
            if (
                f.startswith("docker-compose.")
                and f.endswith(".yml")
                and not f.endswith(".git.yml")
                and not f.endswith(".resources.yml")
            ):
                out.append(os.path.join(config_dir, f))
    if not out:
        out = [COMPOSE_FILE]
    return out


def lifecycle_check_existence(ctx) -> None:
    """DOWN_BEFORE/100: ``down`` only — bail if project missing."""
    if not ctx.check_existence:
        return

    # Local import to avoid module-level cycle (lifecycle.py imports this).
    from sanity_gravity.verbs.lifecycle import get_active_projects

    active = get_active_projects()
    if ctx.project not in active:
        ctx.reporter.warning(f"Project '{ctx.project}' not found.")
        if active:
            print(f"Active projects: {', '.join(active)}")
            print(
                f"{Colors.OKBLUE}Tip: Use --name <project> to specify a project.{Colors.ENDC}"
            )
        else:
            print("No active Sanity-Gravity projects found.")
        ctx.project_exists = False


def lifecycle_clean_prompt(ctx) -> None:
    """DOWN_BEFORE/50: ``clean`` only — interactive confirmation."""
    # CleanContext has a `force` attribute; plain DownContext does not.
    if not hasattr(ctx, "force"):
        return
    if ctx.force:
        return
    print(
        f"{Colors.WARNING}CAUTION: This will destroy ALL data in volumes "
        f"for project '{ctx.project}'.{Colors.ENDC}"
    )
    if sys.stdin.isatty():
        choice = input(
            f"{Colors.BOLD}Proceed with deep clean? [y/N]: {Colors.ENDC}"
        ).lower().strip()
        if choice != "y":
            ctx.reporter.info("Cleanup cancelled.")
            ctx.cancelled = True


def lifecycle_resolve_compose(ctx) -> None:
    """DOWN_BEFORE/200: populate ctx.compose_files."""
    if getattr(ctx, "project_exists", True) is False:
        return
    if getattr(ctx, "cancelled", False):
        return
    ctx.compose_files = [Path(p) for p in _project_compose_files()]


def lifecycle_recover_env(ctx) -> None:
    """DOWN_BEFORE/300: recover environment from a running container."""
    if getattr(ctx, "project_exists", True) is False:
        return
    if getattr(ctx, "cancelled", False):
        return
    if ctx.dry_run:
        return  # nothing to inspect in dry-run

    from sanity_gravity.verbs.lifecycle import get_project_env

    ctx.env = get_project_env(ctx.project) or {}


def _emit_header(ctx) -> None:
    label = ctx.action.capitalize()
    if ctx.action == "down" and ctx.extra_action_args:
        label = "Deep Cleaning"
    ctx.reporter.header(f"{label}{'ing' if not label.endswith('ing') else ''} Sandbox ({ctx.project})")


def lifecycle_compose_action(ctx) -> None:
    """DOWN_DOCKER/100: enqueue ``docker compose -p <name> -f ... <action>``."""
    if getattr(ctx, "project_exists", True) is False:
        return
    if getattr(ctx, "cancelled", False):
        return

    # Header line: print before enqueueing, so it precedes the action's
    # 'would-execute' / 'started' line in the output.
    label_word = "Cleaning" if ctx.extra_action_args else (
        "Stopping" if ctx.action == "stop" else
        "Starting" if ctx.action == "start" else
        "Restarting" if ctx.action == "restart" else
        "Removing"
    )
    if ctx.extra_action_args:
        ctx.reporter.header(f"Deep Cleaning Sandbox ({ctx.project})")
    else:
        ctx.reporter.header(f"{label_word} Sandbox ({ctx.project})")

    cb = CommandBuilder("docker", "compose", "-p", ctx.project)
    for cf in ctx.compose_files:
        cb.opt("-f", str(cf))
    cb.positional(ctx.action, *ctx.extra_action_args)
    ctx.actions.append(RunSubprocess(argv=cb.build(), env=dict(ctx.env) or None))


def lifecycle_announce(ctx) -> None:
    """DOWN_AFTER/100: success message keyed on action verb."""
    if getattr(ctx, "project_exists", True) is False:
        return
    if getattr(ctx, "cancelled", False):
        return
    if ctx.dry_run:
        # Skip success claim in dry-run; the WouldExecute lines speak for themselves.
        return
    if ctx.extra_action_args:
        ctx.reporter.success("Deep cleanup complete.")
        return
    msgs = {
        "down": "All containers removed.",
        "stop": "Containers stopped (data preserved).",
        "start": "Containers started.",
        "restart": "Containers restarted.",
    }
    msg = msgs.get(ctx.action)
    if msg:
        ctx.reporter.success(msg)


def register_builtin_lifecycle_hooks(bus: EventBus) -> None:
    """Subscribe lifecycle hooks. Same hooks serve down/stop/start/restart/clean.

    The ``clean`` prompt is also registered here at priority 50 (before
    the existence check) — it short-circuits via ``ctx.cancelled``.
    """
    from sanity_gravity.plugins.registry import default_registry
    default_registry()  # ensure plugin hooks.py modules are loaded

    bus.subscribe(Phase.DOWN_BEFORE, lifecycle_clean_prompt, priority=50)
    bus.subscribe(Phase.DOWN_BEFORE, lifecycle_check_existence, priority=100)
    bus.subscribe(Phase.DOWN_BEFORE, lifecycle_resolve_compose, priority=200)
    bus.subscribe(Phase.DOWN_BEFORE, lifecycle_recover_env, priority=300)
    bus.subscribe(Phase.DOWN_DOCKER, lifecycle_compose_action, priority=100)
    bus.subscribe(Phase.DOWN_AFTER, lifecycle_announce, priority=100)

    get_default_bus().merge_into(bus)
