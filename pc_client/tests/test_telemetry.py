"""Tests for telemetry module."""

import pytest
import time
from pc_client.telemetry.zmq_publisher import ZMQTelemetryPublisher
from pc_client.telemetry.metrics import (
    tasks_processed_total,
    task_duration_seconds,
    task_queue_size
)
from pc_client.providers.base import TaskResult, TaskStatus


def test_zmq_telemetry_publisher_mock_mode():
    """Test ZMQ telemetry publisher in mock mode (no endpoint)."""
    publisher = ZMQTelemetryPublisher()
    
    assert not publisher.is_enabled()
    
    # Should not raise errors in mock mode
    publisher.publish("test.topic", {"data": "value"})
    publisher.close()


def test_zmq_telemetry_publisher_with_endpoint():
    """Test ZMQ telemetry publisher with endpoint."""
    endpoint = "tcp://127.0.0.1:15557"
    publisher = ZMQTelemetryPublisher(endpoint)
    
    assert publisher.is_enabled()
    assert publisher.endpoint == endpoint
    
    publisher.close()
    assert not publisher.is_enabled()


def test_zmq_publish_task_result():
    """Test publishing task result."""
    publisher = ZMQTelemetryPublisher()  # Mock mode
    
    result = TaskResult(
        task_id="test-1",
        status=TaskStatus.COMPLETED,
        result={"data": "value"},
        processing_time_ms=100.0
    )
    
    # Should not raise error in mock mode
    publisher.publish_task_result(result)
    publisher.close()


def test_zmq_publish_vision_obstacle_enhanced():
    """Test publishing vision obstacle enhanced data."""
    publisher = ZMQTelemetryPublisher()
    
    obstacles = [
        {"type": "obstacle", "distance": 1.5, "angle": 15}
    ]
    meta = {"timestamp": time.time()}
    
    publisher.publish_vision_obstacle_enhanced("frame-123", obstacles, meta)
    publisher.close()


def test_zmq_publish_provider_status():
    """Test publishing provider status."""
    publisher = ZMQTelemetryPublisher()
    
    telemetry = {
        "provider": "VoiceProvider",
        "initialized": True,
        "tasks_processed": 10
    }
    
    publisher.publish_provider_status("VoiceProvider", "active", telemetry)
    publisher.close()


def test_zmq_publish_queue_metrics():
    """Test publishing queue metrics."""
    publisher = ZMQTelemetryPublisher()
    
    stats = {
        "total_queued": 100,
        "total_processed": 90,
        "current_size": 10
    }
    
    publisher.publish_queue_metrics(stats)
    publisher.close()


def test_prometheus_metrics():
    """Test Prometheus metrics."""
    # Test counter
    initial_count = tasks_processed_total.labels(
        provider='TestProvider',
        task_type='test.task',
        status='completed'
    )._value.get()
    
    tasks_processed_total.labels(
        provider='TestProvider',
        task_type='test.task',
        status='completed'
    ).inc()
    
    new_count = tasks_processed_total.labels(
        provider='TestProvider',
        task_type='test.task',
        status='completed'
    )._value.get()
    
    assert new_count == initial_count + 1


def test_prometheus_task_duration():
    """Test task duration histogram."""
    task_duration_seconds.labels(
        provider='TestProvider',
        task_type='test.task'
    ).observe(0.5)
    
    # Verify metric was recorded
    metric = task_duration_seconds.labels(
        provider='TestProvider',
        task_type='test.task'
    )
    assert metric._sum.get() >= 0.5


def test_prometheus_queue_size():
    """Test queue size gauge."""
    task_queue_size.labels(queue_name='test_queue').set(10)
    
    value = task_queue_size.labels(queue_name='test_queue')._value.get()
    assert value == 10
    
    task_queue_size.labels(queue_name='test_queue').set(5)
    value = task_queue_size.labels(queue_name='test_queue')._value.get()
    assert value == 5
