"""Structured Reporter: emit Event objects into a fan-out of Sinks.

The Reporter has no opinion on how an event should look. It just stamps
``ts`` / ``run_id`` / ``level`` and dispatches. Each Sink renders or
persists in its own way:

- ``AnsiSink``  — preserves the legacy ``print_*`` colourised UX.
- ``JsonlSink`` — one JSON object per line (machine consumers / CI).
- ``FileSink``  — always-on, best-effort, writes to
  ``~/.cache/sanity-gravity/runs/<run_id>/events.jsonl``.

Sinks are intentionally not abstract — they only need a ``consume``
method. The ``Sink`` Protocol below documents that contract.
"""
from __future__ import annotations

import dataclasses
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import IO, Iterable, Protocol

from events import (  # type: ignore[import-not-found]
    AccessInfo,
    CacheHit,
    CommandIssued,
    ErrorEvent,
    Event,
    Header,
    Info,
    LayerBuilding,
    LayerBuilt,
    Prompt,
    Success,
    Warning,
)


# ANSI escapes — kept here so AnsiSink is self-contained, but they match
# the legacy ``Colors`` block in sanity-cli byte-for-byte.
_HEADER = "\033[95m"
_OKBLUE = "\033[94m"
_OKCYAN = "\033[96m"
_OKGREEN = "\033[92m"
_WARNING = "\033[93m"
_FAIL = "\033[91m"
_ENDC = "\033[0m"
_BOLD = "\033[1m"
_UNDERLINE = "\033[4m"


class Sink(Protocol):
    """Anything that can consume an Event."""

    def consume(self, event: Event) -> None:  # pragma: no cover - protocol
        ...


class AnsiSink:
    """Renders events as the legacy colourised ``print_*`` lines.

    Output is byte-equivalent to the previous inline ``Colors``-using
    prints, so existing user UX is preserved.
    """

    def __init__(self, stream: IO[str] | None = None) -> None:
        self._out = stream if stream is not None else sys.stdout

    def consume(self, event: Event) -> None:
        out = self._out
        if isinstance(event, Header):
            out.write(f"{_HEADER}{_BOLD}>>> {event.message}{_ENDC}\n")
        elif isinstance(event, Success):
            out.write(f"{_OKGREEN}✔ {event.message}{_ENDC}\n")
        elif isinstance(event, ErrorEvent):
            out.write(f"{_FAIL}✘ {event.message}{_ENDC}\n")
        elif isinstance(event, Warning):
            out.write(f"{_WARNING}⚠ {event.message}{_ENDC}\n")
        elif isinstance(event, Info):
            out.write(f"{_OKCYAN}ℹ {event.message}{_ENDC}\n")
        elif isinstance(event, CommandIssued):
            argv = event.argv
            if isinstance(argv, (list, tuple)):
                import shlex

                rendered = " ".join(shlex.quote(str(p)) for p in argv)
            else:
                rendered = str(argv)
            out.write(f"{_OKBLUE}$ {rendered}{_ENDC}\n")
        elif isinstance(event, AccessInfo):
            self._render_access(event)
        elif isinstance(event, Prompt):
            # Prompts are typed via input(); we leave the actual prompt
            # rendering to the call site, but emit a hint here so a
            # passive Ansi observer still sees the question.
            out.write(f"{_BOLD}{event.question}{_ENDC}")
        elif isinstance(event, (CacheHit, LayerBuilding, LayerBuilt)):
            # These are domain-specific narrations; the legacy code
            # surfaced them via print_info / print_success. We keep the
            # same shape so nothing visually changes when callers route
            # them through events.
            self._render_build(event)
        else:
            # Forward-compat: render the message field if present, else
            # the repr. This branch should only execute for events that
            # post-date this sink.
            msg = getattr(event, "message", None) or repr(event)
            out.write(f"{msg}\n")
        out.flush()

    def _render_access(self, event: AccessInfo) -> None:
        out = self._out
        labels = {
            "kasm": "Access KasmVNC:",
            "vnc": "Access VNC:",
            "ssh": "Access SSH:",
        }
        title = labels.get(event.connector, f"Access {event.connector}:")
        out.write(f"\n{_BOLD}{title}{_ENDC}\n")
        # Keys carry the entire pre-value formatting (label + colon +
        # padding) so the rendered line is byte-identical to the legacy
        # inline prints. Underline URL-shaped values by convention.
        for key, value in event.fields.items():
            stripped = key.strip().rstrip(":").lower()
            if stripped in ("url", "novnc web"):
                out.write(f"  {key}{_UNDERLINE}{value}{_ENDC}\n")
            else:
                out.write(f"  {key}{value}\n")

    def _render_build(self, event: Event) -> None:
        out = self._out
        if isinstance(event, CacheHit):
            out.write(f"{_OKCYAN}ℹ   Cache hit: {event.image}{_ENDC}\n")
        elif isinstance(event, LayerBuilding):
            prefix = (
                f"  [{event.index}/{event.total}] "
                if event.index and event.total
                else "  "
            )
            extra = f" ({event.dockerfile})" if event.dockerfile else ""
            out.write(
                f"{_OKCYAN}ℹ {prefix}Building {event.image}{extra}{_ENDC}\n"
            )
        elif isinstance(event, LayerBuilt):
            out.write(f"{_OKGREEN}✔ Built {event.image}{_ENDC}\n")


