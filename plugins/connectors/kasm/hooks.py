"""Optional plugin-side hooks for the KasmVNC connector.

Demonstrates the ``hooks.py`` extension point: when a plugin needs to
do something the manifest can't express, it drops a Python module here
and uses the ``@on(Phase.X)`` decorator from
:mod:`sanity_gravity.core.eventbus` to subscribe to a lifecycle phase.

Hooks receive the verb's mutable Context object (e.g. ``UpContext``
during ``up``). Filtering on ``ctx.tag.connector`` is the plugin's
responsibility — every connector's ``hooks.py`` runs against every up,
so a kasm-specific hook must guard its own tag.
"""
from __future__ import annotations

from sanity_gravity.core.eventbus import PRIORITY_BUILTIN_SECOND, on
from sanity_gravity.domain.phase import Phase


@on(Phase.UP_ANNOUNCE, priority=PRIORITY_BUILTIN_SECOND, name="kasm_security_tip")
def _kasm_security_tip(ctx) -> None:
    """Emit a follow-up info line after the standard AccessInfo block.

    Using ``PRIORITY_BUILTIN_SECOND`` (200) places this strictly after
    the builtin announce hook (``PRIORITY_BUILTIN_FIRST`` = 100), so the
    tip appears beneath the access details. Skipped on dry-run since no
    container actually started.
    """
    if getattr(ctx, "dry_run", False):
        return
    if ctx.tag.connector != "kasm":
        return
    ctx.reporter.info(
        "» Tip: KasmVNC password is sent in cleartext over the local "
        "socket; secure your host accordingly."
    )
