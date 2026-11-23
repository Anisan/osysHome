import unittest

from app.core.utilities.mqtt_errors import (
    describe_mqtt_connect,
    describe_mqtt_disconnect,
)


class MqttErrorsTest(unittest.TestCase):
    def test_describe_mqtt_disconnect_known_codes(self):
        self.assertEqual(
            describe_mqtt_disconnect(7),
            "Connection lost unexpectedly (code 7)",
        )
        self.assertEqual(
            describe_mqtt_disconnect(16),
            "Keepalive timeout (code 16)",
        )
        self.assertEqual(
            describe_mqtt_disconnect(5),
            "Connection refused by broker (code 5)",
        )

    def test_describe_mqtt_disconnect_graceful(self):
        self.assertEqual(
            describe_mqtt_disconnect(0),
            "Disconnected gracefully",
        )

    def test_describe_mqtt_disconnect_unknown(self):
        self.assertEqual(
            describe_mqtt_disconnect(99),
            "Unexpected disconnection (code 99)",
        )

    def test_describe_mqtt_connect(self):
        self.assertEqual(
            describe_mqtt_connect(4),
            "Connection refused - bad username or password (code 4)",
        )


if __name__ == "__main__":
    unittest.main()