class JsonlSink:
    """Writes one JSON object per line to the given stream.

    Used as the visible sink when ``--log-format=json`` is set, and
    composed into ``FileSink`` for run-state persistence.
    """

    def __init__(self, stream: IO[str]) -> None:
        self._out = stream

    def consume(self, event: Event) -> None:
        try:
            payload = dataclasses.asdict(event)
            payload["type"] = type(event).__name__
        except TypeError:
            # Non-dataclass event slipped through; degrade gracefully.
            payload = {"type": type(event).__name__, "repr": repr(event)}
        self._out.write(json.dumps(payload, default=str) + "\n")
        self._out.flush()


class FileSink:
    """Always-on JSONL sink at ``~/.cache/sanity-gravity/runs/<run_id>/events.jsonl``.

    Lazily creates the directory on first use. Failures are non-fatal:
    this sink is best-effort, not load-bearing.
    """

    def __init__(self, run_id: str, base: Path | None = None) -> None:
        self._run_id = run_id
        self._base = base or (Path.home() / ".cache" / "sanity-gravity" / "runs")
        self._fp: IO[str] | None = None
        self._broken = False

    @property
    def path(self) -> Path:
        return self._base / self._run_id / "events.jsonl"

    def _ensure_open(self) -> IO[str] | None:
        if self._broken:
            return None
        if self._fp is not None:
            return self._fp
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._fp = self.path.open("a", encoding="utf-8")
        except OSError as exc:
            sys.stderr.write(
                f"warning: file event log unavailable ({exc}); continuing\n"
            )
            self._broken = True
            return None
        return self._fp

    def consume(self, event: Event) -> None:
        fp = self._ensure_open()
        if fp is None:
            return
        try:
            payload = dataclasses.asdict(event)
            payload["type"] = type(event).__name__
            fp.write(json.dumps(payload, default=str) + "\n")
            fp.flush()
        except OSError:
            # Disk pressure or closed stream — give up silently.
            self._broken = True

    def close(self) -> None:
        """Close the underlying file handle if open.

        Idempotent and exception-safe: safe to call from ``atexit`` even
        if the sink was never written to or already closed.
        """
        fp = self._fp
        self._fp = None
        if fp is None:
            return
        try:
            fp.close()
        except OSError:
            # Best-effort cleanup; nothing useful to do on failure.
            pass


class Reporter:
    """Builds events with run_id/timestamp and fans them out to sinks."""

    def __init__(
        self,
        sinks: Iterable[Sink] | None = None,
        run_id: str | None = None,
    ) -> None:
        self.run_id = run_id or uuid.uuid4().hex[:8]
        self.sinks: list[Sink] = list(sinks) if sinks else []

    # -- core API -----------------------------------------------------

    def emit(self, event: Event) -> None:
        for sink in self.sinks:
            try:
                sink.consume(event)
            except Exception as exc:  # pragma: no cover - defensive
                sys.stderr.write(
                    f"warning: sink {type(sink).__name__} failed: {exc}\n"
                )

    # -- convenience builders ----------------------------------------

    def _stamp(self, level: str) -> dict:
        return {"ts": time.time(), "run_id": self.run_id, "phase": None, "level": level}

    def header(self, message: str) -> None:
        self.emit(Header(message=message, **self._stamp("header")))

    def info(self, message: str) -> None:
        self.emit(Info(message=message, **self._stamp("info")))

    def success(self, message: str) -> None:
        self.emit(Success(message=message, **self._stamp("success")))

    def warning(self, message: str) -> None:
        self.emit(Warning(message=message, **self._stamp("warning")))

    def error(self, message: str) -> None:
        self.emit(ErrorEvent(message=message, **self._stamp("error")))

    def command(self, argv: tuple[str, ...] | str) -> None:
        self.emit(CommandIssued(argv=argv, **self._stamp("info")))

    def access(self, connector: str, fields: dict[str, str]) -> None:
        self.emit(
            AccessInfo(connector=connector, fields=dict(fields), **self._stamp("info"))
        )

    def close(self) -> None:
        """Close any sinks that own external resources (e.g. file handles).

        Sinks without a ``close`` method are skipped. Failures are logged
        but never raised — this is meant to run from ``atexit``.
        """
        for sink in self.sinks:
            close = getattr(sink, "close", None)
            if not callable(close):
                continue
            try:
                close()
            except Exception as exc:  # pragma: no cover - defensive
                sys.stderr.write(
                    f"warning: sink {type(sink).__name__} close failed: {exc}\n"
                )


def build_default_reporter(
    log_format: str = "text",
    *,
    base: Path | None = None,
) -> Reporter:
    """Construct the standard reporter wiring used by the CLI.

    - ``text`` mode: AnsiSink to stdout + always-on FileSink.
    - ``json`` mode: JsonlSink to **stderr** + always-on FileSink.

    The JSON-mode routing follows the Unix convention: data on stdout,
    narration/diagnostics on stderr. This keeps ``stdout`` clean for
    structured payloads (e.g. the ``list`` matrix, ``--json`` arrays,
    ``docker compose ps`` passthrough) while still letting consumers
    capture every event via ``2> events.jsonl``.
    """
    run_id = uuid.uuid4().hex[:8]
    sinks: list[Sink] = []
    if log_format == "json":
        sinks.append(JsonlSink(sys.stderr))
    else:
        sinks.append(AnsiSink(sys.stdout))
    sinks.append(FileSink(run_id, base=base))
    return Reporter(sinks=sinks, run_id=run_id)
