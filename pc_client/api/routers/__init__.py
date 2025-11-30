"""Router initialization.

This module re-exports router modules so they can be imported both as FastAPI
routers (via the ``router`` attribute) and as modules for testing/monkeypatching.
"""

from . import status_router
from . import provider_router
from . import control_router
from . import voice_router
from . import chat_router
from . import project_router
from . import model_router
from . import knowledge_router
from . import home_router

__all__ = [
    "status_router",
    "provider_router",
    "control_router",
    "voice_router",
    "chat_router",
    "project_router",
    "model_router",
    "knowledge_router",
    "home_router",
]
