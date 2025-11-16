"""Tests for the ZMQ subscriber."""

import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock

from pc_client.adapters import ZmqSubscriber


def test_topic_matching():
    """Test topic pattern matching."""
    subscriber = ZmqSubscriber("tcp://test:5555")

    # Exact match
    assert subscriber._topic_matches("vision.obstacle", "vision.obstacle")

    # Wildcard match
    assert subscriber._topic_matches("vision.obstacle", "vision.*")
    assert subscriber._topic_matches("vision.person", "vision.*")

    # No match
    assert not subscriber._topic_matches("motion.state", "vision.*")

    # Empty pattern (matches all)
    assert subscriber._topic_matches("any.topic", "")


def test_subscribe_topic():
    """Test subscribing to a topic."""
    subscriber = ZmqSubscriber("tcp://test:5555")

    handler = Mock()
    subscriber.subscribe_topic("vision.*", handler)

    assert "vision.*" in subscriber.handlers
    assert handler in subscriber.handlers["vision.*"]


@pytest.mark.asyncio
async def test_handle_message():
    """Test message handling."""
    subscriber = ZmqSubscriber("tcp://test:5555")

    # Register handler
    handler = Mock()
    subscriber.subscribe_topic("test.*", handler)

    # Handle message
    await subscriber._handle_message("test.topic", {"data": "value"})

    # Verify handler was called
    handler.assert_called_once_with("test.topic", {"data": "value"})


@pytest.mark.asyncio
async def test_handle_message_async_handler():
    """Test message handling with async handler."""
    subscriber = ZmqSubscriber("tcp://test:5555")

    # Register async handler
    async_handler = AsyncMock()
    subscriber.subscribe_topic("test.*", async_handler)

    # Handle message
    await subscriber._handle_message("test.topic", {"data": "value"})

    # Verify async handler was called
    async_handler.assert_called_once_with("test.topic", {"data": "value"})


@pytest.mark.asyncio
async def test_handle_message_multiple_handlers():
    """Test message handling with multiple handlers."""
    subscriber = ZmqSubscriber("tcp://test:5555")

    # Register multiple handlers
    handler1 = Mock()
    handler2 = Mock()
    subscriber.subscribe_topic("test.*", handler1)
    subscriber.subscribe_topic("test.*", handler2)

    # Handle message
    await subscriber._handle_message("test.topic", {"data": "value"})

    # Verify both handlers were called
    handler1.assert_called_once_with("test.topic", {"data": "value"})
    handler2.assert_called_once_with("test.topic", {"data": "value"})


@pytest.mark.asyncio
async def test_handle_message_no_match():
    """Test message handling when no handler matches."""
    subscriber = ZmqSubscriber("tcp://test:5555")

    # Register handler for different topic
    handler = Mock()
    subscriber.subscribe_topic("other.*", handler)

    # Handle message that doesn't match
    await subscriber._handle_message("test.topic", {"data": "value"})

    # Verify handler was not called
    handler.assert_not_called()


def test_zmq_endpoint_property():
    """Test ZMQ endpoint configuration."""
    subscriber = ZmqSubscriber("tcp://192.168.1.100:5555")
    assert subscriber.endpoint == "tcp://192.168.1.100:5555"


def test_topics_initialization():
    """Test topics initialization."""
    # No topics specified
    subscriber1 = ZmqSubscriber("tcp://test:5555")
    assert subscriber1.topics == []

    # Topics specified
    subscriber2 = ZmqSubscriber("tcp://test:5555", topics=["vision.*", "motion.*"])
    assert subscriber2.topics == ["vision.*", "motion.*"]
