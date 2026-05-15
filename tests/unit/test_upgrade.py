"""Tests for ``verbs/upgrade.py`` — focused on the port-conflict logic
at lines 101–115. These branches were uncovered: a regression that
silently picks the wrong port in the env set passed to
``docker compose up`` is not caught anywhere else.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))


def _captured_env_after_upgrade(*, busy_ports: set[int]):
    """Run upgrade() against synthetic legacy state and return the env
    dict passed to the final ``docker compose up`` call."""
    from sanity_gravity.verbs import upgrade as upgrade_mod

    captured = {}

    def fake_run_command(cmd, **kwargs):
        # ps to list services for the project.
        if "ps" in cmd and "--format" in cmd and any("service" in c for c in cmd):
            return "ag-xfce-kasm\n"
        # ps -a -q to find a container id (none exists in this test).
        if "-q" in cmd:
            return ""
        # The actual ``docker compose -p ... up -d --force-recreate``: capture env.
        if "compose" in cmd and "up" in cmd:
            captured.update(kwargs.get("env") or {})
            return ""
        return ""

    args = argparse.Namespace(name="sanity-gravity")
    with patch.object(upgrade_mod, "get_legacy_projects",
                      return_value=["sanity-gravity"]), \
         patch.object(upgrade_mod, "get_project_env", return_value={}), \
         patch.object(upgrade_mod, "get_uid_gid_user",
                      return_value=(1000, 1000, "alice")), \
         patch.object(upgrade_mod, "is_port_in_use",
                      side_effect=lambda p: p in busy_ports), \
         patch.object(upgrade_mod, "run_command", side_effect=fake_run_command), \
         patch.object(upgrade_mod, "generate_git_compose", return_value=None), \
         patch("sanity_gravity.verbs.status.status"), \
         patch("sys.stdin.isatty", return_value=False), \
         patch.object(upgrade_mod, "print_info"), \
         patch.object(upgrade_mod, "print_warning"), \
         patch.object(upgrade_mod, "print_header"), \
         patch.object(upgrade_mod, "print_success"), \
         patch.object(upgrade_mod, "print_error"):
        upgrade_mod.upgrade(args)

    return captured


class TestUpgradePortAllocation:
    """Cover the four port branches: ssh / kasm / vnc / novnc."""

    def test_default_project_busy_kasm_port_falls_to_zero(self):
        env = _captured_env_after_upgrade(busy_ports={8444})
        assert env.get("KASM_PORT") == "0"
        # Other ports remain unset (empty dict — they're only set when busy).
        assert "SSH_HOST_PORT" not in env
        assert "VNC_PORT" not in env
        assert "NOVNC_PORT" not in env

    def test_default_project_no_busy_ports_no_zero(self):
        env = _captured_env_after_upgrade(busy_ports=set())
        assert "KASM_PORT" not in env
        assert "SSH_HOST_PORT" not in env

    def test_default_project_all_ports_busy(self):
        env = _captured_env_after_upgrade(
            busy_ports={2222, 8444, 5901, 6901}
        )
        assert env["SSH_HOST_PORT"] == "0"
        assert env["KASM_PORT"] == "0"
        assert env["VNC_PORT"] == "0"
        assert env["NOVNC_PORT"] == "0"

    def test_custom_project_zeros_all_ports_regardless_of_busy(self):
        """For a non-default project name, port-zero is unconditional —
        even if no ports are busy on the host."""
        from sanity_gravity.verbs import upgrade as upgrade_mod

        captured = {}

        def fake_run_command(cmd, **kwargs):
            if "ps" in cmd and "--format" in cmd and any("service" in c for c in cmd):
                return "ag-xfce-kasm\n"
            if "-q" in cmd:
                return ""
            if "compose" in cmd and "up" in cmd:
                captured.update(kwargs.get("env") or {})
                return ""
            return ""

        args = argparse.Namespace(name="myproj")
        with patch.object(upgrade_mod, "get_legacy_projects",
                          return_value=["myproj"]), \
             patch.object(upgrade_mod, "get_project_env", return_value={}), \
             patch.object(upgrade_mod, "get_uid_gid_user",
                          return_value=(1000, 1000, "alice")), \
             patch.object(upgrade_mod, "is_port_in_use", return_value=False), \
             patch.object(upgrade_mod, "run_command", side_effect=fake_run_command), \
             patch.object(upgrade_mod, "generate_git_compose", return_value=None), \
             patch("sanity_gravity.verbs.status.status"), \
             patch("sys.stdin.isatty", return_value=False), \
             patch.object(upgrade_mod, "print_info"), \
             patch.object(upgrade_mod, "print_warning"), \
             patch.object(upgrade_mod, "print_header"), \
             patch.object(upgrade_mod, "print_success"), \
             patch.object(upgrade_mod, "print_error"):
            upgrade_mod.upgrade(args)

        assert captured["SSH_HOST_PORT"] == "0"
        assert captured["KASM_PORT"] == "0"
        assert captured["VNC_PORT"] == "0"
        assert captured["NOVNC_PORT"] == "0"

    def test_preexisting_env_port_preserved(self):
        """If ``get_project_env`` already returned a port (read off the
        existing container), the upgrade must NOT clobber it with 0."""
        from sanity_gravity.verbs import upgrade as upgrade_mod

        captured = {}

        def fake_run_command(cmd, **kwargs):
            if "ps" in cmd and "--format" in cmd and any("service" in c for c in cmd):
                return "ag-xfce-kasm\n"
            if "-q" in cmd:
                return ""
            if "compose" in cmd and "up" in cmd:
                captured.update(kwargs.get("env") or {})
                return ""
            return ""

        args = argparse.Namespace(name="sanity-gravity")
        with patch.object(upgrade_mod, "get_legacy_projects",
                          return_value=["sanity-gravity"]), \
             patch.object(upgrade_mod, "get_project_env",
                          return_value={"KASM_PORT": "12345"}), \
             patch.object(upgrade_mod, "get_uid_gid_user",
                          return_value=(1000, 1000, "alice")), \
             patch.object(upgrade_mod, "is_port_in_use", return_value=True), \
             patch.object(upgrade_mod, "run_command", side_effect=fake_run_command), \
             patch.object(upgrade_mod, "generate_git_compose", return_value=None), \
             patch("sanity_gravity.verbs.status.status"), \
             patch("sys.stdin.isatty", return_value=False), \
             patch.object(upgrade_mod, "print_info"), \
             patch.object(upgrade_mod, "print_warning"), \
             patch.object(upgrade_mod, "print_header"), \
             patch.object(upgrade_mod, "print_success"), \
             patch.object(upgrade_mod, "print_error"):
            upgrade_mod.upgrade(args)

        assert captured["KASM_PORT"] == "12345"  # preserved, NOT overwritten
