"""Tests for ``verbs/lifecycle.py`` discovery helpers.

``get_managed_projects`` and ``get_legacy_projects`` shell out to
``docker ps``; on failure they should warn and degrade to an empty list,
not crash the verb that called them.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))


class TestGetManagedProjects:
    def test_returns_sorted_unique_projects(self):
        from sanity_gravity.verbs import lifecycle as lc

        with patch.object(lc, "run_command", return_value="b\na\nb\n"):
            assert lc.get_managed_projects() == ["a", "b"]

    def test_empty_output_returns_empty_list(self):
        from sanity_gravity.verbs import lifecycle as lc

        with patch.object(lc, "run_command", return_value=""):
            assert lc.get_managed_projects() == []

    def test_subprocess_error_warns_and_returns_empty(self):
        from sanity_gravity.verbs import lifecycle as lc

        with patch.object(lc, "run_command",
                          side_effect=subprocess.CalledProcessError(1, "docker ps")), \
             patch.object(lc, "print_warning") as warn:
            assert lc.get_managed_projects() == []
            warn.assert_called_once()
            assert "managed projects" in warn.call_args[0][0]

    def test_systemexit_from_run_command_warned_not_propagated(self):
        from sanity_gravity.verbs import lifecycle as lc

        with patch.object(lc, "run_command", side_effect=SystemExit(2)), \
             patch.object(lc, "print_warning") as warn:
            assert lc.get_managed_projects() == []
            warn.assert_called_once()


class TestGetLegacyProjects:
    """Legacy = container with a recognised service label but no managed label."""

    def test_legacy_minus_managed_set(self):
        from sanity_gravity.verbs import lifecycle as lc

        # First call (legacy ps) yields project|service per line.
        # Second call (managed ps from get_managed_projects) yields the
        # subset that's already managed.
        outputs = iter([
            "p-old|ag-xfce-kasm\n"
            "p-managed|ag-none-ssh\n"
            "p-junk|nope-service\n",
            "p-managed\n",  # managed projects
        ])

        def fake_run(cmd, **_kw):
            return next(outputs)

        with patch.object(lc, "run_command", side_effect=fake_run):
            assert lc.get_legacy_projects() == ["p-old"]

    def test_legacy_empty_when_no_containers(self):
        from sanity_gravity.verbs import lifecycle as lc

        with patch.object(lc, "run_command", return_value=""):
            assert lc.get_legacy_projects() == []

    def test_legacy_subprocess_error_warns(self):
        from sanity_gravity.verbs import lifecycle as lc

        with patch.object(lc, "run_command",
                          side_effect=subprocess.CalledProcessError(1, "docker ps")), \
             patch.object(lc, "print_warning") as warn:
            assert lc.get_legacy_projects() == []
            warn.assert_called_once()
            assert "legacy projects" in warn.call_args[0][0]
