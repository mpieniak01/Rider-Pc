"""Network diagnostic utilities for Rider-PC.

This module provides asynchronous network utilities for checking connectivity
to remote hosts. Uses async subprocess calls to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
import logging
import platform
import re
import socket
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def get_local_ip() -> str:
    """Get the local IP address of the LAN interface.

    Returns:
        The local IP address as a string. Returns "127.0.0.1" if unable
        to determine the actual LAN IP address.
    """
    try:
        # Create a socket and connect to an external address
        # This will reveal which interface would be used without actually sending data
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # Use Google's DNS as target - no actual connection is made
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            return local_ip
    except (OSError, socket.error) as e:
        logger.warning("Failed to determine local IP address: %s", e)
        return "127.0.0.1"


def _build_ping_command(host: str) -> list[str]:
    """Build the ping command based on the operating system.

    Args:
        host: The host to ping.

    Returns:
        A list of command arguments for the ping command.
    """
    system = platform.system().lower()

    if system == "windows":
        # Windows: -n count, -w timeout in milliseconds
        return ["ping", "-n", "1", "-w", "1000", host]
    else:
        # Linux/macOS: -c count, -W timeout in seconds
        return ["ping", "-c", "1", "-W", "1", host]


def _parse_ping_latency(output: str) -> Optional[float]:
    """Parse latency from ping output.

    Args:
        output: The stdout from ping command.

    Returns:
        Latency in milliseconds, or None if parsing fails.
    """
    # Try common patterns for extracting time from ping output
    # Linux/macOS: "time=X.XXX ms" or "time=X ms"
    # Windows: "time=Xms" or "time<1ms"
    patterns = [
        r"time[=<](\d+\.?\d*)\s*ms",  # General pattern
        r"(\d+\.?\d*)\s*ms",  # Fallback: any number followed by ms
    ]

    for pattern in patterns:
        match = re.search(pattern, output, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                continue

    return None


async def check_connectivity(host: str, port: int = 80) -> Dict[str, Any]:
    """Check connectivity to a remote host using ping.

    This function runs an asynchronous ping command to check if a host
    is reachable. It uses asyncio subprocess to avoid blocking.

    Args:
        host: The hostname or IP address to check.
        port: The port number (unused for ping, kept for interface compatibility).

    Returns:
        A dictionary with:
        - status: "online" or "offline"
        - latency_ms: Latency in milliseconds (only if online)
    """
    if not host:
        return {"status": "offline"}

    cmd = _build_ping_command(host)

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=2.0  # 2 second overall timeout
            )
        except asyncio.TimeoutError:
            # Kill the process if it times out
            try:
                process.kill()
                await process.wait()
            except ProcessLookupError:
                pass
            logger.debug("Ping to %s timed out", host)
            return {"status": "offline"}

        stdout_str = stdout.decode("utf-8", errors="replace")

        if process.returncode == 0:
            latency = _parse_ping_latency(stdout_str)
            result: Dict[str, Any] = {"status": "online"}
            if latency is not None:
                result["latency_ms"] = latency
            return result
        else:
            logger.debug("Ping to %s failed with return code %d", host, process.returncode)
            return {"status": "offline"}

    except FileNotFoundError:
        logger.warning("Ping command not found on this system")
        return {"status": "offline"}
    except Exception as e:
        logger.warning("Error checking connectivity to %s: %s", host, e)
        return {"status": "offline"}


__all__ = ["get_local_ip", "check_connectivity"]
