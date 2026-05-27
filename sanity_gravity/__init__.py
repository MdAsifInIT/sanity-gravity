"""Sanity-Gravity: dimension-based AI sandbox CLI.

This package houses the CLI's logic; the ``sanity-cli`` script in the
repo root is a thin shim that injects ``lib/`` onto ``sys.path`` and
calls :func:`sanity_gravity.cli.main.main`.

A small public API is re-exported here for convenience.
"""
from __future__ import annotations

from sanity_gravity.domain.phase import Phase
from sanity_gravity.domain.tags import Tag

__all__ = ["Phase", "Tag"]
