"""Negocjacja kontraktów HTTP i zachowanie zegara źródła w proxy PC."""

from __future__ import annotations

import json
import time
from typing import Any

from starlette.responses import JSONResponse

ACCEPT = "application/vnd.rider.api+json;version=1"
MEDIA_TYPE = "application/vnd.rider.api+json"
FAMILIES = set(
    "safety telemetry system health catalog tasks services service_graph resources frames obstacle navigation odometry calibration providers voice chat face models google_feed home api_metrics version network mcp project knowledge assistant http".split()
)
VERSIONS = {"rider.catalog": 2, "rider.tasks": 2, "rider.services": 2, "rider.service_graph": 2}


def family(path: str) -> str:
    if path in {"/api/status", "/api/metrics"}:
        return "rider.system"
    for prefixes, name in (
        (
            (
                "/api/control",
                "/api/safety",
                "/api/motion",
                "/api/flags",
                "/api/stop",
                "/api/cmd",
                "/api/move",
                "/api/balance",
                "/api/height",
                "/control",
            ),
            "safety",
        ),
        (("/api/vision/tracking", "/api/vision/follow", "/vision/tracking", "/vision/follow"), "tasks"),
        (("/face/", "/api/draw/face", "/draw/face"), "face"),
        (("/api/calibration",), "calibration"),
        (("/api/odometry",), "odometry"),
        (("/api/navigator",), "navigation"),
        (("/api/logic/catalog",), "catalog"),
        (("/api/logic/",), "tasks"),
        (("/api/services/graph",), "service_graph"),
        (("/svc", "/api/services", "/api/systemd"), "services"),
        (("/api/resource",), "resources"),
        (("/vision/snap-info", "/api/vision/snap-info", "/camera/", "/snapshots/", "/api/last_frame"), "frames"),
        (("/vision/obstacle", "/api/vision/obstacle"), "obstacle"),
        (("/sysinfo", "/status/system-pc"), "system"),
        (("/health", "/livez", "/readyz", "/api/bus/health"), "health"),
        (("/api/app-metrics",), "api_metrics"),
        (("/api/status/version", "/api/version"), "version"),
        (("/api/config/network", "/api/status/network"), "network"),
        (("/api/voice",), "voice"),
        (("/api/chat",), "chat"),
        (("/api/providers", "/providers", "/api/system/ai-mode", "/capabilities"), "providers"),
        (("/api/models", "/api/proxy/pi"), "models"),
        (("/api/google", "/raw/last.json"), "google_feed"),
        (("/api/home",), "home"),
        (("/api/mcp",), "mcp"),
        (("/api/project",), "project"),
        (("/api/knowledge",), "knowledge"),
        (("/api/assistant",), "assistant"),
    ):
        if path.startswith(prefixes):
            return "rider." + name
    return "rider.telemetry"


def error_message(error: Any) -> str | None:
    if isinstance(error, dict):
        return error.get("code") or error.get("message") or "upstream_error"
    return str(error) if error else None


