"""``build`` / ``install`` verbs: kernel-driven layered Docker image build.

The phase loop ``build.plan → build.layer → build.done`` is published by
:class:`Orchestrator`; per-phase behaviour lives in :mod:`build_hooks`.

A few legacy helpers (``resolve_build_chain``, ``build_layered``, etc.)
are re-exported as thin shims so external callers / tests that import
them keep working — the implementations now live in :mod:`build_hooks`.
"""
from __future__ import annotations

import atexit
import json as _json
import sys

from sanity_gravity.cli.io import (
    get_reporter,
    print_error,
    print_header,
)
from sanity_gravity.cli.registry import DEFAULT_TAG, VALID_TAGS, parse_tag
from sanity_gravity.core.eventbus import EventBus
from sanity_gravity.core.orchestrator import (
    BuildContext,
    Orchestrator,
    _BUILD_PHASES,
)
from sanity_gravity.effects.actions import ActionFailedError
from sanity_gravity.effects.executor import build_default_executor
from sanity_gravity.hooks.build import (
    SANDBOX_DIR,
    IMAGE_PREFIX,
    _generate_intermediates,
    _image_exists,
    _image_tag,
    _plugin_dockerfile,
    _resolve_build_chain,
    _resolve_intermediate_chain,
    register_builtin_build_hooks,
)


# Re-exports for legacy callers ----------------------------------------------

def resolve_build_chain(tag):  # pragma: no cover - thin shim
    return _resolve_build_chain(tag)


def resolve_parent(tag):
    agent, desktop, _ = parse_tag(tag)
    return f"_{agent}-{desktop}"


def generate_intermediates():
    return _generate_intermediates()


# ---------------------------------------------------------------------------


def build(args):
    """Build the requested tag(s) by routing through the microkernel."""
    no_cache = bool(getattr(args, "no_cache", False))

    # ``--list-intermediates`` is a read-only print: don't go through the
    # kernel for it.
    if getattr(args, "list_intermediates", False):
        names = _generate_intermediates()
        if getattr(args, "json_output", False):
            print(_json.dumps(names))
        else:
            for n in names:
                print(n)
        return

    layer = getattr(args, "layer", None)
    layer_target = getattr(args, "layer_target", None)
    targets = list(args.variant) if getattr(args, "variant", None) else [DEFAULT_TAG]

    if layer:
        print_header(
            f"Building layer: {layer}"
            + (f" ({layer_target})" if layer_target else "")
        )
    elif "all" in targets:
        print_header(f"Building all {len(VALID_TAGS)} images")
    else:
        # Validate eagerly so a bad tag aborts before we set up the kernel.
        for target in targets:
            try:
                parse_tag(target)
            except ValueError as e:
                print_error(str(e))
                sys.exit(1)
        print_header(f"Building: {', '.join(targets)}")

    reporter = getattr(args, "reporter", None) or get_reporter()
    dry_run = bool(getattr(args, "dry_run", False))

    ctx = BuildContext(
        targets=targets,
        reporter=reporter,
        no_cache=no_cache,
        layer_target=layer,
        layer_target_specific=layer_target,
        list_intermediates=False,
        json_output=bool(getattr(args, "json_output", False)),
        dry_run=dry_run,
    )

    bus = EventBus()
    register_builtin_build_hooks(bus)

    executor = build_default_executor(reporter, dry_run=dry_run)
    atexit.register(executor.close)

    try:
        Orchestrator(bus, reporter, executor=executor).run(_BUILD_PHASES, ctx)
    except ActionFailedError as e:
        sys.exit(e.result.exit_code or 1)


def install(args):
    """Alias for build (in future may pull images from a registry)."""
    build(args)


def explain_build(args):
    """``explain build`` alias: dry-run the plan without executing."""
    args.dry_run = True
    return build(args)


# Legacy thin wrappers re-exposed for callers that still import them
# directly. New code should construct a BuildContext + Orchestrator.

def _build_single(dockerfile, image_name, parent_name, no_cache=False,
                  base_image_override=None):  # pragma: no cover - legacy
    """Legacy single-layer build helper. Routed through the kernel via a
    one-step ``BuildContext``."""
    from sanity_gravity.cli.io import run_command  # local import to avoid cycle
    from sanity_gravity.core.command import CommandBuilder

    cb = CommandBuilder("docker", "build").flag("--no-cache", when=no_cache)
    if base_image_override:
        cb.opt("--build-arg", f"BASE_IMAGE={base_image_override}")
    elif parent_name is not None:
        cb.opt("--build-arg", f"BASE_IMAGE={_image_tag(parent_name)}")
    import os as _os
    if dockerfile.endswith("Dockerfile.base"):
        context = SANDBOX_DIR
    else:
        context = _os.path.dirname(dockerfile)
    cb.opt("-f", dockerfile).opt("-t", _image_tag(image_name)).positional(context)
    run_command(cb.build())


def build_layered(tag, no_cache=False, base_image=None):  # pragma: no cover - legacy
    """Legacy entry point preserved for any external caller."""
    class _Args:
        variant = [tag]
        no_cache = bool(no_cache)
        layer = None
        layer_target = None
        list_intermediates = False
        json_output = False
        dry_run = False
    args = _Args()
    if base_image:
        # Set as override on the ctx through the kernel via a synthetic ctx.
        reporter = get_reporter()
        ctx = BuildContext(
            targets=[tag],
            reporter=reporter,
            no_cache=no_cache,
            base_image_override=base_image,
        )
        bus = EventBus()
        register_builtin_build_hooks(bus)
        executor = build_default_executor(reporter, dry_run=False)
        atexit.register(executor.close)
        Orchestrator(bus, reporter, executor=executor).run(_BUILD_PHASES, ctx)
        return
    build(args)


def build_intermediates(no_cache=False):  # pragma: no cover - legacy
    """Legacy: build all intermediates."""
    class _Args:
        variant = ["all"]
        no_cache = bool(no_cache)
        layer = "agent"  # all intermediates: base + desktops + agents
        layer_target = None
        list_intermediates = False
        json_output = False
        dry_run = False
    build(_Args())


def build_layer_target(layer_type, target=None, no_cache=False):  # pragma: no cover
    """Legacy: build up to a specific layer type."""
    class _Args:
        variant = []
        no_cache = bool(no_cache)
        layer = layer_type
        layer_target = target
        list_intermediates = False
        json_output = False
        dry_run = False
    build(_Args())
