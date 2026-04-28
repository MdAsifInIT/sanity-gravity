"""Phase enum + Tag value object for the microkernel lifecycle.

Phase names are ``<verb>.<step>``. We use ``StrEnum`` (Python 3.11+) so
``Phase.UP_DOCKER == "up.docker"`` is a useful identity.
"""
from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True)
class Tag:
    """Parsed dimension tag (``agent``-``desktop``-``connector``)."""

    agent: str
    desktop: str
    connector: str

    @classmethod
    def parse(cls, s: str, parser=None) -> "Tag":
        """Parse ``s`` via ``parser`` (constraint-checked entry point)."""
        if parser is None:
            raise ValueError("Tag.parse requires a parser callable")
        agent, desktop, connector = parser(s)
        return cls(agent=agent, desktop=desktop, connector=connector)

    def __str__(self) -> str:
        return f"{self.agent}-{self.desktop}-{self.connector}"
