"""Automatyczne testy nie mogą połączyć się z robotem ani otworzyć UART."""

import builtins
import importlib.abc
import io
import os
import socket
import re
import shlex
import sys
import subprocess
import tempfile
from pathlib import Path

from unittest.mock import patch


class AutomationIsolation:
    """Odwracalne blokady transportu i urządzeń dla narzędzi testowych."""

    def __init__(self):
        self._patches = []
        self._sandbox = None
        self._sdk_guard = None

    def setattr(self, target, name, value):
        patcher = patch.object(target, name, value)
        patcher.start()
        self._patches.append(patcher)

    def undo(self):
        for patcher in reversed(self._patches):
            patcher.stop()
        self._patches.clear()
        if self._sdk_guard in sys.meta_path:
            sys.meta_path.remove(self._sdk_guard)
        if self._sandbox:
            self._sandbox.cleanup()


class _RobotSDKBarrier(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {"xgolib", "xgoedu", "RPi", "spidev", "gpiod"}:
            raise PermissionError("Test isolation: real robot SDK forbidden; inject a mock")
        return None


def install_automation_isolation():
    # Ustawienie trybu nie zastępuje blokad poniżej.
    os.environ["TEST_MODE"] = "true"
    os.environ["GOOGLE_ASSISTANT_TEST_MODE"] = "true"
    for name in ("AUTO_HEAL_ENABLED", "ENABLE_PROVIDERS", "ENABLE_TASK_QUEUE"):
        os.environ[name] = "false"

    guard = AutomationIsolation()
    guard._sdk_guard = _RobotSDKBarrier()
    sys.meta_path.insert(0, guard._sdk_guard)
    if any(name in sys.modules for name in ("xgolib", "xgoedu", "spidev", "gpiod")):
        guard.undo()
        raise PermissionError("Test isolation: robot SDK was imported before guards")
    # Każdy interpreter potomny uruchamia bariery przed swoim kodem.
    guard._sandbox = tempfile.TemporaryDirectory(prefix="rider-pc-test-")
    sandbox = Path(guard._sandbox.name)
    (sandbox / "sitecustomize.py").write_text(
        "from pc_client.testing.isolation import install_automation_isolation\n"
        "_robot_test_guard = install_automation_isolation()\n"
    )
    project = Path(__file__).resolve().parents[2]
    child_pythonpath = os.pathsep.join((str(sandbox), str(project), os.environ.get("PYTHONPATH", "")))
    original_connect, original_connect_ex = socket.socket.connect, socket.socket.connect_ex

    def permitted(address):
        if not isinstance(address, tuple):
            return False
        host, port = address[:2]
        ports = {int(p) for p in os.getenv("RIDER_TEST_LOOPBACK_PORTS", "").split(",") if p.isdigit()}
        return host in {"127.0.0.1", "::1", "localhost"} and port in ports

    def connect(sock, address):
        if sock.family in {socket.AF_INET, socket.AF_INET6} and not permitted(address):
            raise PermissionError("Test isolation: real network/robot connections forbidden")
        return original_connect(sock, address)

    def connect_ex(sock, address):
        if sock.family in {socket.AF_INET, socket.AF_INET6} and not permitted(address):
            raise PermissionError("Test isolation: real network/robot connections forbidden")
        return original_connect_ex(sock, address)

    guard.setattr(socket.socket, "connect", connect)
    guard.setattr(socket.socket, "connect_ex", connect_ex)

    def guarded_open(original):
        def open_file(file, *args, **kwargs):
            path = os.fspath(file) if isinstance(file, (str, bytes, os.PathLike)) else ""
            if isinstance(path, bytes):
                path = os.fsdecode(path)
            if path.startswith(("/dev/tty", "/dev/serial", "/dev/spidev", "/dev/gpio", "/dev/i2c", "/dev/video")):
                raise PermissionError("Test isolation: hardware device access forbidden")
            return original(file, *args, **kwargs)

        return open_file

    guard.setattr(builtins, "open", guarded_open(builtins.open))
    guard.setattr(io, "open", guarded_open(io.open))
    guard.setattr(os, "open", guarded_open(os.open))
    original_popen = subprocess.Popen

    def popen(command, *args, **kwargs):
        parts = shlex.split(command) if isinstance(command, str) else [str(p) for p in command]
        executable = os.path.basename(parts[0]) if parts else ""
        python_child = re.fullmatch(r"python(?:3(?:\.\d+)?)?", executable) is not None
        if kwargs.get("shell") or (
            not python_child and executable not in {"git", "node", "ffmpeg", "ffprobe", "which"}
        ):
            raise PermissionError("Test isolation: unapproved child executable/shell forbidden")
        if python_child:
            if any(flag in parts for flag in ("-I", "-E", "-S", "-Es", "-IS", "-IE")):
                raise PermissionError("Test isolation: child Python cannot disable guards")
            child_env = dict(kwargs.get("env") or os.environ)
            child_env["PYTHONPATH"] = child_pythonpath
            child_env["TEST_MODE"] = "true"
            for name in ("AUTO_HEAL_ENABLED", "ENABLE_PROVIDERS", "ENABLE_TASK_QUEUE"):
                child_env[name] = "false"
            child_env["RIDER_TEST_LOOPBACK_PORTS"] = os.getenv("RIDER_TEST_LOOPBACK_PORTS", "")
            kwargs["env"] = child_env
        forbidden = {"ssh", "scp", "sftp", "rsync", "systemctl", "fuser", "sudo", "curl", "wget", "gh"}
        if any(os.path.basename(p) in forbidden for p in parts):
            raise PermissionError("Test isolation: real host/service actions forbidden")
        if parts and os.path.basename(parts[0]) == "git":
            target = Path(kwargs.get("cwd") or os.getcwd()).resolve()
            if "-C" in parts:
                target = Path(parts[parts.index("-C") + 1]).resolve()
            network = {"push", "pull", "fetch", "clone", "ls-remote"}
            mutation = {
                "add",
                "commit",
                "checkout",
                "switch",
                "branch",
                "merge",
                "reset",
                "clean",
                "stash",
                "update-ref",
                "worktree",
                "tag",
            }
            temporary = Path(tempfile.gettempdir()).resolve()
            if network.intersection(parts) or (mutation.intersection(parts) and not target.is_relative_to(temporary)):
                raise PermissionError("Test isolation: repository mutation/network forbidden")
        return original_popen(command, *args, **kwargs)

    guard.setattr(subprocess, "Popen", popen)

    def deny_shell(*args, **kwargs):
        raise PermissionError("Test isolation: unmocked shell forbidden")

    guard.setattr(os, "system", deny_shell)

    try:
        import zmq
        import zmq.asyncio

        def deny_bus(*args, **kwargs):
            raise PermissionError("Test isolation: real ZMQ BUS forbidden")

        guard.setattr(zmq.Socket, "connect", deny_bus)
        guard.setattr(zmq.Socket, "bind", deny_bus)
        guard.setattr(zmq.asyncio.Socket, "connect", deny_bus)
        guard.setattr(zmq.asyncio.Socket, "bind", deny_bus)
    except ImportError:
        pass

    return guard
