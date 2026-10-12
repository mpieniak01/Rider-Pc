"""Metadane transportu bez zmiany czasu źródłowych pomiarów."""

from __future__ import annotations

import asyncio
import math
import time
from typing import Any


def adapter_source(adapter: Any) -> str:
    names = {cls.__name__ for cls in type(adapter).__mro__}
    return "demo" if "MockRestAdapter" in names else "pi"


def _time(value: Any) -> float | None:
    try:
        if type(value) in (int, float) and math.isfinite(value) and value > 0:
            return value
    except OverflowError:
        pass
    return None


def observation_time(row: dict) -> float | None:
    # Jawne null nie może wracać do starszego aliasu ts.
    return _time(row.get("observed_at") if "observed_at" in row else row.get("ts"))


def _source(row: dict, source: str) -> None:
    upstream = row.get("source")
    if upstream and (not isinstance(upstream, str) or upstream not in {"pi", "demo"}):
        row.setdefault("upstream_source", upstream)
    row["source"] = "demo" if source == "demo" or upstream == "demo" or row.get("simulated") is True else "pi"


def transport_failure(payload: Any) -> bool:
    """Adapter zwraca sam error; domena zwraca także swój rzeczywisty stan."""
    if not isinstance(payload, dict):
        return False
    error = payload.get("error")
    if isinstance(error, str) and (error in {"not_found", "invalid_json_type"} or error.startswith("json_decode:")):
        return False
    return bool(error) and set(payload) <= {"error", "ok", "_http_status", "attempted_at"}


def unavailable_snapshot(
    previous: Any = None,
    *,
    source: str = "pi",
    error: str = "snapshot_unavailable",
    attempted_at: float | None = None,
) -> dict:
    row = dict(previous) if isinstance(previous, dict) else {}
    _source(row, source)
    row.update(offline=True, stale=True, error=error, ok=False)
    if "observed_at" not in row and "ts" not in row:
        row["observed_at"] = None
    if attempted_at is not None:
        row["attempted_at"] = attempted_at
    # received_at pozostaje czasem ostatniej udanej odpowiedzi.
    return row


def received_snapshot(payload: dict, *, source: str, received_at: float) -> dict:
    row = dict(payload)
    _source(row, source)
    row["received_at"] = received_at
    row.pop("attempted_at", None)
    row.setdefault("offline", False)
    if row.get("error") or row.get("offline") is True:
        row["stale"] = True
        row["ok"] = False
    else:
        row.setdefault("stale", False)
    if "observed_at" not in row and "ts" not in row:
        row["observed_at"] = None
    return row


def cached_snapshot(cache: Any, key: str, *, source: str = "pi") -> dict:
    payload = cache.get(key)
    if not isinstance(payload, dict) or not payload:
        return unavailable_snapshot(source=source, error=f"{key}_unavailable")
    row = dict(payload)
    _source(row, source)
    return row


def _failed(row: dict) -> bool:
    quality = row.get("quality")
    return (
        row.get("offline") is True
        or row.get("stale") is True
        or bool(row.get("error"))
        or bool(row.get("data_error"))
        or row.get("data_ready") is False
        or ("quality" in row and quality is None)
        or (isinstance(quality, str) and quality.lower() in {"unknown", "unavailable", "invalid", "error", "failed"})
    )


def _receipt_time(row: dict) -> float | None:
    return _time(row.get("attempted_at")) or _time(row.get("received_at"))


def latest_observation(*payloads: Any, source: str = "pi") -> dict:
    """Wybiera poprawną obserwację; awaria jednego transportu nie wygasza drugiego."""
    rows = [dict(row) for row in payloads if isinstance(row, dict) and row]
    if not rows:
        return unavailable_snapshot(source=source, error="vision_obstacle_unavailable")
    for row in rows:
        if observation_time(row) is None:
            row["stale"] = True
            row.setdefault("error", "observation_time_unknown")
    healthy = [row for row in rows if observation_time(row) is not None and not _failed(row)]
    if healthy:
        selected = max(healthy, key=observation_time)
    else:
        # Czasy odbioru błędów porównujemy tylko w domenie czasu PC.
        # Nie służą do odmładzania pomiaru ani porównania z zegarem Pi.
        selected = max(rows, key=lambda row: _receipt_time(row) or 0)
    _source(selected, source)
    if "observed_at" not in selected and "ts" not in selected:
        selected["observed_at"] = None
    return selected


async def refresh_snapshot(app: Any, key: str, fetch: Any, *, reuse_s: float = 0.0) -> dict:
    """Jeden odczyt źródła dla równoległych klientów; wiek pomiaru pozostaje bez zmian."""
    cache = app.state.cache
    previous = cache.get(key)
    attempted = _receipt_time(previous) if isinstance(previous, dict) else None
    if attempted is not None and 0 <= time.time() - attempted < reuse_s:
        return cached_snapshot(cache, key, source=adapter_source(app.state.rest_adapter))
    flights = getattr(app.state, "snapshot_refresh_tasks", None)
    if flights is None:
        flights = app.state.snapshot_refresh_tasks = {}
    flight = flights.get(key)
    if flight is None or flight.done():
        generation = getattr(app.state, "snapshot_generation", 0)

        async def read():
            source = adapter_source(app.state.rest_adapter)
            try:
                payload = await fetch()
                if not isinstance(payload, dict) or not payload:
                    raise ValueError("invalid_snapshot_response")
                if transport_failure(payload):
                    raise RuntimeError(str(payload["error"]))
                row = received_snapshot(payload, source=source, received_at=time.time())
            except Exception as exc:
                row = unavailable_snapshot(
                    cache.get(key), source=source, error=str(exc) or type(exc).__name__, attempted_at=time.time()
                )
            if generation != getattr(app.state, "snapshot_generation", 0):
                return unavailable_snapshot(
                    row, source=source, error="observation_superseded", attempted_at=time.time()
                )
            cache.set(key, row)
            return row

        flight = flights[key] = asyncio.create_task(read())
    try:
        return await asyncio.shield(flight)
    finally:
        if flight.done() and flights.get(key) is flight:
            flights.pop(key, None)


def invalidate_snapshots(app):
    """Resource/task actions invalidate presentation reads, never arm or actuate."""
    app.state.snapshot_generation = getattr(app.state, "snapshot_generation", 0) + 1
    app.state.snapshot_refresh_tasks = {}
    cache = getattr(app.state, "cache", None)
    if cache is not None:
        for key in (
            "healthz",
            "camera_resource",
            "lcd_resource",
            "resource:mic",
            "resource:speaker",
            "resource:uart",
            "catalog",
            "vision_snap_info",
            "state",
        ):
            cache.delete(key)
    for key in list(getattr(app.state, "remote_snapshots", {})):
        if key == "catalog" or key.startswith("resource:"):
            app.state.remote_snapshots.pop(key, None)
    from pc_client.api.binary_snapshot import invalidate

    invalidate(app)
