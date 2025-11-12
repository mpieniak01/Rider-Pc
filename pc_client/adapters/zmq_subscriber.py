"""ZMQ subscriber for consuming real-time data streams from Rider-PI."""

import zmq
import json
import logging
import asyncio
from typing import Callable, Dict, Any, Optional, List
from zmq.asyncio import Context

logger = logging.getLogger(__name__)


class ZmqSubscriber:
    """Subscriber for ZMQ PUB/SUB streams from Rider-PI."""
    
    def __init__(self, endpoint: str, topics: Optional[List[str]] = None):
        """
        Initialize the ZMQ subscriber.
        
        Args:
            endpoint: ZMQ endpoint to connect to (e.g., tcp://robot-ip:5555)
            topics: List of topics to subscribe to (empty list means all topics)
        """
        self.endpoint = endpoint
        self.topics = topics or []
        self.context: Optional[Context] = None
        self.socket: Optional[zmq.asyncio.Socket] = None
        self.running = False
        self.handlers: Dict[str, List[Callable]] = {}
    
    def subscribe_topic(self, topic: str, handler: Callable[[str, Dict[str, Any]], None]):
        """
        Subscribe to a specific topic with a handler.
        
        Args:
            topic: Topic pattern to subscribe to (e.g., "vision.*", "motion.state")
            handler: Callback function to handle messages (receives topic and data)
        """
        if topic not in self.handlers:
            self.handlers[topic] = []
        self.handlers[topic].append(handler)
        logger.info(f"Registered handler for topic: {topic}")
    
    async def start(self):
        """Start the ZMQ subscriber."""
        if self.running:
            logger.warning("ZMQ subscriber already running")
            return
        
        try:
            self.context = Context()
            self.socket = self.context.socket(zmq.SUB)
            
            # Connect to endpoint
            self.socket.connect(self.endpoint)
            logger.info(f"Connected to ZMQ endpoint: {self.endpoint}")
            
            # Subscribe to topics
            if not self.topics:
                # Subscribe to all topics
                self.socket.setsockopt_string(zmq.SUBSCRIBE, "")
                logger.info("Subscribed to all topics")
            else:
                for topic in self.topics:
                    self.socket.setsockopt_string(zmq.SUBSCRIBE, topic)
                    logger.info(f"Subscribed to topic: {topic}")
            
            self.running = True
            
            # Start message loop
            await self._message_loop()
            
        except Exception as e:
            logger.error(f"Error starting ZMQ subscriber: {e}")
            await self.stop()
            raise
    
    async def _message_loop(self):
        """Main message receiving loop."""
        while self.running:
            try:
                # Receive message with topic
                message = await self.socket.recv_multipart()
                
                if len(message) < 2:
                    logger.warning(f"Invalid message format: {message}")
                    continue
                
                topic = message[0].decode("utf-8")
                data_bytes = message[1]
                
                # Parse JSON data
                try:
                    data = json.loads(data_bytes.decode("utf-8"))
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON for topic {topic}: {e}")
                    continue
                
                logger.debug(f"Received message on topic: {topic}")
                
                # Call registered handlers
                await self._handle_message(topic, data)
                
            except asyncio.CancelledError:
                logger.info("Message loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in message loop: {e}")
                if not self.running:
                    break
                # Continue processing even if one message fails
                await asyncio.sleep(0.1)
    
    async def _handle_message(self, topic: str, data: Dict[str, Any]):
        """
        Handle a received message by calling registered handlers.
        
        Args:
            topic: Message topic
            data: Message data
        """
        handled = False
        
        # Call handlers for matching topics
        for pattern, handlers in self.handlers.items():
            if self._topic_matches(topic, pattern):
                for handler in handlers:
                    try:
                        # Support both sync and async handlers
                        if asyncio.iscoroutinefunction(handler):
                            await handler(topic, data)
                        else:
                            handler(topic, data)
                        handled = True
                    except Exception as e:
                        logger.error(f"Error in handler for topic {topic}: {e}")
        
        if not handled:
            logger.debug(f"No handler found for topic: {topic}")
    
    def _topic_matches(self, topic: str, pattern: str) -> bool:
        """
        Check if a topic matches a pattern.
        
        Args:
            topic: Full topic string
            pattern: Pattern with wildcards (* for any characters)
            
        Returns:
            True if topic matches pattern
        """
        # Simple wildcard matching
        if pattern == "":
            return True
        
        if "*" not in pattern:
            return topic == pattern
        
        # Convert pattern to regex-like matching
        pattern_parts = pattern.split("*")
        
        # Check if topic starts with first part
        if pattern_parts[0] and not topic.startswith(pattern_parts[0]):
            return False
        
        # Check if topic ends with last part
        if pattern_parts[-1] and not topic.endswith(pattern_parts[-1]):
            return False
        
        return True
    
    async def stop(self):
        """Stop the ZMQ subscriber."""
        if not self.running:
            return
        
        logger.info("Stopping ZMQ subscriber...")
        self.running = False
        
        if self.socket:
            self.socket.close()
            self.socket = None
        
        if self.context:
            self.context.term()
            self.context = None
        
        logger.info("ZMQ subscriber stopped")
    
    async def __aenter__(self):
        """Context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.stop()
