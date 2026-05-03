"""Phase enum for the microkernel lifecycle.

Phase names are ``<verb>.<step>``. We use ``StrEnum`` (Python 3.11+) so
``Phase.UP_DOCKER == "up.docker"`` is a useful identity.

The :class:`Tag` value object lives next door in :mod:`.tags`.
"""
from __future__ import annotations

from enum import StrEnum


class Phase(StrEnum):
    """Lifecycle phases. Only ``up.*`` is wired in PR #4."""

    # up verb (active)
    UP_VALIDATE = "up.validate"
    UP_COMPOSE = "up.compose"
    UP_PORT_ALLOC = "up.port_alloc"
    UP_DOCKER = "up.docker"
    UP_PROVISION = "up.provision"
    UP_ANNOUNCE = "up.announce"

    # build verb (active in PR #7b)
    BUILD_PLAN = "build.plan"
    BUILD_LAYER = "build.layer"
    BUILD_DONE = "build.done"

    # lifecycle verbs share one phase sequence; the verb is carried on
    # ctx.action ("down"/"stop"/"start"/"restart"); clean is "down" with
    # extra_action_args. Phase names match the file naming
    # (hooks/lifecycle.py, verbs/lifecycle.py, test_lifecycle_kernel.py).
    LIFECYCLE_BEFORE = "lifecycle.before"
    LIFECYCLE_DOCKER = "lifecycle.docker"
    LIFECYCLE_AFTER = "lifecycle.after"

    # snapshot verb (active in PR #7b)
    SNAPSHOT_PLAN = "snapshot.plan"
    SNAPSHOT_DOCKER = "snapshot.docker"
    SNAPSHOT_DONE = "snapshot.done"
