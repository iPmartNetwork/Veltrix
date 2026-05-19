"""Server-Sent Events (SSE) for Veltrix.

Provides real-time push updates to connected dashboard clients
without requiring WebSocket or external dependencies.
"""
from __future__ import annotations

import json
import queue
import threading
import time
from typing import Any


class SSEBroker:
    """Thread-safe broker that manages SSE client connections and broadcasts events."""

    def __init__(self, max_clients: int = 50, heartbeat_interval: int = 25) -> None:
        self._clients: list[queue.Queue[str]] = []
        self._lock = threading.Lock()
        self.max_clients = max_clients
        self.heartbeat_interval = heartbeat_interval
        self._running = True

        # Start heartbeat thread
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True,
            name="sse-heartbeat",
        )
        self._heartbeat_thread.start()

    def subscribe(self) -> queue.Queue[str]:
        """Register a new SSE client. Returns a queue to read events from."""
        client_queue: queue.Queue[str] = queue.Queue(maxsize=64)
        with self._lock:
            # Evict oldest client if at capacity
            while len(self._clients) >= self.max_clients:
                old = self._clients.pop(0)
                old.put("")  # Signal close
            self._clients.append(client_queue)
        return client_queue

    def unsubscribe(self, client_queue: queue.Queue[str]) -> None:
        """Remove a client from the broker."""
        with self._lock:
            try:
                self._clients.remove(client_queue)
            except ValueError:
                pass

    def publish(self, event: str, data: dict[str, Any] | str, event_id: str | None = None) -> None:
        """Broadcast an event to all connected clients."""
        if isinstance(data, dict):
            payload = json.dumps(data, ensure_ascii=False)
        else:
            payload = data

        message = ""
        if event_id:
            message += f"id: {event_id}\n"
        message += f"event: {event}\n"
        for line in payload.split("\n"):
            message += f"data: {line}\n"
        message += "\n"

        with self._lock:
            dead_clients = []
            for client_queue in self._clients:
                try:
                    client_queue.put_nowait(message)
                except queue.Full:
                    dead_clients.append(client_queue)
            for dead in dead_clients:
                try:
                    self._clients.remove(dead)
                except ValueError:
                    pass

    def client_count(self) -> int:
        """Get the number of connected clients."""
        with self._lock:
            return len(self._clients)

    def shutdown(self) -> None:
        """Shutdown the broker and disconnect all clients."""
        self._running = False
        with self._lock:
            for client_queue in self._clients:
                client_queue.put("")
            self._clients.clear()

    def _heartbeat_loop(self) -> None:
        """Send periodic heartbeat comments to keep connections alive."""
        while self._running:
            time.sleep(self.heartbeat_interval)
            if not self._running:
                break
            comment = ": heartbeat\n\n"
            with self._lock:
                dead_clients = []
                for client_queue in self._clients:
                    try:
                        client_queue.put_nowait(comment)
                    except queue.Full:
                        dead_clients.append(client_queue)
                for dead in dead_clients:
                    try:
                        self._clients.remove(dead)
                    except ValueError:
                        pass


# Global SSE broker instance
_broker: SSEBroker | None = None


def get_sse_broker() -> SSEBroker:
    """Get or create the global SSE broker."""
    global _broker
    if _broker is None:
        _broker = SSEBroker()
    return _broker


def publish_event(event: str, data: dict[str, Any] | str, event_id: str | None = None) -> None:
    """Publish an event to all connected SSE clients."""
    get_sse_broker().publish(event, data, event_id)


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------

def emit_server_status(server_id: int, status: str, details: dict[str, Any] | None = None) -> None:
    """Emit a server status change event."""
    publish_event("server.status", {
        "server_id": server_id,
        "status": status,
        **(details or {}),
    })


def emit_outbound_status(outbound_id: int, server_id: int, status: str, latency_ms: float | None = None) -> None:
    """Emit an outbound ping result event."""
    publish_event("outbound.ping", {
        "outbound_id": outbound_id,
        "server_id": server_id,
        "status": status,
        "latency_ms": latency_ms,
    })


def emit_alert(alert_type: str, server_id: int, message: str, severity: str = "warning") -> None:
    """Emit a new alert event."""
    publish_event("alert.new", {
        "type": alert_type,
        "server_id": server_id,
        "message": message,
        "severity": severity,
    })


def emit_incident(incident_id: int, action: str, details: dict[str, Any] | None = None) -> None:
    """Emit an incident lifecycle event."""
    publish_event("incident.update", {
        "incident_id": incident_id,
        "action": action,
        **(details or {}),
    })


def emit_monitor_cycle(servers_checked: int, duration_ms: float) -> None:
    """Emit a monitor cycle completion event."""
    publish_event("monitor.cycle", {
        "servers_checked": servers_checked,
        "duration_ms": round(duration_ms, 1),
    })
