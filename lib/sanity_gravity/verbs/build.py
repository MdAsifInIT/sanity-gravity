"""``build`` / ``install`` verbs: layered Docker image construction.

The build chain is ``base → desktop → agent → connector``. Each layer
is a standalone Dockerfile with ``ARG BASE_IMAGE`` / ``FROM
${BASE_IMAGE}``. Intermediate images are tagged with ``_`` prefix
(e.g. ``sanity-gravity:_base``).
"""
from __future__ import annotations

import os
import subprocess
import sys

from sanity_gravity.cli.io import (
    print_error,
    print_header,
    print_info,
    print_success,
    run_command,
)
from sanity_gravity.cli.registry import (
    DEFAULT_TAG,
    VALID_TAGS,
    DESKTOPS,
    get_registry,
    parse_tag,
)
from sanity_gravity.core.command import CommandBuilder


SANDBOX_DIR = "sandbox"
IMAGE_PREFIX = "sanity-gravity"


def _image_tag(name):
    return f"{IMAGE_PREFIX}:{name}"


def _image_exists(tag):
    """Check if a Docker image exists locally."""
    r = subprocess.run(
        ("docker", "image", "inspect", tag),
        capture_output=True, text=True,
    )
    return r.returncode == 0


def _get_unique_agent_desktop_pairs():
    """Return unique (agent, desktop) pairs from VALID_TAGS."""
    pairs = set()
    for tag in VALID_TAGS:
        a, d, _ = tag.split("-")
        pairs.add((a, d))
    return sorted(pairs)


def _plugin_dockerfile(kind, slug):
    """Return the manifest-declared Dockerfile path for a plugin."""
    m = get_registry().get(kind, slug)
    return str(m.dockerfile_path)


def _build_context_for(dockerfile_path):
    """Pick the docker build context for a given Dockerfile.

    - ``sandbox/Dockerfile.base`` keeps ``sandbox/`` as its context so it
      can ``COPY rootfs /``.
    - Plugin Dockerfiles use **their own directory** as the context. Only
      ``kasm`` / ``vnc`` actually ``COPY`` local files (supervisord.conf,
      startup.sh) — keeping the context tight prevents accidental reads
      of the rest of the repo and keeps build-cache hashes stable.
    """
    df = os.path.abspath(dockerfile_path)
    base_df = os.path.abspath(os.path.join(SANDBOX_DIR, "Dockerfile.base"))
    if df == base_df:
        return SANDBOX_DIR
    return os.path.dirname(dockerfile_path)


def resolve_build_chain(tag):
    """Build chain for a final tag as ``[(dockerfile, image_name, parent_or_None)]``."""
    agent, desktop, connector = parse_tag(tag)
    return [
        (os.path.join(SANDBOX_DIR, "Dockerfile.base"), "_base", None),
        (_plugin_dockerfile("desktop", desktop), f"_base-{desktop}", "_base"),
        (_plugin_dockerfile("agent", agent),
         f"_{agent}-{desktop}", f"_base-{desktop}"),
        (_plugin_dockerfile("connector", connector),
         tag, f"_{agent}-{desktop}"),
    ]


def resolve_parent(tag):
    """Return the immediate parent intermediate image name for a final tag."""
    agent, desktop, _ = parse_tag(tag)
    return f"_{agent}-{desktop}"


def generate_intermediates():
    """Return ordered list of all intermediate image names to build."""
    intermediates = ["_base"]
    desktops_needed = set()
    for a, d in _get_unique_agent_desktop_pairs():
        desktops_needed.add(d)
    for d in sorted(desktops_needed):
        intermediates.append(f"_base-{d}")
    for a, d in _get_unique_agent_desktop_pairs():
        intermediates.append(f"_{a}-{d}")
    return intermediates


