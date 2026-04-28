"""Microkernel for the ``up`` lifecycle.

This module defines the context carried across phases and the kernel
that drives the phase loop. Hook implementations live in :mod:`up_hooks`
so this file stays a small, easily-audited piece of orchestration glue.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from sanity_gravity.effects.actions import Action
from sanity_gravity.core.eventbus import EventBus
from sanity_gravity.domain.phase import Phase
from sanity_gravity.domain.tags import Tag
# Re-export hook registration so callers have a single import surface.
from sanity_gravity.verbs.up_hooks import register_builtin_up_hooks  # noqa: F401


@dataclass
class PortRequest:
    """User's desired ports + whether each was passed explicitly on CLI."""

    ssh: str
    ssh_explicit: bool
    kasm: str
    kasm_explicit: bool
    vnc: str
    vnc_explicit: bool
    novnc: str
    novnc_explicit: bool


@dataclass
class Deps:
    """Injected helpers. Tests swap any of these for stubs."""

    validate_username: Callable[[str], str]
    validate_project_name: Callable[[str], str]
    generate_compose_for_tag: Callable[[str], tuple[str, str]]
    generate_git_compose: Callable[[str, str], str | None]
    generate_resource_compose: Callable[[str | None, str | None, str], str | None]
    sync_config: Callable[[str, str, str], None]
    is_port_in_use: Callable[[int], bool]
    run_command: Callable[..., Any]


@dataclass
class UpContext:
    """Mutable context carried across all up phases."""

    tag: Tag
    project: str
    host_user: str
    host_uid: int
    host_gid: int
    password: str
    workspace: Path
    image_override: str | None
    requested_ports: PortRequest
    deps: Deps
    reporter: Any  # lib.reporter.Reporter; left untyped to avoid cycle
    resolved_ports: dict[str, str] = field(default_factory=dict)
    compose_files: list[Path] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    extra_compose_overlays: list[Any] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    dry_run: bool = False

    def drain_actions(self) -> list[Action]:
        """Pop and return the queued actions, leaving the list empty.

        Called by :class:`UpOrchestrator` after each phase publish so the
        Executor runs them in order before the next phase begins.
        """
        out = list(self.actions)
        self.actions.clear()
        return out

    @property
    def service_name(self) -> str:
        return str(self.tag)

    @property
    def run_id(self) -> str:
        return getattr(self.reporter, "run_id", "")

    @property
    def container_name(self) -> str:
        return f"{self.project}-{self.service_name}-1"


_UP_PHASES: tuple[Phase, ...] = (
    Phase.UP_VALIDATE,
    Phase.UP_COMPOSE,
    Phase.UP_PORT_ALLOC,
    Phase.UP_DOCKER,
    Phase.UP_PROVISION,
    Phase.UP_ANNOUNCE,
)


class UpOrchestrator:
    """Drives the up-lifecycle phase loop.

    The orchestrator iterates :data:`_UP_PHASES` and publishes each
    phase, surfacing a subtle ``[up.*]`` tick line so users can see
    where a slow run is hung. After each phase's hooks fire, queued
    :class:`Action` instances are drained through ``executor`` (when
    provided) so side effects happen between phase boundaries.
    """

    def __init__(
        self,
        bus: EventBus,
        reporter: Any,
        executor: Any | None = None,
    ) -> None:
        self.bus = bus
        self.reporter = reporter
        self.executor = executor

    def run(self, ctx: UpContext) -> None:
        for phase in _UP_PHASES:
            self.reporter.info(f"[{phase.value}]")
            # Iterate hooks ourselves so the action queue can be drained
            # *between* hooks within the same phase. Without this, a
            # later hook (e.g. resolve_ephemeral, which reads docker
            # state back) would observe state from before the earlier
            # hook's enqueued actions ran.
            hooks = self.bus.hooks_for(phase) if hasattr(self.bus, "hooks_for") else None
            if hooks is None:
                self.bus.publish(phase, ctx)
            else:
                for hook in hooks:
                    hook.fn(ctx)
                    if self.executor is not None:
                        pending = ctx.drain_actions()
                        if pending:
                            self.executor.drain(pending, phase=phase)
            # Final drain in case actions accumulated without an executor
            # being attached, or the bus did not expose hooks_for.
            if self.executor is not None:
                pending = ctx.drain_actions()
                if pending:
                    self.executor.drain(pending, phase=phase)
