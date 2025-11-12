"""Base classes for AI providers."""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """Supported task types."""
    VOICE_ASR = "voice.asr"
    VOICE_TTS = "voice.tts"
    VISION_DETECTION = "vision.detection"
    VISION_FRAME = "vision.frame"
    TEXT_GENERATE = "text.generate"
    TEXT_NLU = "text.nlu"


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskEnvelope:
    """
    Unified JSON envelope for task offload.
    
    This format is used for communication between Rider-PI and PC providers.
    """
    task_id: str
    task_type: TaskType
    payload: Dict[str, Any]
    meta: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5  # 1 (highest) to 10 (lowest)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskEnvelope":
        """Create from dictionary."""
        return cls(
            task_id=data["task_id"],
            task_type=TaskType(data["task_type"]),
            payload=data["payload"],
            meta=data.get("meta", {}),
            priority=data.get("priority", 5)
        )


@dataclass
class TaskResult:
    """
    Result of a task execution.
    """
    task_id: str
    status: TaskStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    processing_time_ms: Optional[float] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskResult":
        """Create from dictionary."""
        return cls(
            task_id=data["task_id"],
            status=TaskStatus(data["status"]),
            result=data.get("result"),
            error=data.get("error"),
            processing_time_ms=data.get("processing_time_ms"),
            meta=data.get("meta", {})
        )


class BaseProvider(ABC):
    """
    Base class for all AI providers.
    
    Providers handle specific domains (voice, vision, text) and process
    offloaded tasks from Rider-PI using PC computational resources.
    """
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the provider.
        
        Args:
            name: Provider name (e.g., "VoiceProvider", "VisionProvider")
            config: Provider-specific configuration
        """
        self.name = name
        self.config = config or {}
        self.logger = logging.getLogger(f"[provider] {name}")
        self._initialized = False
    
    async def initialize(self) -> None:
        """
        Initialize provider resources.
        
        Override this method to load models, establish connections, etc.
        """
        if self._initialized:
            self.logger.warning(f"{self.name} already initialized")
            return
        
        self.logger.info(f"Initializing {self.name}...")
        await self._initialize_impl()
        self._initialized = True
        self.logger.info(f"{self.name} initialized successfully")
    
    @abstractmethod
    async def _initialize_impl(self) -> None:
        """Implementation-specific initialization."""
        pass
    
    async def shutdown(self) -> None:
        """
        Shutdown provider and cleanup resources.
        
        Override this method to cleanup models, close connections, etc.
        """
        if not self._initialized:
            return
        
        self.logger.info(f"Shutting down {self.name}...")
        await self._shutdown_impl()
        self._initialized = False
        self.logger.info(f"{self.name} shut down successfully")
    
    @abstractmethod
    async def _shutdown_impl(self) -> None:
        """Implementation-specific shutdown."""
        pass
    
    async def process_task(self, task: TaskEnvelope) -> TaskResult:
        """
        Process a task envelope.
        
        Args:
            task: Task envelope to process
            
        Returns:
            Task result with status and output
        """
        if not self._initialized:
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error="Provider not initialized"
            )
        
        self.logger.info(f"Processing task {task.task_id} (type: {task.task_type})")
        start_time = time.time()
        
        try:
            result = await self._process_task_impl(task)
            processing_time_ms = (time.time() - start_time) * 1000
            
            result.processing_time_ms = processing_time_ms
            self.logger.info(
                f"Task {task.task_id} completed in {processing_time_ms:.2f}ms"
            )
            
            return result
            
        except Exception as e:
            processing_time_ms = (time.time() - start_time) * 1000
            self.logger.error(f"Task {task.task_id} failed: {e}", exc_info=True)
            
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error=str(e),
                processing_time_ms=processing_time_ms
            )
    
    @abstractmethod
    async def _process_task_impl(self, task: TaskEnvelope) -> TaskResult:
        """
        Implementation-specific task processing.
        
        Args:
            task: Task envelope to process
            
        Returns:
            Task result
        """
        pass
    
    def get_supported_tasks(self) -> list[TaskType]:
        """
        Get list of supported task types.
        
        Returns:
            List of supported task types
        """
        return []
    
    def get_telemetry(self) -> Dict[str, Any]:
        """
        Get provider telemetry data.
        
        Returns:
            Dictionary with telemetry metrics
        """
        return {
            "provider": self.name,
            "initialized": self._initialized,
            "supported_tasks": [t.value for t in self.get_supported_tasks()]
        }
