"""Metadane transportu bez zmiany czasu źródłowych pomiarów."""

import math
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
    """Łączy REST/BUS według czasu źródła; nowe błędy wygaszają stary odczyt."""
    rows = [dict(row) for row in payloads if isinstance(row, dict) and row]
    if not rows:
        return unavailable_snapshot(source=source, error="vision_obstacle_unavailable")
    for row in rows:
        if observation_time(row) is None:
            row["stale"] = True
            row.setdefault("error", "observation_time_unknown")
    known = [row for row in rows if observation_time(row) is not None]
    selected = max(known, key=observation_time) if known else rows[0]
    # Czasy odbioru porównujemy wyłącznie między sobą w domenie czasu PC.
    # Nie służą do odmładzania pomiaru ani do porównania z zegarem Pi.
    failures = [row for row in rows if _failed(row)]
    if failures:
        failure = max(failures, key=lambda row: _receipt_time(row) or 0)
        failure_time, selected_time = _receipt_time(failure), _receipt_time(selected)
        if (failure_time is not None and (selected_time is None or failure_time >= selected_time)) or (
            failure_time is None
            and (
                observation_time(failure) is None
                or not known
                or observation_time(failure) >= observation_time(selected)
            )
        ):
            selected = failure
    _source(selected, source)
    if "observed_at" not in selected and "ts" not in selected:
        selected["observed_at"] = None
    return selected
