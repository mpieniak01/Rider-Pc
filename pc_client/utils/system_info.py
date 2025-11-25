"""Utilities for collecting local Rider-PC host metrics."""

from __future__ import annotations

import os
import platform
import shutil
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
