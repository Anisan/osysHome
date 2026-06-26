"""Human-readable descriptions for paho-mqtt client error codes."""

from __future__ import annotations

# paho.mqtt.client on_disconnect rc values (Callback API v1).
PAHO_DISCONNECT_CODES: dict[int, str] = {
    -1: "Operation would block",
    0: "Disconnected gracefully",
    1: "Out of memory",
    2: "Protocol error",
    3: "Invalid function argument",
    4: "Client is not connected",
    5: "Connection refused by broker",
    6: "Message not found",
    7: "Connection lost unexpectedly",
    8: "TLS/SSL error",
    9: "Payload size is too large",
    10: "Feature is not supported",
    11: "Authentication failed",
    12: "Access denied by ACL",
    13: "Unknown error",
    14: "System errno error",
    15: "Message queue is full",
    16: "Keepalive timeout",
    17: "Oversize packet",
}

# MQTT CONNACK return codes for on_connect rc (0 = success).
MQTT_CONNACK_CODES: dict[int, str] = {
    0: "Connected successfully",
    1: "Connection refused - incorrect protocol version",
    2: "Connection refused - invalid client identifier",
    3: "Connection refused - server unavailable",
    4: "Connection refused - bad username or password",
    5: "Connection refused - not authorised",
}


def _normalize_code(rc) -> int | None:
    if rc is None:
        return None
    try:
        return int(rc)
    except (TypeError, ValueError):
        return None


def describe_mqtt_disconnect(rc) -> str:
    """Return a human-readable description for paho-mqtt on_disconnect rc."""
    code = _normalize_code(rc)
    if code is None:
        return f"Unexpected disconnection: {rc}"
    message = PAHO_DISCONNECT_CODES.get(code)
    if message:
        if code == 0:
            return message
        return f"{message} (code {code})"
    return f"Unexpected disconnection (code {code})"


def describe_mqtt_connect(rc) -> str:
    """Return a human-readable description for paho-mqtt on_connect CONNACK rc."""
    code = _normalize_code(rc)
    if code is None:
        return f"Connection failed: {rc}"
    message = MQTT_CONNACK_CODES.get(code)
    if message:
        if code == 0:
            return message
        return f"{message} (code {code})"
    return f"Connection failed (code {code})"
