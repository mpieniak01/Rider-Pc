"""Oryginalny czas kamery i symulacja nie mogą stać się świeżym pomiarem robota."""

from unittest.mock import MagicMock

import pytest

from pc_client.api.task_utils import build_vision_frame_task, build_voice_tts_task
from pc_client.providers.base import TaskResult, TaskStatus
from pc_client.queue import TaskQueue
from pc_client.queue.task_queue import TaskQueueWorker
from pc_client.telemetry.zmq_publisher import ZMQTelemetryPublisher


@pytest.mark.parametrize("observed", [123.0, None, 0, False])
def test_capture_observed_at_is_not_replaced_by_publication_time(observed):
    task = build_vision_frame_task({"frame_data": "fake", "observed_at": observed, "timestamp": 999.0}, 1)
    assert task.payload["observed_at"] == observed
    assert task.payload["timestamp"] == observed


@pytest.mark.parametrize(
    "observed,ready", [(123.0, True), (None, False), (0, False), (False, False), (float("nan"), False)]
)
def test_publisher_marks_unknown_observation_not_ready(observed, ready):
    publisher = ZMQTelemetryPublisher()
    publisher.publish = MagicMock()
    publisher.publish_vision_obstacle_enhanced("frame", [], {"observed_at": observed, "timestamp": 999.0})
    data = publisher.publish.call_args.args[1]
    assert data["data_ready"] is ready
    assert data["observed_at"] == observed or str(data["observed_at"]) == "nan"
    assert data["timestamp"] != 999.0


@pytest.mark.parametrize(
    "payload",
    [
        {"offset": 0.2},
        {"offset": 0.2, "observed_at": None, "ts": 999.0},
        {"offset": 0.2, "observed_at": 123.0, "simulated": True},
    ],
)
def test_tracking_never_mints_fresh_capture_or_publishes_demo(payload):
    publisher = ZMQTelemetryPublisher()
    publisher.publish = MagicMock()
    publisher.publish_tracking_offset(payload)
    publisher.publish.assert_not_called()


@pytest.mark.asyncio
async def test_worker_keeps_original_capture_even_if_result_claims_new_time():
    task = build_vision_frame_task({"frame_data": "fake", "observed_at": 123.0}, 1)
    telemetry = MagicMock()
    worker = TaskQueueWorker(TaskQueue(), {}, telemetry_publisher=telemetry)
    result = TaskResult(
        task.task_id,
        TaskStatus.COMPLETED,
        result={"timestamp": 999.0, "obstacles": []},
        meta={"timestamp": 999.0, "observed_at": 999.0, "engine": "yolov8"},
        processing_time_ms=1,
    )
    await worker._publish_result(task, result)
    meta = telemetry.publish_vision_obstacle_enhanced.call_args.kwargs["meta"]
    assert meta["observed_at"] == meta["timestamp"] == 123.0


def test_tts_builder_preserves_explicit_provider_and_default_speed():
    task = build_voice_tts_task({"text": "hello", "provider": "openai"}, 5)
    assert task.payload["provider"] == "openai"
    assert task.payload["speed"] == 1.0