def _resolve_intermediate_chain(target):
    """Return the build chain for an intermediate image."""
    if target == "_base":
        return [(os.path.join(SANDBOX_DIR, "Dockerfile.base"), "_base", None)]
    if target.startswith("_base-"):
        desktop = target[len("_base-"):]
        if desktop not in get_registry().desktops:
            raise ValueError(f"Unknown intermediate target: {target}")
        return [
            (os.path.join(SANDBOX_DIR, "Dockerfile.base"), "_base", None),
            (_plugin_dockerfile("desktop", desktop), target, "_base"),
        ]
    if target.startswith("_"):
        parts = target[1:].split("-")
        if len(parts) == 2:
            agent, desktop = parts
            reg = get_registry()
            if agent in reg.agents and desktop in reg.desktops:
                return [
                    (os.path.join(SANDBOX_DIR, "Dockerfile.base"), "_base", None),
                    (_plugin_dockerfile("desktop", desktop),
                     f"_base-{desktop}", "_base"),
                    (_plugin_dockerfile("agent", agent),
                     target, f"_base-{desktop}"),
                ]
    raise ValueError(f"Unknown intermediate target: {target}")


def _build_single(dockerfile, image_name, parent_name, no_cache=False,
                  base_image_override=None):
    """Build a single layer image."""
    tag = _image_tag(image_name)
    if not os.path.exists(dockerfile):
        print_error(f"Layer file not found: {dockerfile}")
        sys.exit(1)

    context = _build_context_for(dockerfile)
    cb = CommandBuilder("docker", "build").flag("--no-cache", when=no_cache)
    if base_image_override:
        cb.opt("--build-arg", f"BASE_IMAGE={base_image_override}")
    elif parent_name is not None:
        cb.opt("--build-arg", f"BASE_IMAGE={_image_tag(parent_name)}")
    cb.opt("-f", dockerfile).opt("-t", tag).positional(context)
    run_command(cb.build())


def build_layered(tag, no_cache=False, base_image=None):
    """Build a final image using FROM-chained layers, skipping cached intermediates.

    If ``base_image`` is provided, skip all intermediates and only build
    the final connector layer FROM the given base (CI mode: parent
    intermediate already pulled).
    """
    if base_image:
        agent, desktop, connector = parse_tag(tag)
        dockerfile = _plugin_dockerfile("connector", connector)
        print_info(f"  Building {_image_tag(tag)} (connector only, from {base_image})")
        _build_single(dockerfile, tag, None, no_cache=no_cache,
                      base_image_override=base_image)
        print_success(f"Built {_image_tag(tag)}")
        return

    chain = resolve_build_chain(tag)
    total = len(chain)
    for i, (dockerfile, image_name, parent_name) in enumerate(chain, 1):
        full_tag = _image_tag(image_name)
        if image_name != tag and not no_cache and _image_exists(full_tag):
            print_info(f"  [{i}/{total}] Cache hit: {full_tag}")
            continue
        layer_label = os.path.relpath(dockerfile)
        print_info(f"  [{i}/{total}] Building {full_tag} ({layer_label})")
        _build_single(dockerfile, image_name, parent_name, no_cache=no_cache)
    print_success(f"Built {_image_tag(tag)}")


def build_intermediates(no_cache=False):
    """Build all intermediate images in dependency order."""
    intermediates = generate_intermediates()
    total = len(intermediates)
    for i, name in enumerate(intermediates, 1):
        full_tag = _image_tag(name)
        if not no_cache and _image_exists(full_tag):
            print_info(f"  [{i}/{total}] Cache hit: {full_tag}")
            continue
        chain = _resolve_intermediate_chain(name)
        dockerfile, image_name, parent_name = chain[-1]
        layer_label = os.path.relpath(dockerfile)
        print_info(f"  [{i}/{total}] Building {full_tag} ({layer_label})")
        _build_single(dockerfile, image_name, parent_name, no_cache=no_cache)
    print_success(f"Built {total} intermediate images")


