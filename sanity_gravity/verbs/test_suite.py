"""``test`` verb: run the project's pytest suite.

The module is named ``test_suite`` (not ``test``) to keep pytest's
default discovery from sweeping it up as a test file.
"""
from __future__ import annotations

import os
import sys

from sanity_gravity.cli.io import print_error, print_header


def test_suite(args):
    """Run the test suite using pytest."""
    try:
        import pytest
    except ImportError:
        print_error("pytest is not installed. Please run: pip install pytest requests")
        sys.exit(1)

    print_header("Running Test Suite")

    # Disable plugin autoloading to avoid ROS2 environment pollution.
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"

    pytest_args = ["-v"]
    if args.target:
        pytest_args.append(args.target)

    exit_code = pytest.main(pytest_args)
    if exit_code != 0:
        sys.exit(exit_code)
