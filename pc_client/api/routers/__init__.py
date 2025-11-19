"""Router initialization."""

from .status_router import router as status_router
from .provider_router import router as provider_router
from .control_router import router as control_router

__all__ = ["status_router", "provider_router", "control_router"]