def build_layer_target(layer_type, target=None, no_cache=False):
    """Build up to a specific layer type. Used by ``--layer`` flag.

    ``layer_type`` is one of ``base``, ``desktop``, ``agent``,
    ``connector`` (connector = all finals).
    """
    if layer_type == "base":
        chain = _resolve_intermediate_chain("_base")
        dockerfile, image_name, parent_name = chain[-1]
        print_info(f"Building {_image_tag(image_name)}")
        _build_single(dockerfile, image_name, parent_name, no_cache=no_cache)
        print_success(f"Built {_image_tag(image_name)}")
        return

    if layer_type == "desktop":
        build_layer_target("base", no_cache=no_cache)
        desktops = [target] if target else list(DESKTOPS.keys())
        for d in desktops:
            name = f"_base-{d}"
            if not no_cache and _image_exists(_image_tag(name)):
                print_info(f"  Cache hit: {_image_tag(name)}")
                continue
            chain = _resolve_intermediate_chain(name)
            dockerfile, image_name, parent_name = chain[-1]
            print_info(f"Building {_image_tag(image_name)}")
            _build_single(dockerfile, image_name, parent_name, no_cache=no_cache)
        print_success("Desktop layer(s) built")
        return

    if layer_type == "agent":
        build_layer_target("desktop", no_cache=no_cache)
        if target:
            pairs = [tuple(target.split("-"))]
        else:
            pairs = _get_unique_agent_desktop_pairs()
        for a, d in pairs:
            name = f"_{a}-{d}"
            if not no_cache and _image_exists(_image_tag(name)):
                print_info(f"  Cache hit: {_image_tag(name)}")
                continue
            chain = _resolve_intermediate_chain(name)
            dockerfile, image_name, parent_name = chain[-1]
            print_info(f"Building {_image_tag(image_name)}")
            _build_single(dockerfile, image_name, parent_name, no_cache=no_cache)
        print_success("Agent layer(s) built")
        return

    if layer_type == "connector":
        build_intermediates(no_cache=no_cache)
        for tag in VALID_TAGS:
            chain = resolve_build_chain(tag)
            dockerfile, image_name, parent_name = chain[-1]
            print_info(f"Building {_image_tag(tag)} (connector)")
            _build_single(dockerfile, image_name, parent_name, no_cache=no_cache)
        print_success("All images built")
        return

    print_error(f"Unknown layer type: {layer_type}. Valid: base, desktop, agent, connector")
    sys.exit(1)


def build(args):
    """Builds the specified tag(s) using FROM-chained layered system."""
    import json as _json

    no_cache = getattr(args, "no_cache", False)

    if getattr(args, "list_intermediates", False):
        names = generate_intermediates()
        if getattr(args, "json_output", False):
            print(_json.dumps(names))
        else:
            for n in names:
                print(n)
        return

    layer = getattr(args, "layer", None)
    if layer:
        layer_target = getattr(args, "layer_target", None)
        print_header(
            f"Building layer: {layer}"
            + (f" ({layer_target})" if layer_target else "")
        )
        build_layer_target(layer, target=layer_target, no_cache=no_cache)
        return

    targets = args.variant if args.variant else [DEFAULT_TAG]
    if "all" in targets:
        print_header(f"Building all {len(VALID_TAGS)} images")
        print_info("Phase 1: Building intermediate layers...")
        build_intermediates(no_cache=no_cache)
        print_info("Phase 2: Building final images...")
        for tag in VALID_TAGS:
            build_layered(tag, no_cache=no_cache)
        print_success("All builds complete!")
        return

    print_header(f"Building: {', '.join(targets)}")
    for target in targets:
        try:
            parse_tag(target)
        except ValueError as e:
            print_error(str(e))
            sys.exit(1)
        build_layered(target, no_cache=no_cache)

    print_success("Build complete!")


def install(args):
    """Alias for build (in future may pull images from a registry)."""
    build(args)
