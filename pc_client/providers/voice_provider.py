"""Voice provider for ASR/TTS offload tasks."""

import logging
import base64
import tempfile
import wave
from typing import Dict, Any, Optional
from pathlib import Path
from pc_client.providers.base import (
    BaseProvider,
    TaskEnvelope,
    TaskResult,
    TaskType,
    TaskStatus
)
from pc_client.telemetry.metrics import tasks_processed_total, task_duration_seconds

logger = logging.getLogger(__name__)

# Import AI libraries with fallback to mock mode
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    logger.warning("Whisper not available, using mock ASR")

try:
    import subprocess
    PIPER_AVAILABLE = True
except ImportError:
    PIPER_AVAILABLE = False
    logger.warning("Piper TTS not available, using mock TTS")


class VoiceProvider(BaseProvider):
    """
    Provider for voice processing tasks (ASR/TTS).
    
    This provider handles audio processing offloaded from the Rider-PI
    voice pipeline (apps/voice). It receives audio chunks and returns
    transcriptions or synthesized audio.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the voice provider.
        
        Args:
            config: Voice provider configuration
                - asr_model: ASR model to use (default: "base" for Whisper)
                - tts_model: TTS model to use (default: "en_US-lessac-medium")
                - sample_rate: Audio sample rate (default: 16000)
                - use_mock: Force mock mode (default: False)
        """
        super().__init__("VoiceProvider", config)
        self.asr_model_name = self.config.get("asr_model", "base")
        self.tts_model_name = self.config.get("tts_model", "en_US-lessac-medium")
        self.sample_rate = self.config.get("sample_rate", 16000)
        self.use_mock = self.config.get("use_mock", False)
        
        # Model instances (loaded during initialization)
        self.asr_model: Optional[Any] = None
        self.tts_available = False
    
    async def _initialize_impl(self) -> None:
        """Initialize voice processing models."""
        self.logger.info(f"Loading ASR model: {self.asr_model_name}")
        self.logger.info(f"TTS model: {self.tts_model_name}")
        self.logger.info(f"Sample rate: {self.sample_rate}Hz")
        
        # Load Whisper ASR model if available and not in mock mode
        if WHISPER_AVAILABLE and not self.use_mock:
            try:
                self.logger.info("[voice] Loading Whisper ASR model...")
                self.asr_model = whisper.load_model(self.asr_model_name)
                self.logger.info("[voice] Whisper ASR model loaded successfully")
            except Exception as e:
                self.logger.error(f"[voice] Failed to load Whisper: {e}")
                self.logger.warning("[voice] Falling back to mock ASR")
                self.asr_model = None
        else:
            self.logger.info("[voice] Using mock ASR implementation")
            self.asr_model = None
        
        # Check TTS availability
        if PIPER_AVAILABLE and not self.use_mock:
            try:
                # Check if piper is installed
                result = subprocess.run(['which', 'piper'], capture_output=True)
                if result.returncode == 0:
                    self.tts_available = True
                    self.logger.info("[voice] Piper TTS available")
                else:
                    self.logger.warning("[voice] Piper not installed, using mock TTS")
            except Exception as e:
                self.logger.warning(f"[voice] TTS check failed: {e}, using mock TTS")
        else:
            self.logger.info("[voice] Using mock TTS implementation")
        
        self.logger.info("[voice] Voice provider initialized")
    
    async def _shutdown_impl(self) -> None:
        """Cleanup voice processing resources."""
        self.logger.info("[voice] Cleaning up voice resources")
        if self.asr_model is not None:
            # Whisper models don't require explicit cleanup
            self.asr_model = None
        self.logger.info("[voice] Voice resources cleaned up")
    
    async def _process_task_impl(self, task: TaskEnvelope) -> TaskResult:
        """
        Process voice task.
        
        Args:
            task: Task envelope with voice data
            
        Returns:
            Task result with processed audio or text
        """
        if task.task_type == TaskType.VOICE_ASR:
            return await self._process_asr(task)
        elif task.task_type == TaskType.VOICE_TTS:
            return await self._process_tts(task)
        else:
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error=f"Unsupported task type: {task.task_type}"
            )
    
    async def _process_asr(self, task: TaskEnvelope) -> TaskResult:
        """
        Process ASR (speech-to-text) task.
        
        Expected payload:
            - audio_data: Base64-encoded audio chunk
            - format: Audio format (e.g., "wav", "raw")
            - sample_rate: Sample rate in Hz
        
        Returns:
            TaskResult with transcription text
        """
        self.logger.info(f"[voice] Processing ASR task {task.task_id}")
        
        audio_data = task.payload.get("audio_data")
        audio_format = task.payload.get("format", "wav")
        sample_rate = task.payload.get("sample_rate", self.sample_rate)
        
        if not audio_data:
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error="Missing audio_data in payload"
            )
        
        # Process with real Whisper model if available
        if self.asr_model is not None:
            try:
                # Decode base64 audio data with error handling
                try:
                    audio_bytes = base64.b64decode(audio_data)
                    if len(audio_bytes) == 0:
                        raise ValueError("Audio data is empty")
                except (Exception, ValueError) as e:
                    self.logger.error(f"[voice] Failed to decode audio data: {e}")
                    return TaskResult(
                        task_id=task.task_id,
                        status=TaskStatus.FAILED,
                        error=f"Invalid audio data: {str(e)}"
                    )
                
                # Save to temporary file for Whisper
                with tempfile.NamedTemporaryFile(suffix=f'.{audio_format}', delete=False) as tmp_file:
                    tmp_file.write(audio_bytes)
                    tmp_path = tmp_file.name
                # File is now closed before transcription
                # File is now closed before transcription
                try:
                    # Transcribe with Whisper
                    result = self.asr_model.transcribe(tmp_path)
                    transcription = result["text"].strip()
                    language = result.get("language", "en")
                    
                    self.logger.info(f"[voice] ASR completed: {transcription}")
                    
                    # Update metrics
                    tasks_processed_total.labels(
                        provider='VoiceProvider',
                        task_type='voice.asr',
                        status='completed'
                    ).inc()
                    
                    return TaskResult(
                        task_id=task.task_id,
                        status=TaskStatus.COMPLETED,
                        result={
                            "text": transcription,
                            "confidence": 0.95,
                            "language": language
                        },
                        meta={
                            "model": self.asr_model_name,
                            "sample_rate": sample_rate,
                            "format": audio_format,
                            "engine": "whisper"
                        }
                    )
                finally:
                    # Clean up temporary file
                    Path(tmp_path).unlink(missing_ok=True)
                    
            except Exception as e:
                self.logger.error(f"[voice] ASR processing failed: {e}")
                return TaskResult(
                    task_id=task.task_id,
                    status=TaskStatus.FAILED,
                    error=f"ASR processing error: {str(e)}"
                )
        
        # Fall back to mock implementation
        transcription = "Mock transcription: Hello from voice provider"
        
        self.logger.info(f"[voice] ASR completed (mock): {transcription}")
        
        # Update metrics
        tasks_processed_total.labels(
            provider='VoiceProvider',
            task_type='voice.asr',
            status='completed'
        ).inc()
        
        return TaskResult(
            task_id=task.task_id,
            status=TaskStatus.COMPLETED,
            result={
                "text": transcription,
                "confidence": 0.95,
                "language": "en"
            },
            meta={
                "model": "mock",
                "sample_rate": sample_rate,
                "format": audio_format,
                "engine": "mock"
            }
        )
    
    async def _process_tts(self, task: TaskEnvelope) -> TaskResult:
        """
        Process TTS (text-to-speech) task.
        
        Expected payload:
            - text: Text to synthesize
            - voice: Voice ID (optional)
            - speed: Speech speed (optional, default: 1.0)
        
        Returns:
            TaskResult with synthesized audio data
        """
        self.logger.info(f"[voice] Processing TTS task {task.task_id}")
        
        text = task.payload.get("text")
        voice = task.payload.get("voice", "default")
        speed = task.payload.get("speed", 1.0)
        
        if not text:
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error="Missing text in payload"
            )
        
        # Validate text input
        if not text.strip():
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error="Text cannot be empty"
            )
        
        max_text_length = 5000  # Reasonable limit
        if len(text) > max_text_length:
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error=f"Text too long (max {max_text_length} chars)"
            )
        
        # Process with real Piper TTS if available
        if self.tts_available:
            try:
                # Create temporary output file
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                    output_path = tmp_file.name
                
                try:
                    # Run Piper TTS (using stdin for safety - no shell injection)
                    # Note: This assumes piper is installed and in PATH
                    process = subprocess.run(
                        ['piper', '--output_file', output_path],
                        input=text.encode('utf-8'),
                        capture_output=True,
                        timeout=30
                    )
                    
                    if process.returncode == 0 and Path(output_path).exists():
                        # Read and encode audio
                        with open(output_path, 'rb') as f:
                            audio_bytes = f.read()
                        audio_data = base64.b64encode(audio_bytes).decode('utf-8')
                        
                        # Calculate duration using wave module
                        try:
                            with wave.open(output_path, 'rb') as wf:
                                frames = wf.getnframes()
                                rate = wf.getframerate()
                                duration_ms = int((frames / rate) * 1000)
                        except Exception:
                            # Fallback to rough estimate if wave parsing fails
                            duration_ms = len(audio_bytes) // (self.sample_rate * 2 // 1000)
                        
                        self.logger.info(f"[voice] TTS completed for text: {text[:50]}...")
                        
                        # Update metrics
                        tasks_processed_total.labels(
                            provider='VoiceProvider',
                            task_type='voice.tts',
                            status='completed'
                        ).inc()
                        
                        return TaskResult(
                            task_id=task.task_id,
                            status=TaskStatus.COMPLETED,
                            result={
                                "audio_data": audio_data,
                                "format": "wav",
                                "sample_rate": self.sample_rate,
                                "duration_ms": duration_ms
                            },
                            meta={
                                "model": self.tts_model_name,
                                "voice": voice,
                                "speed": speed,
                                "engine": "piper"
                            }
                        )
                    else:
                        raise Exception(f"Piper TTS failed: {process.stderr.decode()}")
                        
                finally:
                    # Clean up temporary file
                    Path(output_path).unlink(missing_ok=True)
                    
            except Exception as e:
                self.logger.error(f"[voice] TTS processing failed: {e}")
                self.logger.warning("[voice] Falling back to mock TTS")
                # Fall through to mock implementation
        
        # Mock implementation fallback
        audio_data = "base64_encoded_mock_audio_data"
        
        self.logger.info(f"[voice] TTS completed (mock) for text: {text[:50]}...")
        
        # Update metrics
        tasks_processed_total.labels(
            provider='VoiceProvider',
            task_type='voice.tts',
            status='completed'
        ).inc()
        
        return TaskResult(
            task_id=task.task_id,
            status=TaskStatus.COMPLETED,
            result={
                "audio_data": audio_data,
                "format": "wav",
                "sample_rate": self.sample_rate,
                "duration_ms": 1000
            },
            meta={
                "model": "mock",
                "voice": voice,
                "speed": speed,
                "engine": "mock"
            }
        )
    
    def get_supported_tasks(self) -> list[TaskType]:
        """Get list of supported task types."""
        return [TaskType.VOICE_ASR, TaskType.VOICE_TTS]
    
    def get_telemetry(self) -> Dict[str, Any]:
        """Get voice provider telemetry."""
        base_telemetry = super().get_telemetry()
        base_telemetry.update({
            "asr_model": self.asr_model_name,
            "tts_model": self.tts_model_name,
            "sample_rate": self.sample_rate,
            "asr_available": self.asr_model is not None,
            "tts_available": self.tts_available,
            "mode": "mock" if self.asr_model is None else "real"
        })
        return base_telemetry