def unpack(payload: Any, expected_family: str | None = None) -> dict:
    """Legacy pozostaje odczytywalne; koperta nigdy nie odmładza obserwacji."""
    if not isinstance(payload, dict):
        raise ValueError("invalid_json_type")
    declared = (
        "data" in payload
        or isinstance(payload.get("meta"), dict)
        and ("envelope_version" in payload["meta"] or "contract_id" in payload["meta"])
    )
    if not declared:
        return dict(payload)
    if "meta" not in payload or "data" not in payload:
        raise ValueError("invalid_contract_payload")
    meta, data = payload["meta"], payload["data"]
    if not isinstance(meta, dict) or type(meta.get("envelope_version")) is not int or meta["envelope_version"] != 1:
        raise ValueError("unsupported_contract")
    contract = meta.get("contract_id")
    if (
        not isinstance(contract, str)
        or contract.removeprefix("rider.") not in FAMILIES
        or not contract.startswith("rider.")
        or type(meta.get("contract_version")) is not int
        or meta.get("contract_version") != VERSIONS.get(contract, 1)
    ):
        raise ValueError("unsupported_contract")
    if expected_family is not None and contract != expected_family:
        raise ValueError("contract_family_mismatch")
    if data is None and payload.get("ok") is False and isinstance(payload.get("error"), dict):
        data = {}
    if not isinstance(data, dict) or not isinstance(payload.get("ok"), bool):
        raise ValueError("invalid_contract_payload")
    result = dict(data)
    result["contract_meta"] = dict(meta)
    for key in ("host", "source", "observed_at", "server_time", "generated_at", "partial"):
        result.setdefault(key, meta.get(key))
    for key in ("stale", "offline"):
        result[key] = meta.get(key) is True or result.get(key) is True
    result["ok"] = payload["ok"]
    if payload.get("error"):
        result["error"] = error_message(payload["error"])
        result["contract_error"] = payload["error"]
    if payload.get("operation") is not None:
        operation = payload["operation"]
        result["operation"] = operation
        if isinstance(operation, dict):
            result.setdefault("pending", operation.get("status") == "pending")
            result.setdefault("confirmed", operation.get("confirmed") is True)
    return result


def requires_confirmation(path: str) -> bool:
    """Jawne polecenia wymagają ACK; zwykłe zapisy/generowanie pozostają wynikami HTTP."""
    return path in {
        "/api/control",
        "/api/safety",
        "/api/vision/tracking/mode",
        "/api/navigator/config",
        "/api/navigator/start",
        "/api/navigator/stop",
        "/api/navigator/return_home",
        "/api/odometry/reference",
        "/api/calibration/activate",
        "/api/systemd/action",
        "/api/services/systemd/action",
        "/api/services/action",
        "/api/system/ai-mode",
        "/api/providers/text",
        "/api/providers/voice",
        "/api/providers/vision",
    } or any(path.startswith(prefix) for prefix in ("/api/logic/feature/", "/api/resource/", "/svc/"))


def envelope(payload: dict, path: str, method: str, status: int) -> dict:
    data = dict(payload)
    upstream = data.pop("contract_meta", None)
    now = time.time()
    contract = family(path)
    meta = (
        dict(upstream)
        if isinstance(upstream, dict)
        else {
            "envelope_version": 1,
            "contract_id": contract,
            "contract_version": VERSIONS.get(contract, 1),
            "host": "pc",
            "source": data.get("source", "pc-api"),
            "observed_at": data.get("observed_at", data.get("ts", data.get("timestamp"))),
        }
    )
    if not upstream:
        meta.update(generated_at=now, server_time=now)
    for key in ("stale", "offline", "partial"):
        meta[key] = meta.get(key) is True or data.get(key) is True
    if upstream:
        meta["transport"] = {
            **upstream.get("transport", {}),
            "receiver_host": "pc",
            "generated_at": now,
            "server_time": now,
            "received_at": data.get("received_at"),
            "attempted_at": data.get("attempted_at"),
            "upstream_status": data.get("_http_status", status),
        }
        # Zegar Pi nadal potrzebny w handshake poleceń, osobno od zegara proxy.
        meta["upstream_server_time"] = upstream.get("server_time")
    raw_error = data.get("error") or data.get("detail")
    error = data.pop("contract_error", None) or (
        {"code": error_message(raw_error), "message": str(raw_error), "retryable": False, "details": None}
        if raw_error
        else None
    )
    operation = data.pop("operation", None)
    if method not in {"GET", "HEAD", "OPTIONS"} and operation is None and requires_confirmation(path):
        pending = status == 202 or data.get("pending") is True
        successful = status < 400 and not error and data.get("ok") is not False
        confirmed = (
            successful
            and not pending
            and (
                data.get("confirmed") is True
                or isinstance(data.get("ack"), dict)
                and data["ack"].get("status") == "executed"
            )
        )
        operation = {
            "request_id": data.get("request_id"),
            "action": data.get("action"),
            "target": data.get("target"),
            "status": "pending"
            if pending
            else "executed"
            if confirmed
            else "unknown"
            if successful or status >= 500
            else "rejected",
            "confirmed": confirmed,
            "ack_kind": data.get("ack_kind"),
            "ack": data.get("ack"),
            "actuation": data.get("actuation", False),
        }
        if contract == "rider.safety":
            operation["physical_completion"] = "unverified"
    if operation is not None:
        meta["partial"] = meta["partial"] or operation.get("status") != "executed"
    return {
        "meta": meta,
        "ok": status < 400
        and data.get("ok") is not False
        and not error
        and (operation is None or operation.get("status") == "executed" and operation.get("confirmed") is True),
        "data": data,
        "error": error,
        "operation": operation,
    }


