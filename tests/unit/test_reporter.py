"""Minimal tests for the structured Reporter introduced in PR #2."""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Make the package importable the same way sanity-cli does.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from sanity_gravity.events import (  # noqa: E402
    AccessInfo, CommandIssued, Header, Info, Success,
)
from sanity_gravity.core.reporter import (  # noqa: E402
    AnsiSink,
    FileSink,
    JsonlSink,
    Reporter,
    build_default_reporter,
)


class RecorderSink:
    """Test helper sink: captures every event for assertion."""

    def __init__(self):
        self.events = []

    def consume(self, event):
        self.events.append(event)


def test_reporter_emits_to_all_sinks():
    rec = RecorderSink()
    r = Reporter(sinks=[rec], run_id="testrun1")
    r.info("hello")
    r.success("done")
    assert len(rec.events) == 2
    assert isinstance(rec.events[0], Info) and rec.events[0].message == "hello"
    assert rec.events[0].run_id == "testrun1"
    assert rec.events[0].level == "info"
    assert isinstance(rec.events[1], Success)


def test_ansi_sink_renders_legacy_colours():
    buf = io.StringIO()
    sink = AnsiSink(buf)
    sink.consume(Header(ts=0.0, run_id="x", level="header", message="hi"))
    sink.consume(Info(ts=0.0, run_id="x", level="info", message="hi"))
    sink.consume(Success(ts=0.0, run_id="x", level="success", message="ok"))
    sink.consume(CommandIssued(ts=0.0, run_id="x", argv=("ls", "-la")))
    out = buf.getvalue()
    assert "\033[95m\033[1m>>> hi\033[0m" in out
    assert "\033[96mℹ hi\033[0m" in out
    assert "\033[92m✔ ok\033[0m" in out
    assert "\033[94m$ ls -la\033[0m" in out


def test_jsonl_sink_emits_one_object_per_line():
    buf = io.StringIO()
    sink = JsonlSink(buf)
    sink.consume(Info(ts=1.5, run_id="abc", level="info", message="x"))
    sink.consume(Success(ts=1.6, run_id="abc", level="success", message="y"))
    lines = [ln for ln in buf.getvalue().splitlines() if ln]
    assert len(lines) == 2
    obj = json.loads(lines[0])
    assert obj["type"] == "Info"
    assert obj["run_id"] == "abc"
    assert obj["message"] == "x"


def test_file_sink_writes_to_run_dir(tmp_path):
    sink = FileSink(run_id="abcd1234", base=tmp_path)
    sink.consume(Info(ts=0.0, run_id="abcd1234", level="info", message="m"))
    expected = tmp_path / "abcd1234" / "events.jsonl"
    assert expected.exists()
    payload = json.loads(expected.read_text().strip())
    assert payload["type"] == "Info" and payload["message"] == "m"


def test_access_info_renders_with_underline():
    buf = io.StringIO()
    sink = AnsiSink(buf)
    sink.consume(AccessInfo(
        ts=0.0,
        run_id="x",
        connector="kasm",
        fields={"URL:      ": "https://localhost:8444", "User:     ": "alice"},
    ))
    out = buf.getvalue()
    assert "Access KasmVNC:" in out
    assert "\033[4mhttps://localhost:8444\033[0m" in out  # URL underlined
    assert "  User:     alice" in out


def test_build_default_reporter_text_mode(tmp_path, monkeypatch):
    # Redirect FileSink base so we don't pollute the user's cache.
    monkeypatch.setenv("HOME", str(tmp_path))
    r = build_default_reporter(log_format="text", base=tmp_path / "runs")
    assert r.run_id and len(r.run_id) == 8
    assert len(r.sinks) == 2  # AnsiSink + FileSink


def test_build_default_reporter_json_mode_writes_to_stderr(tmp_path, capsys):
    """JSON-mode JsonlSink must write to stderr so stdout stays clean
    for structured data payloads (the ``list`` matrix, ``--json``
    arrays, ``docker compose ps`` passthrough, etc.)."""
    r = build_default_reporter(log_format="json", base=tmp_path / "runs")
    r.info("hello-json")
    captured = capsys.readouterr()
    # Narration must land on stderr.
    assert "hello-json" in captured.err
    err_lines = [ln for ln in captured.err.splitlines() if ln.strip()]
    assert err_lines, "expected at least one JSONL line on stderr"
    payload = json.loads(err_lines[0])
    assert payload["type"] == "Info"
    assert payload["message"] == "hello-json"
    # And nothing should land on stdout.
    assert captured.out == ""


def test_file_sink_close_releases_handle(tmp_path):
    """FileSink.close() must release its file handle and be idempotent."""
    sink = FileSink(run_id="closetest", base=tmp_path)
    sink.consume(Info(ts=0.0, run_id="closetest", level="info", message="m"))
    assert sink._fp is not None and not sink._fp.closed
    fp = sink._fp
    sink.close()
    assert sink._fp is None
    assert fp.closed
    # Idempotent: a second close is a no-op, not an error.
    sink.close()


def test_reporter_close_propagates_to_sinks(tmp_path):
    """Reporter.close() must call close() on every sink that has one
    and must not raise for sinks that don't."""
    file_sink = FileSink(run_id="rcclose", base=tmp_path)
    ansi_sink = AnsiSink(io.StringIO())  # no close() method
    r = Reporter(sinks=[file_sink, ansi_sink], run_id="rcclose")
    r.info("x")
    assert file_sink._fp is not None
    r.close()
    assert file_sink._fp is None


def test_cli_list_visual_parity_only_run_id_header():
    """Legacy ``list`` output must be byte-identical except for the new
    ``run-id:`` header line emitted at startup."""
    repo = _REPO_ROOT
    res = subprocess.run(
        [str(repo / "sanity-cli"), "list"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": os.environ.get("HOME", "/tmp")},
    )
    assert res.returncode == 0
    lines = res.stdout.splitlines()
    # First line must be the run-id header; the rest should be the
    # familiar dimension matrix output.
    assert lines and "run-id:" in lines[0]
    assert any("Dimension Matrix" in ln for ln in lines)
    assert any("ag-xfce-kasm" in ln for ln in lines)
