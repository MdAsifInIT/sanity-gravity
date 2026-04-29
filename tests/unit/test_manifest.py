"""Tests for ``lib/manifest.py`` — TOML schema parsing.

Each of the 8 builtin plugins must load cleanly and surface its declared
fields. We also cover failure paths (missing required keys, kind/dir
mismatches) on synthesised manifests.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from sanity_gravity.plugins.manifest import (  # noqa: E402
    AnnounceSpec,
    ComposeOverlay,
    ManifestError,
    PluginManifest,
    PortSpec,
    load_manifest,
)


PLUGINS_DIR = _REPO_ROOT / "plugins"


# ---------------------------------------------------------------------------
# All 8 builtin manifests: load + structural assertions.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind,slug",
    [
        ("agents", "ag"),
        ("agents", "gc"),
        ("agents", "cc"),
        ("desktops", "xfce"),
        ("desktops", "none"),
        ("connectors", "kasm"),
        ("connectors", "vnc"),
        ("connectors", "ssh"),
    ],
)
def test_load_each_builtin_manifest(kind, slug):
    """Every shipped plugin manifest parses, with consistent slug/kind."""
    path = PLUGINS_DIR / kind / slug / "manifest.toml"
    m = load_manifest(path)

    assert isinstance(m, PluginManifest)
    assert m.slug == slug
    # kind=singular in manifest, kind=plural in directory tree
    assert m.kind == kind.rstrip("s")
    assert m.api_version == "1"
    assert m.dockerfile == "Dockerfile"
    assert m.dockerfile_path.is_file()


def test_ag_requires_display():
    m = load_manifest(PLUGINS_DIR / "agents" / "ag" / "manifest.toml")
    assert m.requires == ("display",)
    assert m.provides == ()


def test_xfce_provides_display():
    m = load_manifest(PLUGINS_DIR / "desktops" / "xfce" / "manifest.toml")
    assert m.provides == ("display",)
    assert m.requires == ()


def test_none_desktop_no_capabilities():
    m = load_manifest(PLUGINS_DIR / "desktops" / "none" / "manifest.toml")
    assert m.provides == ()
    assert m.requires == ()


def test_kasm_ports_and_compose():
    m = load_manifest(PLUGINS_DIR / "connectors" / "kasm" / "manifest.toml")
    assert m.provides == ("graphical-remote",)
    assert m.requires == ("display",)
    by_label = m.ports_by_label()
    assert by_label["http"] == PortSpec(
        label="http", internal=8444, default=8444, env_var="KASM_PORT"
    )
    assert by_label["ssh"].internal == 22
    assert m.compose == ComposeOverlay(
        shm_size="512m", restart="unless-stopped", stop_grace_period="30s"
    )
    assert m.environment == ()
    assert isinstance(m.announce, AnnounceSpec)
    # template carries the {ports.http} substitution placeholder
    assert "{ports.http}" in m.announce.template


def test_vnc_environment_includes_vnc_pw():
    m = load_manifest(PLUGINS_DIR / "connectors" / "vnc" / "manifest.toml")
    env = dict(m.environment)
    assert "VNC_PW" in env
    assert "VNC_RESOLUTION" in env
    assert "VNC_DEPTH" in env
    by_label = m.ports_by_label()
    assert set(by_label) == {"vnc", "novnc", "ssh"}


def test_ssh_announce_uses_container_name():
    m = load_manifest(PLUGINS_DIR / "connectors" / "ssh" / "manifest.toml")
    assert m.compose.is_empty()
    assert m.environment == ()
    assert "{container_name}" in m.announce.template


# ---------------------------------------------------------------------------
# Failure paths.
# ---------------------------------------------------------------------------


def _write(tmp_path, body: str) -> Path:
    p = tmp_path / "manifest.toml"
    p.write_text(body)
    return p


def test_missing_plugin_table_raises(tmp_path):
    path = _write(tmp_path, '[capabilities]\nprovides = []\n')
    with pytest.raises(ManifestError, match="missing required key 'plugin'"):
        load_manifest(path)


def test_invalid_kind_rejected(tmp_path):
    path = _write(
        tmp_path,
        '[plugin]\nslug = "x"\nname = "x"\nkind = "weapon"\napi_version = "1"\n'
        '[build]\ndockerfile = "Dockerfile"\n',
    )
    with pytest.raises(ManifestError, match="kind must be one of"):
        load_manifest(path)


def test_ports_on_non_connector_rejected(tmp_path):
    path = _write(
        tmp_path,
        '[plugin]\nslug = "x"\nname = "x"\nkind = "agent"\napi_version = "1"\n'
        '[build]\ndockerfile = "Dockerfile"\n'
        '[ports.web]\ninternal = 80\ndefault = 80\nenv_var = "WEB_PORT"\n',
    )
    with pytest.raises(ManifestError, match=r"\[ports\.\*\] only valid on kind=connector"):
        load_manifest(path)


def test_announce_on_non_connector_rejected(tmp_path):
    path = _write(
        tmp_path,
        '[plugin]\nslug = "x"\nname = "x"\nkind = "desktop"\napi_version = "1"\n'
        '[build]\ndockerfile = "Dockerfile"\n'
        '[announce]\ntemplate = "hi"\n',
    )
    with pytest.raises(ManifestError, match=r"\[announce\] only valid on kind=connector"):
        load_manifest(path)


def test_missing_dockerfile_key_rejected(tmp_path):
    path = _write(
        tmp_path,
        '[plugin]\nslug = "x"\nname = "x"\nkind = "agent"\napi_version = "1"\n'
        '[build]\n',
    )
    with pytest.raises(ManifestError, match="missing required key 'dockerfile'"):
        load_manifest(path)


def test_nonexistent_file(tmp_path):
    with pytest.raises(ManifestError, match="manifest not found"):
        load_manifest(tmp_path / "nope.toml")
