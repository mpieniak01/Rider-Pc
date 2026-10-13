"""Weryfikacja koperty operatora bez odświeżania starej komendy."""

import math


class SafetyRefusal(ValueError):
    pass


def finite_number(value):
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        return False


class RemoteSafety:
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
        # Pi's sole executor validates generation, sequence, owner, TTL and
        # actuation readiness. A telemetry GET must not gate a new manual intent.
        return {k: body[k] for k in ("generation", "seq", "source", "ts", "ttl_ms")}
