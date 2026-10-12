"""Cached camera headers never create a producer time from receipt time."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pc_client.api.lifecycle import _fetch_and_store_camera_frame, _last_modified_timestamp
from pc_client.api.routers.control_router import router
from pc_client.telemetry.zmq_publisher import ZMQTelemetryPublisher


@pytest.mark.parametrize(
    "headers", [{}, {"Last-Modified": "invalid"}, {"Last-Modified": "Thu, 01 Jan 1970 00:00:00 GMT"}]
)
@pytest.mark.asyncio
async def test_unknown_capture_does_not_inherit_receipt_time(headers):
    class Adapter:
        async def fetch_binary(self, path, params=None):
            assert path == "/camera/last"
            return b"image", "image/jpeg", headers

    app = SimpleNamespace(state=SimpleNamespace(rest_adapter=Adapter()))
    await _fetch_and_store_camera_frame(app)
    assert app.state.last_camera_frame["timestamp"] is None
    assert app.state.last_camera_frame["received_at"] > 0


def test_source_clock_is_preserved_without_assuming_clock_alignment():
    observed = _last_modified_timestamp({"Last-Modified": "Sat, 01 Jan 2050 00:00:00 GMT"})
    assert observed == 2524608000


class FrameAdapter:
    def __init__(self, headers):
        self.headers = headers
        self.calls = []

    async def fetch_binary(self, path, params=None):
        self.calls.append((path, params))
        return b"source image", "image/jpeg", self.headers


def camera_client(headers):
    app = FastAPI()
    app.include_router(router)
    app.state.last_camera_frame = {"content": b"local placeholder", "timestamp": None}
    app.state.rest_adapter = FrameAdapter(headers)
    return TestClient(app)


FRESH_HEADERS = {
    "X-Rider-Contract": "rider.frames;version=1",
    "X-Rider-Source": "pi/raw",
    "X-Rider-Placeholder": "false",
    "X-Rider-Stale": "false",
    "X-Rider-File-Observed-At": "100.25",
    "X-Rider-Frame-Id": "source-frame",
}


@pytest.mark.parametrize("method", ["get", "head"])
@pytest.mark.parametrize(
    "patch",
    [
        {"X-Rider-Stale": "true"},
        {"X-Rider-Placeholder": "true"},
        {"X-Rider-File-Observed-At": ""},
        {"X-Rider-File-Observed-At": "nan"},
        {"X-Rider-Contract": "unknown"},
    ],
)
def test_current_get_and_head_refuse_unknown_stale_or_placeholder(method, patch):
    with camera_client({**FRESH_HEADERS, **patch}) as client:
        response = getattr(client, method)("/camera/last")
    assert response.status_code == 404
    assert b"local placeholder" not in response.content
    assert response.headers["x-rider-source"] == "pi/raw"


@pytest.mark.parametrize("method", ["get", "head"])
def test_current_frame_is_live_proxy_with_original_source_headers(method):
    with camera_client(FRESH_HEADERS) as client:
        response = getattr(client, method)("/camera/last")
        assert client.app.state.rest_adapter.calls == [("/camera/last", {})]
    assert response.status_code == 200
    assert response.content == (b"source image" if method == "get" else b"")
    assert response.headers["x-rider-file-observed-at"] == "100.25"
    assert response.headers["x-rider-frame-id"] == "source-frame"
    assert "last-modified" not in response.headers


def test_archive_is_only_available_as_explicit_upstream_request():
    with camera_client({**FRESH_HEADERS, "X-Rider-Stale": "true"}) as client:
        assert client.get("/camera/last").status_code == 404
        response = client.get("/camera/last?archive=1")
        assert client.app.state.rest_adapter.calls[-1] == ("/camera/last", {"archive": "1"})
    assert response.status_code == 200
    assert response.headers["x-rider-stale"] == "true"


def test_upstream_current_404_keeps_source_headers():
    import httpx

    class Missing:
        async def fetch_binary(self, path, params=None):
            response = httpx.Response(
                404,
                headers={**FRESH_HEADERS, "X-Rider-Stale": "true"},
                request=httpx.Request("GET", "http://127.0.0.1/camera/last"),
            )
            response.raise_for_status()

    with camera_client(FRESH_HEADERS) as client:
        client.app.state.rest_adapter = Missing()
        response = client.get("/camera/last")
    assert response.status_code == 404
    assert response.headers["x-rider-stale"] == "true"
    assert response.headers["x-rider-source"] == "pi/raw"


def test_image_heuristic_never_claims_verified_metric_range():
    messages = []
    publisher = ZMQTelemetryPublisher()
    publisher.publish = lambda topic, data: messages.append(data)
    publisher.publish_vision_obstacle_enhanced("frame", [], {"observed_at": 100, "range_verified": True})
    assert messages[0]["range_verified"] is False
    assert messages[0]["distance_unit"] == "unverified"
