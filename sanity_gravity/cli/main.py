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


def main():
    """Top-level entry. Wired to ``sanity-cli`` via the shim."""
    parser = build_parser()
    args = parser.parse_args()

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
    reporter.header(f"run-id: {reporter.run_id}")

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
