"""Builtin hooks implementing the up-lifecycle.

Each hook is a plain ``hook(ctx) -> None`` that mirrors a slice of the
legacy inline ``up()`` body. Data flows through :class:`UpContext`
(defined in :mod:`orchestrator`) rather than local variables, so the
kernel can be unit-tested with stubs in place of Docker / FS calls.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from actions import RunSubprocess  # type: ignore[import-not-found]
from command import CommandBuilder  # type: ignore[import-not-found]
from eventbus import EventBus  # type: ignore[import-not-found]
from phase import Phase  # type: ignore[import-not-found]


def validate_inputs(ctx) -> None:
    """UP_VALIDATE: project / username sanity checks."""
    ctx.deps.validate_project_name(ctx.project)
    ctx.deps.validate_username(ctx.host_user)


def gen_main_compose(ctx) -> None:
    """UP_COMPOSE/100: primary tag-derived compose file."""
    path, _ = ctx.deps.generate_compose_for_tag(str(ctx.tag))
    ctx.compose_files.append(Path(path))


def gen_git_compose(ctx) -> None:
    """UP_COMPOSE/200: optional git-context overlay."""
    git = ctx.deps.generate_git_compose(ctx.host_user, ctx.service_name)
    if git:
        ctx.compose_files.append(Path(git))
        ctx.reporter.info("Git Context Sharing Enabled")


def gen_resource_compose(ctx) -> None:
    """UP_COMPOSE/300: optional cpus/memory overlay."""
    cpus = ctx.env.get("_REQ_CPUS")
    memory = ctx.env.get("_REQ_MEMORY")
    if not cpus and not memory:
        return
    out = ctx.deps.generate_resource_compose(cpus, memory, ctx.service_name)
    if out:
        ctx.compose_files.append(Path(out))
        ctx.reporter.info("Resource Limits Applied")


def auto_port_alloc(ctx) -> None:
    """UP_PORT_ALLOC: explicit / ephemeral / auto-fallback decision.

    Mirrors legacy logic exactly: a custom ``--name`` switches every
    non-explicit default to ``"0"``; the default project switches only
    when the default port is already taken (with a warning).
    """
    rp = ctx.requested_ports
    ssh, kasm, vnc, novnc = rp.ssh, rp.kasm, rp.vnc, rp.novnc
    is_busy = ctx.deps.is_port_in_use

    if ctx.project != "sanity-gravity":
        if not rp.ssh_explicit and ssh == "2222":
            ssh = "0"
        if not rp.kasm_explicit and kasm == "8444":
            kasm = "0"
        if not rp.vnc_explicit and vnc == "5901":
            vnc = "0"
        if not rp.novnc_explicit and novnc == "6901":
            novnc = "0"
    else:
        if not rp.ssh_explicit and ssh == "2222" and is_busy(2222):
            ctx.reporter.warning("Default SSH port 2222 is busy. Switching to ephemeral.")
            ssh = "0"
        if not rp.kasm_explicit and kasm == "8444" and is_busy(8444):
            ctx.reporter.warning("Default Kasm port 8444 is busy. Switching to ephemeral.")
            kasm = "0"
        if not rp.vnc_explicit and vnc == "5901" and is_busy(5901):
            ctx.reporter.warning("Default VNC port 5901 is busy. Switching to ephemeral.")
            vnc = "0"
        if not rp.novnc_explicit and novnc == "6901" and is_busy(6901):
            ctx.reporter.warning("Default noVNC port 6901 is busy. Switching to ephemeral.")
            novnc = "0"

    ctx.resolved_ports = {"ssh": ssh, "kasm": kasm, "vnc": vnc, "novnc": novnc}
    ctx.env.update({
        "SSH_HOST_PORT": ssh, "KASM_PORT": kasm,
        "VNC_PORT": vnc, "NOVNC_PORT": novnc,
        "HOST_UID": str(ctx.host_uid), "HOST_GID": str(ctx.host_gid),
        "HOST_USER": ctx.host_user, "HOST_PASSWORD": ctx.password,
        "VNC_PW": ctx.password, "WORKSPACE_DIR": str(ctx.workspace),
    })

    if ctx.image_override:
        var = f"SANITY_IMAGE_{str(ctx.tag).upper().replace('-', '_')}"
        os.environ[var] = ctx.image_override
        ctx.reporter.info(f"Using Custom Image: {ctx.image_override} for {ctx.tag}")


def _compose_cmd(ctx, *action: str) -> tuple[str, ...]:
    cb = CommandBuilder("docker", "compose", "-p", ctx.project)
    for cf in ctx.compose_files:
        cb.opt("-f", str(cf))
    cb.positional(*action)
    return cb.build()


def docker_compose_up(ctx) -> None:
    """UP_DOCKER/100: enqueue the ``compose up`` action."""
    env = {k: v for k, v in ctx.env.items() if not k.startswith("_")}
    ctx.actions.append(RunSubprocess(
        argv=_compose_cmd(ctx, "up", "-d", ctx.service_name),
        env=env,
    ))


def resolve_ephemeral(ctx) -> None:
    """UP_DOCKER/200: replace ``"0"`` ports with what Docker actually bound.

    Direct ``run_command`` callable on purpose: the hook needs the
    captured stdout to feed back into ``ctx.resolved_ports``. Wrapping
    this as a typed Action with result piping is a future refinement.
    """
    rp = ctx.resolved_ports
    if "0" not in (rp.get("ssh"), rp.get("kasm"), rp.get("vnc"), rp.get("novnc")):
        return
    if getattr(ctx, "dry_run", False):
        ctx.reporter.info("Resolving ephemeral ports... (skipped in dry-run)")
        return

    ctx.reporter.info("Resolving ephemeral ports...")

    def _get(internal: str) -> str:
        try:
            out = ctx.deps.run_command(
                _compose_cmd(ctx, "port", ctx.service_name, internal), capture=True,
            )
            if isinstance(out, str) and ":" in out:
                return out.split(":")[-1]
        except (subprocess.CalledProcessError, SystemExit) as e:
            ctx.reporter.warning(
                f"Could not resolve {ctx.service_name}:{internal} port ({e})"
            )
        return "?"

    ctx.resolved_ports["ssh"] = _get("22")
    if ctx.tag.connector == "kasm":
        ctx.resolved_ports["kasm"] = _get("8444")
    elif ctx.tag.connector == "vnc":
        ctx.resolved_ports["vnc"] = _get("5901")
        ctx.resolved_ports["novnc"] = _get("6901")


def sync_config_hook(ctx) -> None:
    """UP_PROVISION: push the host's ``./config/`` into the container.

    Direct ``deps.sync_config`` callable for now — the function mixes
    interactive prompts, file copies, and a tar pipe that need shell.
    Splitting into Actions is tracked in PR #6 backlog.
    """
    if getattr(ctx, "dry_run", False):
        ctx.reporter.info(
            f"» would: sync host config → {ctx.container_name} (skipped in dry-run)"
        )
        return
    ctx.deps.sync_config(ctx.project, ctx.container_name, ctx.host_user)


def announce(ctx) -> None:
    """UP_ANNOUNCE: emit AccessInfo + final success line.

    Field labels include the colon + padding so AnsiSink renders byte-
    identically to the legacy inline prints.

    In dry-run mode, no container exists and ephemeral ports were not
    resolved, so emit a single planned-outcome summary instead of the
    misleading success + access block.
    """
    rp = ctx.resolved_ports
    user = ctx.host_user
    if getattr(ctx, "dry_run", False):
        ports_summary = ", ".join(
            f"{name}={value if value != '0' else '<ephemeral>'}"
            for name, value in rp.items()
        )
        ctx.reporter.info(
            f"» would announce: {ctx.tag} ({ctx.tag.connector}) — "
            f"ports: {ports_summary}"
        )
        return
    ctx.reporter.success(f"{ctx.tag} is running.")
    if ctx.tag.connector == "kasm":
        ctx.reporter.access("kasm", {
            "URL:      ": f"https://localhost:{rp['kasm']}",
            "SSH:      ": f"ssh -p {rp['ssh']} {user}@localhost",
            "User:     ": user,
            "Pass:     ": ctx.password,
        })
    elif ctx.tag.connector == "vnc":
        ctx.reporter.access("vnc", {
            "VNC Client: ": f"localhost:{rp['vnc']}",
            "noVNC Web:  ": f"http://localhost:{rp['novnc']}/vnc.html",
            "SSH:        ": f"ssh -p {rp['ssh']} {user}@localhost",
            "Password:   ": ctx.password,
        })
    elif ctx.tag.connector == "ssh":
        ctx.reporter.access("ssh", {
            "SSH:        ": f"ssh -p {rp['ssh']} {user}@localhost",
            "Pass:       ": ctx.password,
            "Shell:      ": (
                f"docker exec -it -u {user} {ctx.container_name} /bin/bash"
            ),
        })


def register_builtin_up_hooks(bus: EventBus) -> None:
    """Subscribe builtin up hooks. Priorities (100/200/300) are spaced
    so plugin hooks can slot in between without renumbering."""
    bus.subscribe(Phase.UP_VALIDATE, validate_inputs, priority=100)
    bus.subscribe(Phase.UP_COMPOSE, gen_main_compose, priority=100)
    bus.subscribe(Phase.UP_COMPOSE, gen_git_compose, priority=200)
    bus.subscribe(Phase.UP_COMPOSE, gen_resource_compose, priority=300)
    bus.subscribe(Phase.UP_PORT_ALLOC, auto_port_alloc, priority=100)
    bus.subscribe(Phase.UP_DOCKER, docker_compose_up, priority=100)
    bus.subscribe(Phase.UP_DOCKER, resolve_ephemeral, priority=200)
    bus.subscribe(Phase.UP_PROVISION, sync_config_hook, priority=100)
    bus.subscribe(Phase.UP_ANNOUNCE, announce, priority=100)
