import os
import json
import time
from decimal import Decimal

import pika

from app.config import logger
from app.exceptions import EventPublishingError
from app.request_context import ensure_request_id


def _get_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


class EventPublisher:
    def __init__(self, exchange_name="order_exchange"):
        self.exchange_name = exchange_name
        self.connection = None
        self.channel = None

    def _connect(self):
        """Establishes a connection to RabbitMQ if not already connected"""
        if self.connection is None or self.connection.is_closed:
            rabbitmq_host = os.getenv("RABBITMQ_HOST", "rabbitmq")
            rabbitmq_user = os.getenv("RABBITMQ_USER", "user")
            rabbitmq_pass = os.getenv("RABBITMQ_PASS", "password")
            last_error = None
            max_retries = max(_get_int_env("RABBITMQ_CONNECT_MAX_RETRIES", 5), 1)
            retry_delay_seconds = max(_get_int_env("RABBITMQ_CONNECT_RETRY_DELAY_SECONDS", 5), 0)

            credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_pass)

            # Retry loop in case RabbitMQ is not ready yet
            for i in range(max_retries):
                try:
                    self.connection = pika.BlockingConnection(
                        pika.ConnectionParameters(host=rabbitmq_host, credentials=credentials)
                    )
                    self.channel = self.connection.channel()
                    self.channel.exchange_declare(
                        exchange=self.exchange_name, exchange_type="direct", durable=True
                    )
                    logger.info("Connected to RabbitMQ")
                    break
                except pika.exceptions.AMQPConnectionError as exc:
                    last_error = exc
                    if i == max_retries - 1:
                        break
                    logger.warning(
                        "Attempt %s/%s: Could not connect to RabbitMQ, retrying in %s seconds...",
                        i + 1,
                        max_retries,
                        retry_delay_seconds,
                    )
                    if retry_delay_seconds > 0:
                        time.sleep(retry_delay_seconds)
            else:
                pass

            if self.connection is None or self.connection.is_closed:
                raise EventPublishingError(
                    self.exchange_name,
                    last_error,
                    phase="connect",
                    retryable=True,
                )

    def publish_event(self, event_type, data):
        """Publishes an event to RabbitMQ with error handling"""
        self._connect()  # Ensure connection is established before publishing
        payload = dict(data)
        payload.setdefault("request_id", ensure_request_id())
        try:
            self.channel.basic_publish(
                exchange=self.exchange_name,
                routing_key=event_type,
                body=json.dumps(payload, cls=EnhancedJSONEncoder),
                properties=pika.BasicProperties(
                    delivery_mode=2  # Ensures message persistence
                ),
            )
            logger.info(f"Event published: {event_type} - {payload}")
        except Exception as e:
            error_message = EventPublishingError(event_type, e, phase="publish", retryable=True)
            logger.error(f"❌ {error_message}")
            raise error_message

    def close(self):
        """Closes RabbitMQ connection"""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
