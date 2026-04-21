"""Tests for username / project-name validation and defence against
shell/sed injection via HOST_USER or --name."""
import sys
import os
import importlib.util
import pytest
from importlib.machinery import SourceFileLoader


def load_sanity_cli():
    if "sanity_cli" in sys.modules:
        return sys.modules["sanity_cli"]
    file_path = os.path.abspath("sanity-cli")
    loader = SourceFileLoader("sanity_cli", file_path)
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader("sanity_cli", loader))
    sys.modules["sanity_cli"] = module
    loader.exec_module(module)
    return module


sanity_cli = load_sanity_cli()


class TestUsernameValidation:
    @pytest.mark.parametrize("name", [
        "developer",
        "alice",
        "_root",
        "user-1",
        "a",
        "A" * 32,
    ])
    def test_accepts_valid(self, name):
        assert sanity_cli.validate_username(name) == name

    @pytest.mark.parametrize("name", [
        "",
        "1leading-digit",
        "-leadingdash",
        "has space",
        "has/slash",
        "'; rm -rf /",
        "a|b",
        "x$y",
        "x`y`",
        "name;drop",
        "A" * 33,
        "unicodeé",
    ])
    def test_rejects_injection(self, name):
        with pytest.raises(ValueError, match="Invalid username"):
            sanity_cli.validate_username(name)


class TestProjectNameValidation:
    @pytest.mark.parametrize("name", [
        "sanity-gravity",
        "proj_1",
        "a.b.c",
        "A1",
    ])
    def test_accepts_valid(self, name):
        assert sanity_cli.validate_project_name(name) == name

    @pytest.mark.parametrize("name", [
        "",
        "-leadingdash",
        ".dotstart",
        "bad name",
        "has/slash",
        "'; echo pwn",
        "a" * 64,
    ])
    def test_rejects_bad(self, name):
        with pytest.raises(ValueError, match="Invalid project name"):
            sanity_cli.validate_project_name(name)
