"""WebSocket Connection Manager"""

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field

from fastapi import WebSocket

from finbot.core.websocket.events import WSEvent, WSEventType

logger = logging.getLogger(__name__)


@dataclass
class Connection:
    """Represents a WebSocket connection"""

    websocket: WebSocket
    user_id: str
    namespace: str
    subscriptions: set[str] = field(default_factory=set)


class WebSocketManager:
    """
    Manages WebSocket connections and message broadcasting.

    Supports:
    - Multiple connections per user (different browser tabs)
    - Topic-based subscriptions
    - Broadcast to specific users or topics
    """

    def __init__(self):
        # Active connections by connection ID
        self._connections: dict[str, Connection] = {}

        # Connections indexed by user (namespace:user_id -> [connection_ids])
        self._user_connections: dict[str, set[str]] = defaultdict(set)

        # Connections indexed by topic (topic -> [connection_ids])
        self._topic_subscriptions: dict[str, set[str]] = defaultdict(set)

        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

        # Connection counter for unique IDs
        self._connection_counter = 0

    async def connect(
        self,
        websocket: WebSocket,
        user_id: str,
        namespace: str,
    ) -> str:
        """
        Accept a new WebSocket connection.

        Returns connection ID.
        """
        await websocket.accept()

        async with self._lock:
            self._connection_counter += 1
            connection_id = f"conn_{self._connection_counter}"

            connection = Connection(
                websocket=websocket,
                user_id=user_id,
                namespace=namespace,
            )

            self._connections[connection_id] = connection

            user_key = f"{namespace}:{user_id}"
            self._user_connections[user_key].add(connection_id)

            # Auto-subscribe to user's activity topic
            activity_topic = f"activity:{namespace}:{user_id}"
            connection.subscriptions.add(activity_topic)
            self._topic_subscriptions[activity_topic].add(connection_id)

        logger.info("WebSocket connected: %s (user: %s)", connection_id, user_id)

        # Send connected confirmation
        await self.send_to_connection(
            connection_id,
            WSEvent(type=WSEventType.CONNECTED, data={"connection_id": connection_id}),
        )

        return connection_id

    async def disconnect(self, connection_id: str):
        """Disconnect and cleanup a WebSocket connection"""
        async with self._lock:
            connection = self._connections.pop(connection_id, None)
            if not connection:
                return

            # Remove from user index
            user_key = f"{connection.namespace}:{connection.user_id}"
            self._user_connections[user_key].discard(connection_id)
            if not self._user_connections[user_key]:
                del self._user_connections[user_key]

            # Remove from topic subscriptions
            for topic in connection.subscriptions:
                self._topic_subscriptions[topic].discard(connection_id)
                if not self._topic_subscriptions[topic]:
                    del self._topic_subscriptions[topic]

        logger.info("WebSocket disconnected: %s", connection_id)

    async def subscribe(self, connection_id: str, topic: str) -> bool:
        """Subscribe a connection to a topic"""
        async with self._lock:
            connection = self._connections.get(connection_id)
            if not connection:
                return False

            connection.subscriptions.add(topic)
            self._topic_subscriptions[topic].add(connection_id)

        await self.send_to_connection(
            connection_id, WSEvent(type=WSEventType.SUBSCRIBED, data={"topic": topic})
        )

        return True

    async def unsubscribe(self, connection_id: str, topic: str) -> bool:
        """Unsubscribe a connection from a topic"""
        async with self._lock:
            connection = self._connections.get(connection_id)
            if not connection:
                return False

            connection.subscriptions.discard(topic)
            self._topic_subscriptions[topic].discard(connection_id)

        await self.send_to_connection(
            connection_id, WSEvent(type=WSEventType.UNSUBSCRIBED, data={"topic": topic})
        )

        return True

    async def send_to_connection(self, connection_id: str, event: WSEvent) -> bool:
        """Send event to a specific connection"""
        connection = self._connections.get(connection_id)
        if not connection:
            return False

        try:
            await connection.websocket.send_text(event.to_json())
            return True
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.warning("Failed to send to %s: %s", connection_id, e)
            await self.disconnect(connection_id)
            return False

    async def send_to_user(self, namespace: str, user_id: str, event: WSEvent):
        """Send event to all connections for a user"""
        user_key = f"{namespace}:{user_id}"
        connection_ids = list(self._user_connections.get(user_key, []))

        for conn_id in connection_ids:
            await self.send_to_connection(conn_id, event)

    async def broadcast_to_topic(self, topic: str, event: WSEvent):
        """Broadcast event to all subscribers of a topic"""
        connection_ids = list(self._topic_subscriptions.get(topic, []))

        for conn_id in connection_ids:
            await self.send_to_connection(conn_id, event)

    async def broadcast_activity(self, namespace: str, user_id: str, event: WSEvent):
        """Broadcast to user's activity topic"""
        topic = f"activity:{namespace}:{user_id}"
        await self.broadcast_to_topic(topic, event)

    def get_connection_count(self) -> int:
        """Get total number of active connections"""
        return len(self._connections)

    def get_user_connection_count(self, namespace: str, user_id: str) -> int:
        """Get number of connections for a user"""
        user_key = f"{namespace}:{user_id}"
        return len(self._user_connections.get(user_key, []))


# Singleton instance
ws_manager = WebSocketManager()


def get_ws_manager() -> WebSocketManager:
    """Get the WebSocket manager singleton"""
    return ws_manager
