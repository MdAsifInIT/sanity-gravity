"""Plugin registry: discover and index manifest-driven plugins.

A registry walks ``plugins/<kind>/<slug>/manifest.toml`` once at startup
and stores the parsed :class:`~manifest.PluginManifest` objects in three
kind-keyed dicts. Other components (CLI tag parsing, build-chain
resolver, compose hook, announce hook) consult the registry via small
typed accessors instead of hardcoded ``AGENTS`` / ``DESKTOPS`` /
``CONNECTORS`` literals.

Discovery is filesystem-based and builtin-only: there is no entry-point
support and no remote loading. Adding a new dimension is ``mkdir
plugins/<kind>/<slug>/`` + ``manifest.toml`` + ``Dockerfile``.
"""
from __future__ import annotations

from pathlib import Path

from capability import CapabilityConflictError, solve  # type: ignore[import-not-found]
from manifest import (  # type: ignore[import-not-found]
    ManifestError,
    PluginManifest,
    load_manifest,
)
from phase import Tag  # type: ignore[import-not-found]


__all__ = ["PluginRegistry", "default_registry"]


_VALID_KINDS: tuple[str, ...] = ("agent", "desktop", "connector")
_KIND_TO_PLURAL: dict[str, str] = {
    "agent": "agents",
    "desktop": "desktops",
    "connector": "connectors",
}


class PluginRegistry:
    """Three-keyed index of parsed plugin manifests.

    Attributes
    ----------
    agents / desktops / connectors:
        ``dict[slug -> PluginManifest]`` for that kind.
    root:
        Root of the plugin tree (e.g. ``plugins/``). Useful for callers
        that need to resolve relative manifest paths.
    """

    __slots__ = ("agents", "desktops", "connectors", "root")

    def __init__(self, root: Path | None = None) -> None:
        self.agents: dict[str, PluginManifest] = {}
        self.desktops: dict[str, PluginManifest] = {}
        self.connectors: dict[str, PluginManifest] = {}
        self.root = root

    # -- construction ------------------------------------------------

    @classmethod
    def from_dir(cls, root: str | Path) -> "PluginRegistry":
        """Walk ``<root>/{agents,desktops,connectors}/<slug>/manifest.toml``.

        Each subdirectory missing a ``manifest.toml`` is silently skipped
        (it can host stale aux files mid-refactor); each *present* one is
        loaded and validated. Duplicate slugs within a kind raise.
        """
        r = Path(root)
        reg = cls(root=r)
        for kind in _VALID_KINDS:
            kind_dir = r / _KIND_TO_PLURAL[kind]
            if not kind_dir.is_dir():
                continue
            for slug_dir in sorted(kind_dir.iterdir()):
                if not slug_dir.is_dir():
                    continue
                manifest_path = slug_dir / "manifest.toml"
                if not manifest_path.is_file():
                    continue
                m = load_manifest(manifest_path)
                if m.kind != kind:
                    raise ManifestError(
                        f"{manifest_path}: kind '{m.kind}' does not match "
                        f"directory '{kind_dir.name}'"
                    )
                if m.slug != slug_dir.name:
                    raise ManifestError(
                        f"{manifest_path}: slug '{m.slug}' does not match "
                        f"directory '{slug_dir.name}'"
                    )
                bucket = reg._bucket(kind)
                if m.slug in bucket:
                    raise ManifestError(
                        f"{manifest_path}: duplicate slug '{m.slug}' for kind '{kind}'"
                    )
                bucket[m.slug] = m
        return reg

    # -- accessors ---------------------------------------------------

    def _bucket(self, kind: str) -> dict[str, PluginManifest]:
        if kind == "agent":
            return self.agents
        if kind == "desktop":
            return self.desktops
        if kind == "connector":
            return self.connectors
        raise KeyError(f"unknown plugin kind: {kind!r}")

    def get(self, kind: str, slug: str) -> PluginManifest:
        """Return the manifest for ``(kind, slug)`` or raise ``KeyError``.

        ``kind`` accepts the singular form (``"agent"``).
        """
        bucket = self._bucket(kind)
        if slug not in bucket:
            raise KeyError(f"no {kind} plugin with slug {slug!r}")
        return bucket[slug]

    def all_slugs(self, kind: str) -> list[str]:
        """Slugs registered for ``kind``, in stable insertion order."""
        return list(self._bucket(kind).keys())

    def all_manifests(self) -> list[PluginManifest]:
        """Flat list of every registered manifest (agents → desktops → connectors)."""
        return [
            *self.agents.values(),
            *self.desktops.values(),
            *self.connectors.values(),
        ]

    # -- tag enumeration --------------------------------------------

    def valid_tags(self) -> list[Tag]:
        """All ``(agent, desktop, connector)`` combos that satisfy capabilities.

        Mirrors the legacy ``generate_valid_tags`` ordering: agent outer,
        desktop middle, connector inner; each loop uses the registry's
        own (insertion) order.
        """
        out: list[Tag] = []
        for a in self.agents:
            for d in self.desktops:
                for c in self.connectors:
                    tag = Tag(agent=a, desktop=d, connector=c)
                    try:
                        solve(tag, self)
                    except CapabilityConflictError:
                        continue
                    out.append(tag)
        return out


# ---- module-level lazy default registry --------------------------------

_DEFAULT: PluginRegistry | None = None


def default_registry(root: str | Path | None = None) -> PluginRegistry:
    """Return a process-wide registry, lazily loaded from ``root``.

    Subsequent calls ignore ``root`` (the first call wins) so the CLI's
    ``parse_tag``/``generate_valid_tags`` see a stable view.
    """
    global _DEFAULT
    if _DEFAULT is None:
        if root is None:
            # repo root assumption: lib/plugins.py → ../plugins
            root = Path(__file__).resolve().parent.parent / "plugins"
        _DEFAULT = PluginRegistry.from_dir(root)
    return _DEFAULT


def reset_default_registry() -> None:
    """Test helper: forget the cached default so the next call rescans."""
    global _DEFAULT
    _DEFAULT = None
