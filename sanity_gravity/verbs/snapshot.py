"""``snapshot`` verb: ``docker commit`` a running container to a new image tag.

The phase loop ``snapshot.plan → snapshot.docker → snapshot.done`` is
published by :class:`Orchestrator`; per-phase behaviour lives in
:mod:`snapshot_hooks`.
"""
from __future__ import annotations

import sys

from sanity_gravity.cli.io import get_reporter
from sanity_gravity.core.eventbus import EventBus
from sanity_gravity.core.orchestrator import (
    Orchestrator,
    SnapshotContext,
    _SNAPSHOT_PHASES,
)
from sanity_gravity.effects.actions import ActionFailedError
from sanity_gravity.effects.executor import build_default_executor
from sanity_gravity.hooks.snapshot import register_builtin_snapshot_hooks


def snapshot_cmd(args):
    """Snapshot a running container to a new image (kernel-driven)."""
    reporter = getattr(args, "reporter", None) or get_reporter()
    ctx = SnapshotContext(
        project=args.name,
        target_tag=args.tag,
        variant=args.variant,
        reporter=reporter,
        dry_run=bool(getattr(args, "dry_run", False)),
    )

    bus = EventBus()
    register_builtin_snapshot_hooks(bus)
    executor = build_default_executor(reporter, dry_run=ctx.dry_run)

    try:
        try:
            Orchestrator(bus, reporter, executor=executor).run(_SNAPSHOT_PHASES, ctx)
        except ActionFailedError as e:
            sys.exit(e.result.exit_code or 1)
    finally:
        executor.close()


def explain_snapshot(args):
    """``explain snapshot`` alias: dry-run the plan without executing."""
    args.dry_run = True
    return snapshot_cmd(args)
