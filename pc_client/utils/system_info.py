"""Utilities for collecting local Rider-PC host metrics."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import time
from typing import Any, Callable, Dict, Optional, TypeVar, cast

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    psutil = None  # type: ignore


T = TypeVar("T")


def _safe_call(fn: Callable[[], T], default: T) -> T:
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
        fd_data: Dict[str, str] = _safe_call(freedesktop, {})
        if fd_data:
            meta.update(fd_data)

    os_release_data = _parse_os_release_file("/etc/os-release")
    if os_release_data:
        meta.update(os_release_data)

    raw_lsb_desc = _safe_call(lambda: subprocess.check_output(["lsb_release", "-ds"], text=True).strip().strip('"'), "")
    lsb_desc = raw_lsb_desc.strip() if raw_lsb_desc else ""
    if lsb_desc:
        meta.setdefault("PRETTY_NAME", lsb_desc)

    raw_lsb_release = _safe_call(lambda: subprocess.check_output(["lsb_release", "-rs"], text=True).strip(), "")
    lsb_release = raw_lsb_release.strip() if raw_lsb_release else ""
    debian_version = _read_first_line("/etc/debian_version")

    pretty = meta.get("PRETTY_NAME")
    name: Optional[str] = meta.get("NAME") or meta.get("ID") or (lsb_desc if lsb_desc else None)
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
        distribution_name: str = name
        result["distribution_name"] = distribution_name
    if version or codename:
        distribution_version: str = cast(str, version or codename)
        result["distribution_version"] = distribution_version
    if meta.get("ID_LIKE"):
        result["distribution_family"] = meta["ID_LIKE"]
    return result


def _collect_gpu_metrics() -> Dict[str, Any]:
    """
    Collect GPU utilization/memory statistics if nvidia-smi is available.

    Returns:
        Dict with gpu_util_pct, gpu_mem_used_mb, gpu_mem_total_mb, gpu_mem_pct
    """
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return {}

    query = ["memory.used", "memory.total", "utilization.gpu"]
    try:
        output = subprocess.check_output(
            [nvidia_smi, f"--query-gpu={','.join(query)}", "--format=csv,noheader,nounits"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.SubprocessError, FileNotFoundError, PermissionError):
        return {}

    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return {}

    parts = [part.strip() for part in lines[0].split(",")]
    if len(parts) < 3:
        return {}

    def _to_float(value: str) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    used_mb = _to_float(parts[0])
    total_mb = _to_float(parts[1])
    util_pct = _to_float(parts[2])

    gpu_data: Dict[str, Any] = {}
    if util_pct is not None:
        gpu_data["gpu_util_pct"] = util_pct
    if used_mb is not None:
        gpu_data["gpu_mem_used_mb"] = used_mb
    if total_mb is not None and total_mb > 0:
        gpu_data["gpu_mem_total_mb"] = total_mb
        pct = (used_mb / total_mb) * 100 if used_mb is not None else None
        if pct is not None:
            gpu_data["gpu_mem_pct"] = pct

    return gpu_data


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
        data["cpu_pct"] = _safe_call(lambda: psutil.cpu_percent(interval=None), 0.0)
        vm = _safe_call(psutil.virtual_memory, None)
        if vm:
            data["mem_total_mb"] = _mb(vm.total)
            data["mem_used_mb"] = _mb(vm.used)
            data["mem_pct"] = vm.percent

        disk = _safe_call(lambda: psutil.disk_usage("/"), None)
        if disk:
            data["disk_total_gb"] = _gb(disk.total)
            data["disk_used_gb"] = _gb(disk.used)
            data["disk_pct"] = disk.percent

        boot_time = _safe_call(psutil.boot_time, 0.0)
        if boot_time:
            data["uptime_s"] = max(0.0, time.time() - float(boot_time))

        temps: Dict[str, Any] = _safe_call(psutil.sensors_temperatures, {})
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

    gpu_metrics = _collect_gpu_metrics()
    if gpu_metrics:
        data.update(gpu_metrics)

    return {k: v for k, v in data.items() if v is not None}


__all__ = ["collect_system_metrics"]