def accept_version(header: str):
    offered = []
    for item in header.split(","):
        parts = [part.strip() for part in item.split(";")]
        if parts[0].lower() != MEDIA_TYPE:
            continue
        parameters = {
            key.strip().lower(): value.strip().strip('"')
            for key, value in (part.split("=", 1) for part in parts[1:] if "=" in part)
        }
        try:
            quality = float(parameters.get("q", "1"))
        except ValueError:
            quality = 0
        if 0 < quality <= 1:
            offered.append((quality, parameters.get("version", "missing")))
    if not offered:
        return None
    return "1" if any(version == "1" for _, version in offered) else max(offered, key=lambda row: row[0])[1]


class ContractMiddleware:
    """Czysty ASGI: nie buforuje SSE, obrazów ani audio."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        accept = dict(scope.get("headers", [])).get(b"accept", b"").decode()
        version = accept_version(accept)
        if version is None:
            return await self.app(scope, receive, send)
        if version != "1":
            response = JSONResponse(
                envelope({"ok": False, "error": "unsupported_contract"}, scope["path"], scope["method"], 406),
                406,
                headers={"Vary": "Accept"},
                media_type=ACCEPT,
            )
            return await response(scope, receive, send)
        start, chunks = None, []

        async def wrapped(message):
            nonlocal start
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                if b"application/json" not in headers.get(b"content-type", b"") or message["status"] in {204, 304}:
                    return await send(message)
                start = message
                return
            if start is None:
                return await send(message)
            chunks.append(message.get("body", b""))
            if message.get("more_body"):
                return
            status = start["status"]
            try:
                body = json.loads(b"".join(chunks))
                value = envelope(
                    body if isinstance(body, dict) else {"value": body}, scope["path"], scope["method"], status
                )
                operation = value["operation"]
                if operation and status < 400:
                    status = {"pending": 202, "unknown": 502, "partial": 409}.get(operation.get("status"), status)
                if status >= 400 and value["error"] is None:
                    value["error"] = {"code": f"http_{status}", "message": "Request failed", "retryable": False}
                output = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
            except (ValueError, TypeError, OverflowError):
                status = 502
                value = envelope(
                    {"ok": False, "partial": True, "error": "invalid_domain_payload"}, scope["path"], "GET", status
                )
                value["data"] = None
                output = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
            original = start.get("headers", [])
            varies = [v.decode() for k, v in original if k.lower() == b"vary"]
            vary = [part.strip() for item in varies for part in item.split(",") if part.strip()]
            if not any(part.lower() == "accept" for part in vary):
                vary.append("Accept")
            headers = [(k, v) for k, v in original if k.lower() not in {b"content-type", b"content-length", b"vary"}]
            headers += [
                (b"content-type", ACCEPT.encode()),
                (b"content-length", str(len(output)).encode()),
                (b"vary", ", ".join(vary).encode()),
            ]
            await send({**start, "status": status, "headers": headers})
            await send({"type": "http.response.body", "body": output})

        await self.app(scope, receive, wrapped)
