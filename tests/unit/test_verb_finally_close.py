"""Tests that each kernelized verb's ``try/finally`` actually flushes
the executor when the orchestrator raises an UNEXPECTED exception
(i.e. not ``ActionFailedError``, which has its own catch).

Without ``try/finally`` (the legacy ``atexit``-only design) a
non-``ActionFailedError`` exception would skip executor.close() and
the actions.jsonl tail would be lost.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))


def _stub_reporter():
    rep = MagicMock()
    rep.run_id = "vt"
    rep.run_dir = Path("/tmp/vt")
    return rep


class TestBuildVerbFinally:
    def test_executor_closed_on_keyerror(self):
        from sanity_gravity.verbs import build as build_mod

        executor = MagicMock()
        with patch.object(build_mod, "build_default_executor",
                          return_value=executor), \
             patch.object(build_mod, "Orchestrator") as orch_cls, \
             patch.object(build_mod, "register_builtin_build_hooks"), \
             patch.object(build_mod, "get_reporter",
                          return_value=_stub_reporter()), \
             patch.object(build_mod, "print_header"), \
             patch.object(build_mod, "print_error"):
            orch_cls.return_value.run.side_effect = KeyError("boom")
            args = argparse.Namespace(
                no_cache=False, list_intermediates=False,
                layer=None, layer_target=None,
                variant=["ag-xfce-kasm"], dry_run=False,
                json_output=False,
            )
            with pytest.raises(KeyError):
                build_mod.build(args)
            executor.close.assert_called_once()


class TestLifecycleVerbFinally:
    def test_executor_closed_on_keyerror_for_down(self):
        from sanity_gravity.verbs import lifecycle as lc_mod

        executor = MagicMock()
        with patch.object(lc_mod, "build_default_executor",
                          return_value=executor), \
             patch.object(lc_mod, "Orchestrator") as orch_cls, \
             patch.object(lc_mod, "register_builtin_lifecycle_hooks"), \
             patch.object(lc_mod, "get_reporter",
                          return_value=_stub_reporter()):
            orch_cls.return_value.run.side_effect = KeyError("boom")
            args = argparse.Namespace(name="proj", dry_run=False)
            with pytest.raises(KeyError):
                lc_mod.down(args)
            executor.close.assert_called_once()


class TestSnapshotVerbFinally:
    def test_executor_closed_on_keyerror(self):
        from sanity_gravity.verbs import snapshot as sn_mod

        executor = MagicMock()
        with patch.object(sn_mod, "build_default_executor",
                          return_value=executor), \
             patch.object(sn_mod, "Orchestrator") as orch_cls, \
             patch.object(sn_mod, "register_builtin_snapshot_hooks"), \
             patch.object(sn_mod, "get_reporter",
                          return_value=_stub_reporter()):
            orch_cls.return_value.run.side_effect = KeyError("boom")
            args = argparse.Namespace(
                name="proj", tag="newtag", variant=None,
                dry_run=False,
            )
            with pytest.raises(KeyError):
                sn_mod.snapshot_cmd(args)
            executor.close.assert_called_once()


class TestUpVerbFinally:
    def test_executor_closed_on_keyerror(self):
        from sanity_gravity.verbs import up as up_mod

        executor = MagicMock()
        rep = _stub_reporter()
        with patch.object(up_mod, "build_default_executor",
                          return_value=executor), \
             patch.object(up_mod, "Orchestrator") as orch_cls, \
             patch.object(up_mod, "register_builtin_up_hooks"), \
             patch.object(up_mod, "get_reporter", return_value=rep), \
             patch.object(up_mod, "check_prereqs"), \
             patch.object(up_mod, "get_uid_gid_user",
                          return_value=(1000, 1000, "u")), \
             patch.object(up_mod, "validate_project_name", return_value="p"), \
             patch.object(up_mod, "print_header"), \
             patch.object(up_mod, "print_info"), \
             patch.object(up_mod, "print_error"), \
             patch("os.makedirs"):
            orch_cls.return_value.run.side_effect = KeyError("boom")
            args = argparse.Namespace(
                variant="ag-xfce-kasm",
                skip_check=True,
                workspace=None,
                name="p",
                ssh_port="2222",
                kasm_port="8444",
                vnc_port="5901",
                novnc_port="6901",
                password="pw",
                cpus=None,
                memory=None,
                image=None,
                reporter=rep,
                dry_run=False,
            )
            with pytest.raises(KeyError):
                up_mod.up(args)
            executor.close.assert_called_once()
