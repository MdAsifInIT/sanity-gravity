"""Tests for the lifecycle verbs' microkernel migration (PR #7b).

Covers down/stop/start/restart and clean. We patch ``get_active_projects``
and ``get_project_env`` so the tests don't touch docker.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "lib"))

from sanity_gravity.core.eventbus import EventBus  # noqa: E402
from sanity_gravity.core.orchestrator import (  # noqa: E402
    CleanContext,
    DownContext,
    Orchestrator,
    _DOWN_PHASES,
)
from sanity_gravity.core.reporter import Reporter  # noqa: E402
from sanity_gravity.domain.phase import Phase  # noqa: E402
from sanity_gravity.effects.actions import RunSubprocess  # noqa: E402
from sanity_gravity.verbs.lifecycle_hooks import (  # noqa: E402
    register_builtin_lifecycle_hooks,
)


def _reporter():
    return Reporter(sinks=[], run_id="test")


def _ctx(action="down", project="my-proj", **kw):
    kw.setdefault("dry_run", True)
    return DownContext(
        project=project, action=action, reporter=_reporter(), **kw,
    )


@pytest.fixture(autouse=True)
def _stub_lifecycle_helpers():
    """Stub the docker-touching helpers in lifecycle_hooks."""
    with patch(
        "sanity_gravity.verbs.lifecycle.get_active_projects",
        return_value=["my-proj"],
    ), patch(
        "sanity_gravity.verbs.lifecycle.get_project_env",
        return_value={"HOST_USER": "dev"},
    ), patch(
        "sanity_gravity.verbs.lifecycle_hooks._project_compose_files",
        return_value=["config/docker-compose.tag.yml"],
    ):
        yield


def test_down_phase_sequence_runs_in_order():
    bus = EventBus()
    fired: list[Phase] = []
    for ph in _DOWN_PHASES:
        bus.subscribe(ph, lambda ctx, p=ph: fired.append(p))
    ctx = _ctx()
    Orchestrator(bus, ctx.reporter).run(_DOWN_PHASES, ctx)
    assert fired == list(_DOWN_PHASES)


def test_down_enqueues_compose_down_action():
    bus = EventBus()
    register_builtin_lifecycle_hooks(bus)
    ctx = _ctx(action="down", check_existence=True)

    captured: list = []

    class _Exec:
        def drain(self, actions, phase=None):
            captured.extend(actions)

    Orchestrator(bus, ctx.reporter, executor=_Exec()).run(_DOWN_PHASES, ctx)
    assert len(captured) == 1
    a = captured[0]
    assert isinstance(a, RunSubprocess)
    assert a.argv[:4] == ("docker", "compose", "-p", "my-proj")
    assert a.argv[-1] == "down"


def test_stop_action_uses_stop_verb():
    bus = EventBus()
    register_builtin_lifecycle_hooks(bus)
    ctx = _ctx(action="stop")

    captured: list = []

    class _Exec:
        def drain(self, actions, phase=None):
            captured.extend(actions)

    Orchestrator(bus, ctx.reporter, executor=_Exec()).run(_DOWN_PHASES, ctx)
    assert captured[0].argv[-1] == "stop"


def test_down_with_check_existence_bails_when_project_missing():
    """``down -n nonexistent`` should not enqueue any docker action."""
    bus = EventBus()
    register_builtin_lifecycle_hooks(bus)
    ctx = _ctx(action="down", check_existence=True, project="does-not-exist")

    captured: list = []

    class _Exec:
        def drain(self, actions, phase=None):
            captured.extend(actions)

    Orchestrator(bus, ctx.reporter, executor=_Exec()).run(_DOWN_PHASES, ctx)
    assert captured == []


def test_clean_appends_extra_compose_args():
    bus = EventBus()
    register_builtin_lifecycle_hooks(bus)
    ctx = CleanContext(
        project="my-proj",
        action="down",
        reporter=_reporter(),
        check_existence=False,
        dry_run=True,
        extra_action_args=("-v", "--rmi", "local", "--remove-orphans"),
        force=True,
    )

    captured: list = []

    class _Exec:
        def drain(self, actions, phase=None):
            captured.extend(actions)

    Orchestrator(bus, ctx.reporter, executor=_Exec()).run(_DOWN_PHASES, ctx)
    assert len(captured) == 1
    argv = captured[0].argv
    # Tail must be: down -v --rmi local --remove-orphans
    assert argv[-5:] == ("down", "-v", "--rmi", "local", "--remove-orphans")


def test_clean_cancelled_when_user_says_no(monkeypatch):
    """The interactive prompt path should set ctx.cancelled and skip docker."""
    bus = EventBus()
    register_builtin_lifecycle_hooks(bus)
    # Pretend stdin is a TTY and user typed 'n'.
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *a, **kw: "n")

    ctx = CleanContext(
        project="my-proj",
        action="down",
        reporter=_reporter(),
        dry_run=True,
        extra_action_args=("-v", "--rmi", "local", "--remove-orphans"),
        force=False,
    )

    captured: list = []

    class _Exec:
        def drain(self, actions, phase=None):
            captured.extend(actions)

    Orchestrator(bus, ctx.reporter, executor=_Exec()).run(_DOWN_PHASES, ctx)
    assert ctx.cancelled is True
    assert captured == []
