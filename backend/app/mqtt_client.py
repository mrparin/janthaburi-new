from __future__ import annotations

import logging
from threading import Event, Thread

import paho.mqtt.client as mqtt

from app.config import Settings
from app.service import DataService

logger = logging.getLogger(__name__)


class MqttIngestClient:
    def __init__(self, settings: Settings, service: DataService) -> None:
        self.settings = settings
        self.service = service
        self.client = mqtt.Client(protocol=mqtt.MQTTv311)
        self.client.reconnect_delay_set(min_delay=2, max_delay=30)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        self._started = False
        self._stop_event = Event()
        self._watchdog_thread: Thread | None = None

    def _on_connect(self, client: mqtt.Client, userdata, flags, reason_code):
        if reason_code == 0:
            logger.info("Connected to MQTT broker %s:%s", self.settings.mqtt_host, self.settings.mqtt_port)
            client.subscribe(self.settings.mqtt_topic, qos=self.settings.mqtt_qos)
            logger.info("Subscribed topic: %s", self.settings.mqtt_topic)
        else:
            logger.error("MQTT connection failed, code=%s", reason_code)

    def _on_disconnect(self, client: mqtt.Client, userdata, reason_code):
        logger.warning("MQTT disconnected, code=%s", reason_code)

    def _attempt_connect(self) -> None:
        try:
            self.client.connect_async(self.settings.mqtt_host, self.settings.mqtt_port, keepalive=60)
        except OSError as exc:
            logger.warning("MQTT connect_async failed: %s", exc)

    def _connection_watchdog(self) -> None:
        # Keep trying to reconnect when startup happens without network.
        while not self._stop_event.wait(timeout=5):
            if not self._started or self.client.is_connected():
                continue

            try:
                self.client.reconnect()
                logger.info("MQTT watchdog reconnect attempt sent")
            except Exception as exc:  # pragma: no cover
                logger.debug("MQTT reconnect failed, fallback to connect_async: %s", exc)
                self._attempt_connect()

    def _on_message(self, client: mqtt.Client, userdata, msg: mqtt.MQTTMessage):
        self.service.process_mqtt_payload(msg.payload)

    def start(self) -> None:
        if self._started:
            return

        try:
            self.client.loop_start()
            self._attempt_connect()
            self._stop_event.clear()
            self._watchdog_thread = Thread(target=self._connection_watchdog, name="mqtt-watchdog", daemon=True)
            self._watchdog_thread.start()
            self._started = True
            logger.info(
                "Starting MQTT client for %s:%s topic=%s",
                self.settings.mqtt_host,
                self.settings.mqtt_port,
                self.settings.mqtt_topic,
            )
        except OSError as exc:
            logger.warning("MQTT client start failed: %s", exc)

    def stop(self) -> None:
        if not self._started:
            return

        self._stop_event.set()
        if self._watchdog_thread and self._watchdog_thread.is_alive():
            self._watchdog_thread.join(timeout=2)
        self._watchdog_thread = None
        self.client.loop_stop()
        self.client.disconnect()
        self._started = False
