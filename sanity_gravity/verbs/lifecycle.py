"""``down`` / ``stop`` / ``start`` / ``restart`` / ``clean`` verbs.

The phase loop ``lifecycle.before → lifecycle.docker → lifecycle.after``
is published by :class:`Orchestrator`; per-phase behaviour lives in
:mod:`sanity_gravity.hooks.lifecycle`. ``clean`` reuses the same phase
sequence with a
``CleanContext`` that adds a ``[y/N]`` prompt + extra docker-compose
args (``-v --rmi local --remove-orphans``).

Plus the project-discovery helpers (managed/legacy/active project lists)
and ``get_project_env`` — shared with ``upgrade`` and ``sync_config``.
"""
from __future__ import annotations

import atexit
import subprocess

from sanity_gravity.cli.io import (
    get_reporter,
    print_warning,
    run_command,
)
from sanity_gravity.cli.registry import VALID_TAGS
from sanity_gravity.core.eventbus import EventBus
from sanity_gravity.core.orchestrator import (
    CleanContext,
    DownContext,
    Orchestrator,
    _LIFECYCLE_PHASES,
)
from sanity_gravity.effects.actions import ActionFailedError
from sanity_gravity.effects.executor import build_default_executor
from sanity_gravity.hooks.lifecycle import register_builtin_lifecycle_hooks


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


def _run_lifecycle(ctx) -> None:
    """Drive a DownContext / CleanContext through the kernel."""
    bus = EventBus()
    register_builtin_lifecycle_hooks(bus)
    executor = build_default_executor(ctx.reporter, dry_run=ctx.dry_run)
    atexit.register(executor.close)
    try:
        Orchestrator(bus, ctx.reporter, executor=executor).run(_LIFECYCLE_PHASES, ctx)
    except ActionFailedError as e:
        import sys as _sys
        _sys.exit(e.result.exit_code or 1)


def _make_down_ctx(args, action: str, *, check_existence: bool) -> DownContext:
    reporter = getattr(args, "reporter", None) or get_reporter()
    return DownContext(
        project=args.name,
        action=action,
        reporter=reporter,
        check_existence=check_existence,
        dry_run=bool(getattr(args, "dry_run", False)),
    )


def down(args):
    """Stop and remove all sandbox containers (docker compose down)."""
    _run_lifecycle(_make_down_ctx(args, "down", check_existence=True))


def stop(args):
    """Stop sandbox containers without removing them (docker compose stop)."""
    _run_lifecycle(_make_down_ctx(args, "stop", check_existence=False))


def start(args):
    """Start existing stopped containers (docker compose start)."""
    _run_lifecycle(_make_down_ctx(args, "start", check_existence=False))


def restart(args):
    """Restart sandbox containers (docker compose restart)."""
    _run_lifecycle(_make_down_ctx(args, "restart", check_existence=False))


def clean(args):
    """Deep cleanup: remove containers, volumes, local images and orphans."""
    reporter = getattr(args, "reporter", None) or get_reporter()
    ctx = CleanContext(
        project=args.name,
        action="down",
        reporter=reporter,
        check_existence=False,
        dry_run=bool(getattr(args, "dry_run", False)),
        extra_action_args=("-v", "--rmi", "local", "--remove-orphans"),
        force=bool(getattr(args, "force", False)),
    )
    _run_lifecycle(ctx)


# Explain aliases ------------------------------------------------------------

def explain_down(args):
    args.dry_run = True
    return down(args)


def explain_stop(args):
    args.dry_run = True
    return stop(args)


def explain_start(args):
    args.dry_run = True
    return start(args)


def explain_restart(args):
    args.dry_run = True
    return restart(args)


def explain_clean(args):
    args.dry_run = True
    return clean(args)
