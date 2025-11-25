"""Utilities for collecting local Rider-PC host metrics."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import time
from typing import Any, Dict, Optional

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    psutil = None  # type: ignore


def _safe_call(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _mb(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return float(value) / (1024 * 1024)


def _gb(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return float(value) / (1024 * 1024 * 1024)


def _parse_os_release_file(path: str) -> Dict[str, str]:
    data: Dict[str, str] = {}
    if not os.path.exists(path):
        return data
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                data[key.strip()] = value.strip().strip('"')
    except Exception:
        return {}
    return data


def _read_first_line(path: str) -> str:
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            line = handle.readline()
            return line.strip()
    except Exception:
        return ""


def _collect_os_release_meta() -> Dict[str, str]:
    meta: Dict[str, str] = {}
    freedesktop = getattr(platform, "freedesktop_os_release", None)
    if callable(freedesktop):
        fd_data = _safe_call(freedesktop)
        if fd_data:
            meta.update(fd_data)

    os_release_data = _parse_os_release_file("/etc/os-release")
    if os_release_data:
        meta.update(os_release_data)

    lsb_desc = _safe_call(lambda: subprocess.check_output(["lsb_release", "-ds"], text=True).strip().strip('"'))
    if lsb_desc:
        meta.setdefault("PRETTY_NAME", lsb_desc)

    lsb_release = _safe_call(lambda: subprocess.check_output(["lsb_release", "-rs"], text=True).strip())
    debian_version = _read_first_line("/etc/debian_version")

    pretty = meta.get("PRETTY_NAME")
    name = meta.get("NAME") or meta.get("ID") or (lsb_desc if lsb_desc else None)
    version = (
        meta.get("VERSION")
        or meta.get("VERSION_ID")
        or lsb_release
        or (debian_version if name and "debian" in name.lower() else None)
    )
    codename = meta.get("VERSION_CODENAME") or meta.get("UBUNTU_CODENAME")

    distribution_parts = [pretty or name, version or codename]
    distribution = " ".join(part for part in distribution_parts if part)

    result: Dict[str, str] = {}
    if pretty:
        result["os_release"] = pretty
    if distribution:
        result["distribution"] = distribution
    if name:
        result["distribution_name"] = name
    if version or codename:
        result["distribution_version"] = version or codename
    if meta.get("ID_LIKE"):
        result["distribution_family"] = meta["ID_LIKE"]
    return result


def collect_system_metrics() -> Dict[str, Any]:
    """
    Gather system metrics for the PC host.

    Returns:
        Dict with CPU/memory/disk stats (floats) and timestamps.
    """
    data: Dict[str, Any] = {
        "hostname": platform.node(),
        "platform": platform.platform(),
        "timestamp": time.time(),
    }
    data.update(_collect_os_release_meta())

    if psutil:
        data["cpu_pct"] = _safe_call(lambda: psutil.cpu_percent(interval=None))
        vm = _safe_call(psutil.virtual_memory)
        if vm:
            data["mem_total_mb"] = _mb(vm.total)
            data["mem_used_mb"] = _mb(vm.used)
            data["mem_pct"] = vm.percent

        disk = _safe_call(lambda: psutil.disk_usage("/"))
        if disk:
            data["disk_total_gb"] = _gb(disk.total)
            data["disk_used_gb"] = _gb(disk.used)
            data["disk_pct"] = disk.percent

        boot_time = _safe_call(psutil.boot_time)
        if boot_time:
            data["uptime_s"] = max(0.0, time.time() - float(boot_time))

        temps = _safe_call(psutil.sensors_temperatures)
        if temps:
            # pick first temperature entry if available
            for readings in temps.values():
                if readings:
                    current = readings[0].current
                    if current is not None:
                        data["temp_c"] = current
                        break

    # Fallbacks when psutil is missing or certain calls failed
    if "mem_total_mb" not in data or "mem_used_mb" not in data:
        try:
            total, used, free = shutil.disk_usage("/")
            data.setdefault("disk_total_gb", _gb(total))
            data.setdefault("disk_used_gb", _gb(total - free))
        except Exception:
            pass

    try:
        load1, load5, load15 = os.getloadavg()
        data["load1"] = load1
        data["load5"] = load5
        data["load15"] = load15
    except (OSError, AttributeError):
        pass

    return {k: v for k, v in data.items() if v is not None}


__all__ = ["collect_system_metrics"]
