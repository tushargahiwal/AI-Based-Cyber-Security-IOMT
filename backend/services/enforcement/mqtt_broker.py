"""Cuts a rogue publisher off at the MQTT broker.

The most surgical response available for the data-alteration case. If something
is publishing forged vitals onto a device's topic, revoking that client at the
broker stops the forged readings without a single medical device losing its
network connection.

Brokers differ in how they expose this. Mosquitto with the dynamic-security
plugin takes control messages on `$CONTROL/dynamic-security/v1`; EMQX and HiveMQ
have REST APIs. The control topic is configurable for that reason, and the
default matches Mosquitto because it is what a hospital pilot is most likely to
be running.

This does not disconnect the client's TCP session on its own — the broker does
that when the client's permissions are revoked and it next tries to publish. The
practical effect is the same: the forged readings stop.
"""

import json

from .base import Actuator

DEFAULT_CONTROL_TOPIC = "$CONTROL/dynamic-security/v1"
DEFAULT_PORT = 1883
CONNECT_TIMEOUT_SECONDS = 10


class MqttRevokeActuator(Actuator):
    """Revokes a client's ability to publish."""

    name = "mqtt_revoke"
    requires = ("host",)

    def describe(self, *, target: str, **kwargs) -> str:
        host = self.config.get("host", "?")
        return (f"tell the broker at {host} to disable MQTT client {target!r} "
                f"(control topic {self.config.get('control_topic', DEFAULT_CONTROL_TOPIC)})")

    def _act(self, *, target: str, reason: str, **kwargs) -> str:
        import paho.mqtt.client as mqtt

        host = self.config["host"]
        port = int(self.config.get("port", DEFAULT_PORT))
        control_topic = self.config.get("control_topic", DEFAULT_CONTROL_TOPIC)

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        username = self.config.get("username")
        if username:
            client.username_pw_set(username, self.config.get("password", ""))

        client.connect(host, port, keepalive=CONNECT_TIMEOUT_SECONDS)
        client.loop_start()
        try:
            command = {"commands": [{"command": "disableClient", "username": target}]}
            info = client.publish(control_topic, json.dumps(command), qos=1)
            # Without waiting, loop_stop() can tear the connection down before the
            # PUBLISH leaves — reporting a success that never reached the broker.
            info.wait_for_publish(timeout=CONNECT_TIMEOUT_SECONDS)
            if not info.is_published():
                raise RuntimeError("the broker did not acknowledge the revoke within the timeout")
        finally:
            client.loop_stop()
            client.disconnect()

        return (f"sent disableClient for {target!r} to {host}:{port} on {control_topic}; "
                f"the broker drops it on its next publish")
