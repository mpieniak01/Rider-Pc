"""ZMQ telemetry publisher for sending results back to Rider-PI."""

import zmq
import json
import logging
from typing import Dict, Any, Optional
from pc_client.providers.base import TaskResult

logger = logging.getLogger(__name__)


class ZMQTelemetryPublisher:
    """
    ZMQ Publisher for sending telemetry and task results to Rider-PI bus.

    This publisher sends results on topics that Rider-PI subscribes to,
    allowing PC-processed tasks to be integrated back into the robot's
    data flow.
    """

    def __init__(self, endpoint: Optional[str] = None):
        """
        Initialize ZMQ telemetry publisher.

        Args:
            endpoint: ZMQ endpoint to bind to (e.g., "tcp://10.0.0.2:5557")
                     If None, publisher will be in mock mode
        """
        self.endpoint = endpoint
        self.context: Optional[zmq.Context] = None
        self.socket: Optional[zmq.Socket] = None
        self._enabled = False
        self.logger = logging.getLogger("[bridge] ZMQTelemetryPublisher")

        if endpoint:
            self._initialize()

    def _initialize(self):
        """Initialize ZMQ publisher socket."""
        try:
            self.context = zmq.Context()
            self.socket = self.context.socket(zmq.PUB)
            self.socket.bind(self.endpoint)
            self._enabled = True
            self.logger.info(f"ZMQ telemetry publisher initialized on {self.endpoint}")
        except Exception as e:
            self.logger.error(f"Failed to initialize ZMQ publisher: {e}")
            self._enabled = False

    def publish(self, topic: str, data: Dict[str, Any]):
        """
        Publish message to ZMQ bus.

        Args:
            topic: ZMQ topic (e.g., "telemetry.task.completed")
            data: Message data as dictionary
        """
        if not self._enabled or not self.socket:
            self.logger.debug(f"Publisher not enabled, skipping publish to {topic}")
            return

        try:
            message = [topic.encode('utf-8'), json.dumps(data).encode('utf-8')]
            self.socket.send_multipart(message)
            self.logger.debug(f"Published to topic '{topic}': {len(json.dumps(data))} bytes")
        except Exception as e:
            self.logger.error(f"Failed to publish message: {e}")

    def publish_task_result(self, result: TaskResult):
        """
        Publish task result to telemetry bus.

        Args:
            result: Task result to publish
        """
        import time

        data = {
            'task_id': result.task_id,
            'status': result.status.value,
            'processing_time_ms': result.processing_time_ms,
            'timestamp': time.time(),
            'result': result.result,
            'error': result.error,
            'meta': result.meta,
        }

        self.publish('telemetry.task.completed', data)

    def publish_vision_obstacle_enhanced(self, frame_id: str, obstacles: list, meta: Dict[str, Any]):
        """
        Publish enhanced vision obstacle data.

        This is used by Vision Provider to send processed frame data
        back to Rider-PI for obstacle avoidance.

        Args:
            frame_id: Frame identifier
            obstacles: List of detected obstacles
            meta: Metadata about processing
        """
        data = {
            'frame_id': frame_id,
            'obstacles': obstacles,
            'timestamp': meta.get('timestamp'),
            'processing_source': 'pc',
            'meta': meta,
        }

        self.publish('vision.obstacle.enhanced', data)

    def publish_provider_status(self, provider_name: str, status: str, telemetry: Dict[str, Any]):
        """
        Publish provider status and telemetry.

        Args:
            provider_name: Name of the provider
            status: Provider status (e.g., "active", "idle", "error")
            telemetry: Provider telemetry data
        """
        import time

        data = {'provider': provider_name, 'status': status, 'telemetry': telemetry, 'timestamp': time.time()}

        self.publish('telemetry.provider.status', data)

    def publish_queue_metrics(self, queue_stats: Dict[str, Any]):
        """
        Publish task queue metrics.

        Args:
            queue_stats: Queue statistics
        """
        import time

        data = {'queue_stats': queue_stats, 'timestamp': time.time()}

        self.publish('telemetry.queue.metrics', data)

    def close(self):
        """Close ZMQ publisher and cleanup resources."""
        if self.socket:
            self.socket.close()
            self.logger.info("ZMQ telemetry publisher closed")

        if self.context:
            self.context.term()

        self._enabled = False

    def is_enabled(self) -> bool:
        """Check if publisher is enabled."""
        return self._enabled
