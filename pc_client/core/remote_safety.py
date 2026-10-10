"""Weryfikacja koperty operatora bez odświeżania starej komendy."""

import asyncio
import math
import time


class SafetyRefusal(ValueError):
    pass


def finite_number(value):
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        return False


class RemoteSafety:
    def __init__(self):
        self._lock = asyncio.Lock()

    async def command_context(self, adapter, owner=None, require_armed=True, supplied=None):
        if adapter is None:
            raise SafetyRefusal("pi_offline")
        body = supplied or {}
        generation, seq, ts, ttl = (body.get(k) for k in ("generation", "seq", "ts", "ttl_ms"))
        if (
            not isinstance(generation, (str, int))
            or isinstance(generation, bool)
            or generation == ""
            or not isinstance(seq, int)
            or isinstance(seq, bool)
            or seq < 0
            or not finite_number(ts)
            or not isinstance(ttl, int)
            or isinstance(ttl, bool)
            or not 1 <= ttl <= 500
            or body.get("source") != "manual"
        ):
            raise SafetyRefusal("explicit_fresh_operator_envelope_required")
        async with self._lock:
            response = await adapter.get_control_state()
            if not isinstance(response, dict) or not isinstance(response.get("safety"), dict):
                raise SafetyRefusal("unconfirmed_safety")
            safety = response["safety"]
            observed_at = safety.get("observed_at")
            # Timestamp z UI należy do domeny czasu Pi (handshake). Walidacja
            # porównuje zegary; nigdy nie zmienia ts/generacji samej komendy.
            remote_now = response.get("server_time")
            now = remote_now if finite_number(remote_now) else time.time()
            if (
                response.get("stale") is True
                or response.get("offline") is True
                or safety.get("stale") is True
                or type(safety.get("contract_version")) is not int
                or safety["contract_version"] != 1
                or safety.get("state") not in {"ARMED", "DISARMED", "ESTOP"}
                or not finite_number(observed_at)
                or not -0.1 <= now - observed_at <= 3
            ):
                raise SafetyRefusal("unconfirmed_safety")
            if require_armed and (
                safety.get("state") != "ARMED"
                or safety.get("read_only") is not False
                or safety.get("ready") is not True
                or safety.get("can_move") is not True
            ):
                raise SafetyRefusal("unconfirmed_safety")
            if require_armed and owner is not None and safety.get("owner") != owner:
                raise SafetyRefusal("control_owner_mismatch")
            if safety.get("generation") != generation:
                raise SafetyRefusal("obsolete_generation")
            last_seq = safety.get("last_seq", 0)
            if not isinstance(last_seq, int) or isinstance(last_seq, bool) or seq <= last_seq:
                raise SafetyRefusal("obsolete_sequence")
            if not -0.1 <= now - ts <= ttl / 1000:
                raise SafetyRefusal("expired_operator_envelope")
            return {k: body[k] for k in ("generation", "seq", "source", "ts", "ttl_ms")}
