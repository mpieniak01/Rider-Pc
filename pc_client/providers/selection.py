"""Lekkie identyfikatory konfiguracji bez importów bibliotek AI."""

BACKEND_LOCAL = "local"
BACKEND_GEMINI = "gemini"
BACKEND_CHATGPT = "chatgpt"
BACKEND_AUTO = "auto"
BACKEND_MOCK = "mock"
VALID_BACKENDS = {BACKEND_LOCAL, BACKEND_GEMINI, BACKEND_CHATGPT, BACKEND_AUTO}
