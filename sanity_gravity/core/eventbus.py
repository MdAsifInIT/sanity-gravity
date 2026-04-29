"""Typed pub/sub event bus with priority-ordered hooks.

Hooks subscribe to a :class:`Phase`, the orchestrator publishes phases in
order, and each hook receives a shared mutable context. Hooks are called
by ``priority`` (lower first), then registration order. If a hook raises,
the exception propagates: the orchestrator decides how to surface it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from sanity_gravity.domain.phase import Phase


HookFn = Callable[[Any], None]


@dataclass(frozen=True)
class Hook:
    """A single subscription. ``name`` is for debugging only."""

    phase: Phase
    fn: HookFn
    priority: int = 100
    name: str | None = None
    _seq: int = field(default=0, compare=False)


class EventBus:
    """Phase-keyed registry of hooks with priority dispatch."""

    def __init__(self) -> None:
        self._hooks: dict[Phase, list[Hook]] = {}
        self._counter: int = 0

    def subscribe(self, phase: Phase, fn: HookFn, *,
                  priority: int = 100, name: str | None = None) -> Hook:
        """Register ``fn`` to be called when ``phase`` is published."""
        self._counter += 1
        hook = Hook(phase=phase, fn=fn, priority=priority,
                    name=name or getattr(fn, "__name__", "<anon>"),
                    _seq=self._counter)
        self._hooks.setdefault(phase, []).append(hook)
        return hook

    def publish(self, phase: Phase, ctx: Any) -> None:
        """Dispatch ``ctx`` to every hook bound to ``phase`` in order."""
        for hook in self.hooks_for(phase):
            hook.fn(ctx)

    def hooks_for(self, phase: Phase) -> list[Hook]:
        """Return hooks for ``phase`` in dispatch order (sorted copy)."""
        hooks = self._hooks.get(phase, [])
        return sorted(hooks, key=lambda h: (h.priority, h._seq))

    def all_hooks(self) -> list[Hook]:
        """Flat list of every subscribed hook, in registration order."""
        out: list[Hook] = []
        for hooks in self._hooks.values():
            out.extend(hooks)
        out.sort(key=lambda h: h._seq)
        return out

    def merge_into(self, other: "EventBus") -> None:
        """Re-subscribe every hook on ``self`` onto ``other``.

        Used to splice plugin-contributed hooks (registered against the
        module-level default bus via ``@on``) into a per-verb bus before
        the orchestrator runs.
        """
        for h in self.all_hooks():
            other.subscribe(h.phase, h.fn, priority=h.priority, name=h.name)

    def clear(self) -> None:
        """Drop every subscription. Test isolation only."""
        self._hooks.clear()
        self._counter = 0


_default_bus = EventBus()


def get_default_bus() -> EventBus:
    """Return the shared module-level bus (used by ``@on``)."""
    return _default_bus


def reset_default_bus() -> None:
    """Test helper: clear every ``@on``-registered hook on the default bus."""
    _default_bus.clear()


def on(phase: Phase, *, priority: int = 100, name: str | None = None):
    """Decorator: register against the module-level default bus.

    Plugin ``hooks.py`` modules use this to subscribe to lifecycle phases.
    The registry's ``hooks.py`` loader runs each plugin's module once at
    startup, after which each verb's ``register_builtin_*_hooks`` splices
    the default bus's accumulated subscriptions onto its own per-run bus.
    """
    def decorator(fn: HookFn) -> HookFn:
        _default_bus.subscribe(phase, fn, priority=priority, name=name)
        return fn
    return decorator
