"""Vision provider for image and video stream processing."""

import logging
import base64
import io
import time
from typing import Dict, Any, Optional, Tuple

import numpy as np
from pc_client.providers.base import BaseProvider, TaskEnvelope, TaskResult, TaskType, TaskStatus
from pc_client.telemetry.metrics import tasks_processed_total, task_duration_seconds

logger = logging.getLogger(__name__)

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = ImageDraw = ImageFont = None  # type: ignore
    logger.warning("Pillow not installed; tracker overlay will be disabled")

try:
    from ultralytics import YOLO

    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    logger.warning("YOLOv8 not available, using mock object detection")

try:
    import mediapipe as mp  # type: ignore

    MP_AVAILABLE = True
except ImportError:
    mp = None  # type: ignore
    MP_AVAILABLE = False
    logger.warning("MediaPipe not installed; tracking offsets will use fallback heuristics")


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
        self._tracker_overlay: bytes = self._build_tracker_placeholder()
        self._tracker_ts: float = 0.0
        self._tracker_fps: float = 0.0
        self._tracker_last_frame_ts: float = 0.0
        self._tracking_dead_zone: float = float(self.config.get("tracking_dead_zone", 0.1))
        self._mp_face = None
        self._mp_hands = None
        self._init_tracking_detectors()

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
        self._close_tracking_detectors()
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

                self._update_tracker_snapshot(image, detections)
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

        placeholder = Image.new("RGBA", (width, height), (20, 20, 30, 255))
        self._update_tracker_snapshot(placeholder, detections)
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

    def _init_tracking_detectors(self) -> None:
        """Initialize optional MediaPipe detectors for tracking offsets."""
        if not MP_AVAILABLE:
            self.logger.info("[vision] MediaPipe unavailable – tracking offsets will use detection fallback")
            return

        try:
            self._mp_face = mp.solutions.face_detection.FaceDetection(
                model_selection=0,
                min_detection_confidence=0.5,
            )
            self.logger.info("[vision] MediaPipe face detector initialized")
        except Exception as exc:  # pragma: no cover - defensive
            self._mp_face = None
            self.logger.warning("[vision] Failed to initialize MediaPipe face detector: %s", exc)

        try:
            self._mp_hands = mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            self.logger.info("[vision] MediaPipe hand detector initialized")
        except Exception as exc:  # pragma: no cover - defensive
            self._mp_hands = None
            self.logger.warning("[vision] Failed to initialize MediaPipe hand detector: %s", exc)

    def _close_tracking_detectors(self) -> None:
        """Cleanup MediaPipe detectors on shutdown."""
        for detector in (self._mp_face, self._mp_hands):
            if detector and hasattr(detector, "close"):
                try:
                    detector.close()
                except Exception as exc:  # pragma: no cover - defensive
                    self.logger.debug("Tracking detector close warning: %s", exc)
        self._mp_face = None
        self._mp_hands = None

    def _build_tracker_placeholder(self) -> bytes:
        canvas = Image.new("RGBA", (640, 360), (10, 10, 25, 255))
        draw = ImageDraw.Draw(canvas)
        font = ImageFont.load_default() if ImageFont else None
        draw.text((10, 10), "Tracker idle", fill=(180, 220, 255), font=font)
        return self._to_png_bytes(canvas)

    def _calculate_tracking_marker(
        self,
        image: Image.Image,
        tracking_state: Optional[Dict[str, Any]],
        detections: list[dict[str, Any]],
        frame_timestamp: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Derive tracking offset + overlay metadata."""
        if not tracking_state:
            return None

        enabled = tracking_state.get("enabled")
        raw_mode = tracking_state.get("mode", "none")
        mode = str(raw_mode or "none").lower()
        if not enabled or mode not in {"face", "hand"}:
            return None

        timestamp = frame_timestamp or tracking_state.get("ts") or time.time()
        rgb_frame: Optional[np.ndarray] = None

        try:
            if ((mode == "face" and self._mp_face) or (mode == "hand" and self._mp_hands)) and Image:
                rgb_frame = np.array(image.convert("RGB"))
        except Exception as exc:
            self.logger.debug("[vision] Failed to convert frame for tracking: %s", exc)
            rgb_frame = None

        marker: Optional[Dict[str, Any]] = None
        if mode == "face" and self._mp_face and rgb_frame is not None:
            marker = self._tracking_from_face(rgb_frame, image.size)
        elif mode == "hand" and self._mp_hands and rgb_frame is not None:
            marker = self._tracking_from_hand(rgb_frame, image.size)

        if marker is None:
            marker = self._tracking_from_detections(image.size, detections, mode)

        if marker:
            marker["mode"] = mode
            marker["ts"] = timestamp
            marker.setdefault("source", "pc")
        return marker

    def _tracking_from_face(self, rgb_frame: np.ndarray, image_size: Tuple[int, int]) -> Optional[Dict[str, Any]]:
        if not self._mp_face:
            return None
        try:
            results = self._mp_face.process(rgb_frame)
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.debug("[vision] MediaPipe face detection failed: %s", exc)
            return None

        if not results or not results.detections:
            return None

        detection = results.detections[0]
        if not detection.location_data.HasField("relative_bounding_box"):
            return None
        bbox = detection.location_data.relative_bounding_box
        center_x = bbox.xmin + bbox.width / 2.0
        center_y = bbox.ymin + bbox.height / 2.0
        offset = self._offset_from_center(center_x)
        width, height = image_size
        radius = int(max(bbox.width * width, bbox.height * height) / 2.0)
        confidence = float(detection.score[0]) if detection.score else None
        return self._build_tracking_payload(
            offset=offset,
            confidence=confidence,
            center=(center_x * width, center_y * height),
            radius=radius,
        )

    def _tracking_from_hand(self, rgb_frame: np.ndarray, image_size: Tuple[int, int]) -> Optional[Dict[str, Any]]:
        if not self._mp_hands:
            return None
        try:
            results = self._mp_hands.process(rgb_frame)
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.debug("[vision] MediaPipe hand detection failed: %s", exc)
            return None

        if not results or not results.multi_hand_landmarks:
            return None

        hand = results.multi_hand_landmarks[0]
        xs = [lm.x for lm in hand.landmark]
        ys = [lm.y for lm in hand.landmark]
        center_x = sum(xs) / len(xs)
        center_y = sum(ys) / len(ys)
        offset = self._offset_from_center(center_x)
        width, height = image_size
        span_x = (max(xs) - min(xs)) * width
        span_y = (max(ys) - min(ys)) * height
        radius = int(max(span_x, span_y) / 2.0)
        confidence = None
        try:
            if results.multi_handedness:
                confidence = float(results.multi_handedness[0].classification[0].score)
        except Exception:
            confidence = None

        return self._build_tracking_payload(
            offset=offset,
            confidence=confidence,
            center=(center_x * width, center_y * height),
            radius=radius,
        )

    def _tracking_from_detections(
        self, image_size: Tuple[int, int], detections: list[dict[str, Any]], mode: str
    ) -> Optional[Dict[str, Any]]:
        if not detections:
            return None

        preferred = ["hand", "person"] if mode == "hand" else ["person", "face"]
        candidate = None
        for det in detections:
            cls_name = str(det.get("class") or "").lower()
            if cls_name in preferred:
                candidate = det
                break
        if candidate is None:
            candidate = detections[0]

        bbox = candidate.get("bbox") or [0, 0, 0, 0]
        width, height = image_size
        try:
            x1, y1, x2, y2 = [float(v) for v in bbox]
        except Exception:
            return None
        center_x = (x1 + x2) / 2.0 / max(width, 1)
        center_y = (y1 + y2) / 2.0 / max(height, 1)
        offset = self._offset_from_center(center_x)
        radius = int(max(x2 - x1, y2 - y1) / 2.0)
        confidence = candidate.get("confidence")
        if confidence is not None:
            try:
                confidence = float(confidence)
            except Exception:
                confidence = None

        return self._build_tracking_payload(
            offset=offset,
            confidence=confidence,
            center=(center_x * width, center_y * height),
            radius=radius,
        )

    def _offset_from_center(self, normalized_center_x: float) -> float:
        offset = (normalized_center_x - 0.5) * 2.0
        if abs(offset) < self._tracking_dead_zone:
            offset = 0.0
        return max(-1.0, min(1.0, offset))

    def _build_tracking_payload(
        self,
        offset: float,
        confidence: Optional[float],
        center: Tuple[float, float],
        radius: Optional[int],
        timestamp: Optional[float] = None,
    ) -> Dict[str, Any]:
        cx, cy = center
        payload: Dict[str, Any] = {
            "offset": round(float(offset), 4),
            "confidence": confidence if confidence is None else round(float(confidence), 3),
            "center": [int(cx), int(cy)],
            "radius": int(radius) if radius else None,
            "ts": timestamp or time.time(),
            "source": "pc",
        }
        return payload

    def _update_tracker_snapshot(
        self, image: Image.Image, detections: list[dict[str, Any]], tracking_marker: Optional[Dict[str, Any]] = None
    ) -> None:
        now = time.time()
        delta = now - self._tracker_last_frame_ts if self._tracker_last_frame_ts else 0.0
        self._tracker_last_frame_ts = now
        if delta > 0:
            self._tracker_fps = 1.0 / delta
        self._tracker_overlay = self._render_tracker_overlay(image, detections, tracking_marker)
        self._tracker_ts = now

    def _render_tracker_overlay(
        self, image: Image.Image, detections: list[dict[str, Any]], tracking_marker: Optional[Dict[str, Any]] = None
    ) -> bytes:
        canvas = image.convert("RGBA")
        draw = ImageDraw.Draw(canvas)
        font = ImageFont.load_default() if ImageFont else None
        for det in detections:
            bbox = det.get("bbox", [0, 0, 0, 0])
            draw.rectangle(bbox, outline=(100, 255, 100), width=3)
            label = f"{det.get('class','')} {det.get('confidence',0):.2f}"
            draw.text((bbox[0], max(0, bbox[1] - 14)), label, fill=(0, 255, 0), font=font)
        draw.text((10, 10), f"FPS: {self._tracker_fps:.1f}", fill=(255, 255, 0), font=font)
        width, height = canvas.size
        draw.line([(width / 2, 0), (width / 2, height)], fill=(80, 80, 80), width=1)
        if tracking_marker and tracking_marker.get("center"):
            cx, cy = tracking_marker["center"]
            radius = tracking_marker.get("radius") or 35
            mode_label = tracking_marker.get("mode", "").upper()
            offset = tracking_marker.get("offset")
            color = (0, 200, 255) if mode_label == "HAND" else (255, 200, 0)
            draw.ellipse(
                [(cx - radius, cy - radius), (cx + radius, cy + radius)],
                outline=color,
                width=3,
            )
            draw.ellipse([(cx - 5, cy - 5), (cx + 5, cy + 5)], fill=color)
            if offset is not None:
                text = f"{mode_label or 'MODE'} {offset:+.2f}"
                draw.text((10, 30), text, fill=color, font=font)
        return self._to_png_bytes(canvas)

    def _to_png_bytes(self, image: Image.Image) -> bytes:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def get_tracker_snapshot(self) -> tuple[bytes, float, float]:
        return self._tracker_overlay, self._tracker_ts, self._tracker_fps

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
        tracking_state = task.meta.get("tracking_state")
        frame: Optional[Image.Image] = None

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
                overlay_detections: list[Dict[str, Any]] = []

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
                            overlay_detections.append(
                                {
                                    "class": class_name,
                                    "confidence": round(confidence, 2),
                                    "bbox": [int(x1), int(y1), int(x2), int(y2)],
                                }
                            )

                self.logger.info(f"[vision] Frame {frame_id} processed, found {len(obstacles)} obstacles")

                # Update metrics
                tasks_processed_total.labels(
                    provider='VisionProvider', task_type='vision.frame', status='completed'
                ).inc()

                tracking_marker = None
                if frame is not None:
                    tracking_marker = self._calculate_tracking_marker(
                        frame, tracking_state, overlay_detections, timestamp
                    )
                    self._update_tracker_snapshot(frame, overlay_detections, tracking_marker)

                result_payload: Dict[str, Any] = {
                    "frame_id": frame_id,
                    "timestamp": timestamp,
                    "obstacles": obstacles,
                    "should_avoid": len(obstacles) > 0,
                    "suggested_action": "slow_down" if obstacles else "continue",
                }
                if tracking_marker:
                    result_payload["tracking"] = tracking_marker

                return TaskResult(
                    task_id=task.task_id,
                    status=TaskStatus.COMPLETED,
                    result=result_payload,
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

        fallback_image = frame
        if fallback_image is None:
            fallback_image = Image.new("RGBA", (640, 360), (20, 20, 30, 255))
        tracking_marker = self._calculate_tracking_marker(fallback_image, tracking_state, [], timestamp)
        self._update_tracker_snapshot(fallback_image, [], tracking_marker)

        result_payload = {
            "frame_id": frame_id,
            "timestamp": timestamp,
            "obstacles": obstacles,
            "should_avoid": len(obstacles) > 0,
            "suggested_action": "slow_down" if obstacles else "continue",
        }
        if tracking_marker:
            result_payload["tracking"] = tracking_marker

        return TaskResult(
            task_id=task.task_id,
            status=TaskStatus.COMPLETED,
            result=result_payload,
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
