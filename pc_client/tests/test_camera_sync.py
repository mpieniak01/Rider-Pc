from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from pc_client.api import lifecycle


def test_last_modified_timestamp_parses_header():
    headers = {"Last-Modified": "Mon, 02 Jan 2023 15:04:05 GMT"}
    ts = lifecycle._last_modified_timestamp(headers)
    expected = datetime(2023, 1, 2, 15, 4, 5, tzinfo=timezone.utc).timestamp()
    assert ts == expected


@pytest.mark.asyncio
async def test_fetch_and_store_camera_frame_updates_state():
    class DummyAdapter:
        async def fetch_binary(self, path: str, params=None):
            return b"frame", "image/jpeg", {"Last-Modified": "Mon, 02 Jan 2023 15:04:05 GMT"}

    adapter = DummyAdapter()
    state = SimpleNamespace(
        rest_adapter=adapter,
        last_camera_frame={"content": b"", "media_type": "image/png", "timestamp": 0},
    )
    app = SimpleNamespace(state=state)

    await lifecycle._fetch_and_store_camera_frame(app)

    assert app.state.last_camera_frame["content"] == b"frame"
    assert app.state.last_camera_frame["media_type"] == "image/jpeg"
    expected = datetime(2023, 1, 2, 15, 4, 5, tzinfo=timezone.utc).timestamp()
    assert app.state.last_camera_frame["timestamp"] == expected
