"""Adapters for consuming Rider-PI data."""

from .rest_adapter import RestAdapter
from .zmq_subscriber import ZmqSubscriber
from .mock_rest_adapter import MockRestAdapter
from .systemd_adapter import SystemdAdapter, MockSystemdAdapter, is_systemd_available
from .git_adapter import GitAdapter, MockGitAdapter, is_git_available

__all__ = [
    "RestAdapter",
    "ZmqSubscriber",
    "MockRestAdapter",
    "SystemdAdapter",
    "MockSystemdAdapter",
    "is_systemd_available",
    "GitAdapter",
    "MockGitAdapter",
    "is_git_available",
]
