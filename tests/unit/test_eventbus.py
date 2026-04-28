"""Tests for the EventBus + Phase pair introduced in PR #4.

The bus is the smallest piece of the microkernel; we cover:

- subscribe / publish round-trip,
- priority ordering with ties broken by registration order,
- multiple hooks per phase,
- the ``@on`` decorator landing on the module-level default bus,
- ``hooks_for`` returning a stable, sorted view useful for debugging.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the package importable the same way sanity-cli does.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from sanity_gravity.core.eventbus import EventBus, Hook, get_default_bus, on  # noqa: E402
from sanity_gravity.domain.phase import Phase  # noqa: E402
from sanity_gravity.domain.tags import Tag  # noqa: E402


def test_subscribe_and_publish_invokes_hook():
    bus = EventBus()
    seen = []
    bus.subscribe(Phase.UP_VALIDATE, lambda ctx: seen.append(("a", ctx)))
    bus.publish(Phase.UP_VALIDATE, "ctx")
    assert seen == [("a", "ctx")]


def test_publish_no_subscribers_is_noop():
    EventBus().publish(Phase.UP_DOCKER, object())  # must not raise


def test_priority_orders_lower_first():
    bus = EventBus()
    order = []
    bus.subscribe(Phase.UP_COMPOSE, lambda c: order.append("late"), priority=300)
    bus.subscribe(Phase.UP_COMPOSE, lambda c: order.append("early"), priority=100)
    bus.subscribe(Phase.UP_COMPOSE, lambda c: order.append("mid"), priority=200)
    bus.publish(Phase.UP_COMPOSE, None)
    assert order == ["early", "mid", "late"]


def test_equal_priority_preserves_registration_order():
    bus = EventBus()
    order = []
    for label in ("first", "second", "third"):
        bus.subscribe(Phase.UP_DOCKER, lambda c, l=label: order.append(l))
    bus.publish(Phase.UP_DOCKER, None)
    assert order == ["first", "second", "third"]


def test_multiple_hooks_per_phase_all_fire():
    bus = EventBus()
    counters = {"a": 0, "b": 0}
    bus.subscribe(Phase.UP_PROVISION, lambda c: counters.__setitem__("a", counters["a"] + 1))
    bus.subscribe(Phase.UP_PROVISION, lambda c: counters.__setitem__("b", counters["b"] + 1))
    bus.publish(Phase.UP_PROVISION, None)
    bus.publish(Phase.UP_PROVISION, None)
    assert counters == {"a": 2, "b": 2}


def test_hook_exception_propagates():
    bus = EventBus()

    def boom(ctx):
        raise RuntimeError("nope")

    bus.subscribe(Phase.UP_VALIDATE, boom)
    try:
        bus.publish(Phase.UP_VALIDATE, None)
    except RuntimeError as e:
        assert str(e) == "nope"
    else:  # pragma: no cover - guard
        raise AssertionError("expected RuntimeError to propagate")


def test_named_hook_recorded_for_introspection():
    bus = EventBus()

    def my_hook(ctx):
        pass

    h = bus.subscribe(Phase.UP_DOCKER, my_hook, name="custom-name")
    assert h.name == "custom-name"
    listed = bus.hooks_for(Phase.UP_DOCKER)
    assert listed == [h]
    # default name = fn.__name__
    h2 = bus.subscribe(Phase.UP_DOCKER, my_hook)
    assert h2.name == "my_hook"


def test_hooks_for_returns_sorted_copy():
    bus = EventBus()
    a = bus.subscribe(Phase.UP_ANNOUNCE, lambda c: None, priority=200)
    b = bus.subscribe(Phase.UP_ANNOUNCE, lambda c: None, priority=100)
    listed = bus.hooks_for(Phase.UP_ANNOUNCE)
    assert listed == [b, a]
    # mutating the returned list should not affect the bus's view
    listed.clear()
    assert bus.hooks_for(Phase.UP_ANNOUNCE) == [b, a]


def test_on_decorator_registers_on_default_bus():
    default = get_default_bus()
    before = len(default.hooks_for(Phase.UP_VALIDATE))

    @on(Phase.UP_VALIDATE, priority=42)
    def _decorated(ctx):
        pass

    after = default.hooks_for(Phase.UP_VALIDATE)
    assert len(after) == before + 1
    assert after[-1].priority == 42 or any(h.priority == 42 for h in after)


def test_phase_str_value_round_trip():
    # Phase is a StrEnum: its value is the string form.
    assert Phase.UP_DOCKER.value == "up.docker"
    assert str(Phase.UP_DOCKER) == "up.docker"


def test_tag_parse_round_trip():
    parsed = Tag.parse("ag-xfce-kasm", parser=lambda s: tuple(s.split("-")))
    assert parsed.agent == "ag"
    assert parsed.desktop == "xfce"
    assert parsed.connector == "kasm"
    assert str(parsed) == "ag-xfce-kasm"
