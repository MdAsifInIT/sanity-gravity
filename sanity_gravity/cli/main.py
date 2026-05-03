"""CLI entry point: parse args, install reporter, dispatch to verb."""
from __future__ import annotations

import atexit
import os
import sys

from sanity_gravity.cli.io import (
    print_error,
    print_info,
    print_warning,
    set_reporter,
)
from sanity_gravity.cli.parser import build_parser
from sanity_gravity.core.reporter import build_default_reporter


# Flags accepted at the top level. We pre-process argv so they may also
# appear AFTER the subcommand without confusing argparse, which by
# default attaches a flag to whichever (sub)parser is currently active.
_GLOBAL_BOOL_FLAGS = {"--dry-run"}
_GLOBAL_VALUE_FLAGS = {"--log-format"}


def _preprocess_argv(argv: list[str]) -> list[str]:
    """Two argv massages so the user can't get the syntax wrong:

    1. ``explain`` as the first positional becomes ``--dry-run`` — so
       ``sanity-cli explain status`` is identical to
       ``sanity-cli --dry-run status``. Read-only verbs ignore the
       flag; kernelized verbs honor it.
    2. Global flags (``--dry-run``, ``--log-format[=…]``) are lifted to
       the front regardless of where the user typed them. This makes
       ``sanity-cli status --dry-run`` work the same as
       ``sanity-cli --dry-run status``.

    Both transformations are idempotent: running on already-correct
    argv leaves it unchanged.
    """
    if argv and argv[0] == "explain":
        argv = ["--dry-run", *argv[1:]]

    front: list[str] = []
    rest: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in _GLOBAL_BOOL_FLAGS:
            front.append(a)
            i += 1
        elif a in _GLOBAL_VALUE_FLAGS:
            front.append(a)
            if i + 1 < len(argv):
                front.append(argv[i + 1])
                i += 2
            else:  # malformed; let argparse complain
                i += 1
        elif "=" in a and a.split("=", 1)[0] in _GLOBAL_VALUE_FLAGS:
            front.append(a)
            i += 1
        else:
            rest.append(a)
            i += 1
    return front + rest


def main():
    """Top-level entry. Wired to ``sanity-cli`` via the shim."""
    parser = build_parser()
    args = parser.parse_args(_preprocess_argv(sys.argv[1:]))

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Build the reporter once, install it as the module-level handle so
    # legacy print_* helpers route through it, and also expose it on
    # ``args`` for handlers that want to emit events directly.
    reporter = build_default_reporter(
        log_format=getattr(args, "log_format", "text"),
    )
    set_reporter(reporter)
    args.reporter = reporter
    # Ensure file-backed sinks flush and release their handles even on
    # KeyboardInterrupt / unhandled exception paths.
    atexit.register(reporter.close)
    reporter.start()

    try:
        args.func(args)
    except KeyboardInterrupt:
        print()
        print_warning("Interrupted by user.")
        sys.exit(130)
    except SystemExit:
        raise
    except Exception as e:
        print_error(f"Unexpected error: {type(e).__name__}: {e}")
        if os.environ.get("SANITY_DEBUG"):
            import traceback
            traceback.print_exc()
        else:
            print_info("Re-run with SANITY_DEBUG=1 for a full traceback.")
        sys.exit(1)


if __name__ == "__main__":
    main()
