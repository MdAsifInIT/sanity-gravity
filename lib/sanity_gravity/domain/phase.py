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

    # forward-declared for future PRs (not yet on the kernel)
    BUILD_PLAN = "build.plan"
    BUILD_LAYER = "build.layer"
    BUILD_DONE = "build.done"
    DOWN_BEFORE = "down.before"
    DOWN_DOCKER = "down.docker"
    DOWN_AFTER = "down.after"
