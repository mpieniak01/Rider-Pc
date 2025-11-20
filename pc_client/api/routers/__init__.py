"""Router initialization."""

from .status_router import router as status_router
from .provider_router import router as provider_router
from .control_router import router as control_router
from .voice_router import router as voice_router
from .chat_router import router as chat_router

__all__ = ["status_router", "provider_router", "control_router", "voice_router", "chat_router"]
