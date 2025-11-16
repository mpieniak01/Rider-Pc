"""Vision provider for image and video stream processing."""

import logging
import base64
import io
from typing import Dict, Any, Optional
from pc_client.providers.base import BaseProvider, TaskEnvelope, TaskResult, TaskType, TaskStatus
from pc_client.telemetry.metrics import tasks_processed_total, task_duration_seconds

logger = logging.getLogger(__name__)

# Import AI libraries with fallback to mock mode
try:
    from ultralytics import YOLO
    from PIL import Image

    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    logger.warning("YOLOv8 not available, using mock object detection")


class VisionProvider(BaseProvider):
    """
    Provider for vision processing tasks.

    This provider handles image/video processing offloaded from the Rider-PI
    vision pipeline (apps/vision). It receives frame packets and returns
    detection results, bounding boxes, and enhanced obstacle information.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the vision provider.

        Args:
            config: Vision provider configuration
                - detection_model: Detection model to use (default: "yolov8n")
                - confidence_threshold: Minimum confidence (default: 0.5)
                - max_detections: Maximum detections per frame (default: 10)
                - use_mock: Force mock mode (default: False)
        """
        super().__init__("VisionProvider", config)
        self.detection_model_name = self.config.get("detection_model", "yolov8n")
        self.confidence_threshold = self.config.get("confidence_threshold", 0.5)
        self.max_detections = self.config.get("max_detections", 10)
        self.use_mock = self.config.get("use_mock", False)

        # Model instance (loaded during initialization)
        self.detector: Optional[Any] = None

    async def _initialize_impl(self) -> None:
        """Initialize vision processing models."""
        self.logger.info(f"Loading detection model: {self.detection_model_name}")
        self.logger.info(f"Confidence threshold: {self.confidence_threshold}")
        self.logger.info(f"Max detections: {self.max_detections}")

        # Load YOLO model if available and not in mock mode
        if YOLO_AVAILABLE and not self.use_mock:
            try:
                self.logger.info("[vision] Loading YOLOv8 model...")
                # Load YOLOv8 model (will auto-download if not cached)
                self.detector = YOLO(f"{self.detection_model_name}.pt")
                self.logger.info("[vision] YOLOv8 model loaded successfully")
            except Exception as e:
                self.logger.error(f"[vision] Failed to load YOLO: {e}")
                self.logger.warning("[vision] Falling back to mock detection")
                self.detector = None
        else:
            self.logger.info("[vision] Using mock vision implementation")
            self.detector = None

        self.logger.info("[vision] Vision provider initialized")

    async def _shutdown_impl(self) -> None:
        """Cleanup vision processing resources."""
        self.logger.info("[vision] Cleaning up vision resources")
        if self.detector is not None:
            # YOLO models don't require explicit cleanup
            self.detector = None
        self.logger.info("[vision] Vision resources cleaned up")

    async def _process_task_impl(self, task: TaskEnvelope) -> TaskResult:
        """
        Process vision task.

        Args:
            task: Task envelope with vision data

        Returns:
            Task result with detection results
        """
        if task.task_type == TaskType.VISION_DETECTION:
            return await self._process_detection(task)
        elif task.task_type == TaskType.VISION_FRAME:
            return await self._process_frame(task)
        else:
            return TaskResult(
                task_id=task.task_id, status=TaskStatus.FAILED, error=f"Unsupported task type: {task.task_type}"
            )

    async def _process_detection(self, task: TaskEnvelope) -> TaskResult:
        """
        Process object detection task.

        Expected payload:
            - image_data: Base64-encoded image
            - format: Image format (e.g., "jpeg", "png")
            - width: Image width
            - height: Image height

        Returns:
            TaskResult with detected objects and bounding boxes
        """
        self.logger.info(f"[vision] Processing detection task {task.task_id}")

        image_data = task.payload.get("image_data")
        image_format = task.payload.get("format", "jpeg")
        width = task.payload.get("width", 640)
        height = task.payload.get("height", 480)

        if not image_data:
            return TaskResult(task_id=task.task_id, status=TaskStatus.FAILED, error="Missing image_data in payload")

        # Process with real YOLO model if available
        if self.detector is not None:
            try:
                # Decode base64 image data with error handling
                try:
                    image_bytes = base64.b64decode(image_data)
                    image = Image.open(io.BytesIO(image_bytes))
                except Exception as e:
                    self.logger.error(f"[vision] Failed to decode image data: {e}")
                    raise

                # Run YOLO detection
                results = self.detector(image, conf=self.confidence_threshold, max_det=self.max_detections)

                # Extract detections
                detections = []
                for result in results:
                    boxes = result.boxes
                    for box in boxes:
                        # Get box coordinates (xyxy format)
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        confidence = float(box.conf[0])
                        class_id = int(box.cls[0])
                        class_name = result.names[class_id]

                        # Calculate center
                        center_x = int((x1 + x2) / 2)
                        center_y = int((y1 + y2) / 2)

                        detections.append(
                            {
                                "class": class_name,
                                "confidence": round(confidence, 2),
                                "bbox": [int(x1), int(y1), int(x2), int(y2)],
                                "center": [center_x, center_y],
                            }
                        )

                self.logger.info(f"[vision] Detected {len(detections)} objects")

                # Update metrics
                tasks_processed_total.labels(
                    provider='VisionProvider', task_type='vision.detection', status='completed'
                ).inc()

                return TaskResult(
                    task_id=task.task_id,
                    status=TaskStatus.COMPLETED,
                    result={
                        "detections": detections,
                        "image_width": width,
                        "image_height": height,
                        "num_detections": len(detections),
                    },
                    meta={
                        "model": self.detection_model_name,
                        "confidence_threshold": self.confidence_threshold,
                        "format": image_format,
                        "engine": "yolov8",
                    },
                )

            except Exception as e:
                self.logger.error(f"[vision] Detection processing failed: {e}")
                self.logger.warning("[vision] Falling back to mock detection due to error")

        # Mock implementation fallback
        detections = [
            {
                "class": "person",
                "confidence": 0.92,
                "bbox": [100, 150, 300, 450],  # x1, y1, x2, y2
                "center": [200, 300],
            },
            {"class": "obstacle", "confidence": 0.87, "bbox": [400, 200, 550, 400], "center": [475, 300]},
        ]

        self.logger.info(f"[vision] Detected (mock) {len(detections)} objects")

        # Update metrics
        tasks_processed_total.labels(provider='VisionProvider', task_type='vision.detection', status='completed').inc()

        return TaskResult(
            task_id=task.task_id,
            status=TaskStatus.COMPLETED,
            result={
                "detections": detections,
                "image_width": width,
                "image_height": height,
                "num_detections": len(detections),
            },
            meta={
                "model": "mock",
                "confidence_threshold": self.confidence_threshold,
                "format": image_format,
                "engine": "mock",
            },
        )

    async def _process_frame(self, task: TaskEnvelope) -> TaskResult:
        """
        Process video frame offload task.

        This handles the vision.frame.offload topic from Rider-PI.
        Processes frames and publishes enhanced results to vision.obstacle.enhanced.

        Expected payload:
            - frame_data: Base64-encoded frame
            - frame_id: Frame sequence ID
            - timestamp: Frame timestamp
            - format: Frame format

        Returns:
            TaskResult with enhanced frame analysis
        """
        self.logger.info(f"[vision] Processing frame task {task.task_id}")

        frame_data = task.payload.get("frame_data")
        frame_id = task.payload.get("frame_id")
        timestamp = task.payload.get("timestamp")

        if not frame_data:
            return TaskResult(task_id=task.task_id, status=TaskStatus.FAILED, error="Missing frame_data in payload")

        # Process with real YOLO model if available
        if self.detector is not None:
            try:
                # Decode base64 frame data with error handling
                try:
                    frame_bytes = base64.b64decode(frame_data)
                    frame = Image.open(io.BytesIO(frame_bytes))
                except Exception as e:
                    self.logger.error(f"[vision] Failed to decode frame data: {e}")
                    raise

                # Run YOLO detection
                results = self.detector(frame, conf=self.confidence_threshold)

                # Load obstacle classes from config, or default to YOLO COCO class names.
                # See: https://github.com/ultralytics/ultralytics/blob/main/ultralytics/cfg/datasets/coco.yaml
                obstacle_classes = set(
                    self.config.get(
                        'obstacle_classes',
                        [
                            'person',
                            'bicycle',
                            'car',
                            'motorcycle',
                            'bus',
                            'truck',
                            'chair',
                            'couch',
                            'dog',
                            'cat',
                            'bottle',
                            'cup',
                        ],
                    )
                )

                # Extract obstacles (focus on objects relevant for navigation)
                obstacles = []

                for result in results:
                    boxes = result.boxes
                    for box in boxes:
                        class_id = int(box.cls[0])
                        class_name = result.names[class_id]

                        # Only consider obstacles relevant for navigation
                        if class_name in obstacle_classes:
                            confidence = float(box.conf[0])
                            x1, y1, x2, y2 = box.xyxy[0].tolist()

                            # Estimate distance based on box size (VERY ROUGH - PLACEHOLDER)
                            box_area = (x2 - x1) * (y2 - y1)
                            distance = max(0.5, min(5.0, 5.0 - (box_area / 100000)))

                            # Calculate angle from center
                            center_x = (x1 + x2) / 2
                            frame_width = frame.width
                            angle = int(((center_x - frame_width / 2) / frame_width) * 60)  # ±30 degrees

                            obstacles.append(
                                {
                                    "type": class_name,
                                    "distance": round(distance, 2),
                                    "angle": angle,
                                    "confidence": round(confidence, 2),
                                    "size": "large" if box_area > 50000 else "medium" if box_area > 10000 else "small",
                                }
                            )

                self.logger.info(f"[vision] Frame {frame_id} processed, found {len(obstacles)} obstacles")

                # Update metrics
                tasks_processed_total.labels(
                    provider='VisionProvider', task_type='vision.frame', status='completed'
                ).inc()

                return TaskResult(
                    task_id=task.task_id,
                    status=TaskStatus.COMPLETED,
                    result={
                        "frame_id": frame_id,
                        "timestamp": timestamp,
                        "obstacles": obstacles,
                        "should_avoid": len(obstacles) > 0,
                        "suggested_action": "slow_down" if obstacles else "continue",
                    },
                    meta={
                        "model": self.detection_model_name,
                        "processing_type": "frame_offload",
                        "engine": "yolov8",
                        "timestamp": timestamp,
                    },
                )

            except Exception as e:
                self.logger.error(f"[vision] Frame processing failed: {e}")
                self.logger.warning("[vision] Falling back to mock frame processing due to error")

        # Mock implementation fallback
        obstacles = [
            {
                "type": "obstacle",
                "distance": 1.5,  # meters
                "angle": 15,  # degrees
                "confidence": 0.89,
                "size": "medium",
            }
        ]

        self.logger.info(f"[vision] Frame {frame_id} processed (mock), found {len(obstacles)} obstacles")

        # Update metrics
        tasks_processed_total.labels(provider='VisionProvider', task_type='vision.frame', status='completed').inc()

        return TaskResult(
            task_id=task.task_id,
            status=TaskStatus.COMPLETED,
            result={
                "frame_id": frame_id,
                "timestamp": timestamp,
                "obstacles": obstacles,
                "should_avoid": len(obstacles) > 0,
                "suggested_action": "slow_down" if obstacles else "continue",
            },
            meta={"model": "mock", "processing_type": "frame_offload", "engine": "mock", "timestamp": timestamp},
        )

    def get_supported_tasks(self) -> list[TaskType]:
        """Get list of supported task types."""
        return [TaskType.VISION_DETECTION, TaskType.VISION_FRAME]

    def get_telemetry(self) -> Dict[str, Any]:
        """Get vision provider telemetry."""
        base_telemetry = super().get_telemetry()
        base_telemetry.update(
            {
                "detection_model": self.detection_model_name,
                "confidence_threshold": self.confidence_threshold,
                "max_detections": self.max_detections,
                "detector_available": self.detector is not None,
                "mode": "mock" if self.detector is None else "real",
            }
        )
        return base_telemetry
