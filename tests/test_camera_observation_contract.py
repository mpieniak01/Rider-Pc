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
        async def fetch_binary(self, path):
            assert path == "/camera/last"
            return b"image", "image/jpeg", headers

    app = SimpleNamespace(state=SimpleNamespace(rest_adapter=Adapter()))
    await _fetch_and_store_camera_frame(app)
    assert app.state.last_camera_frame["timestamp"] is None
    assert app.state.last_camera_frame["received_at"] > 0


def test_source_clock_is_preserved_without_assuming_clock_alignment():
    observed = _last_modified_timestamp({"Last-Modified": "Sat, 01 Jan 2050 00:00:00 GMT"})
    assert observed == 2524608000


@pytest.mark.parametrize("method", ["get", "head"])
def test_unknown_get_and_head_have_no_last_modified(method):
    app = FastAPI()
    app.include_router(router)
    app.state.last_camera_frame = {"content": b"image", "media_type": "image/png", "timestamp": None}
    with TestClient(app) as client:
        response = getattr(client, method)("/camera/last")
    assert response.status_code == 200
    assert "last-modified" not in response.headers
    assert response.headers["x-camera-observation-valid"] == "false"


def test_known_capture_is_served_with_original_last_modified():
    app = FastAPI()
    app.include_router(router)
    app.state.last_camera_frame = {"content": b"image", "timestamp": 100.0}
    with TestClient(app) as client:
        response = client.get("/camera/last")
    assert response.headers["last-modified"] == "Thu, 01 Jan 1970 00:01:40 GMT"
    assert response.headers["x-camera-observation-valid"] == "true"


def test_image_heuristic_never_claims_verified_metric_range():
    messages = []
    publisher = ZMQTelemetryPublisher()
    publisher.publish = lambda topic, data: messages.append(data)
    publisher.publish_vision_obstacle_enhanced("frame", [], {"observed_at": 100, "range_verified": True})
    assert messages[0]["range_verified"] is False
    assert messages[0]["distance_unit"] == "unverified"
