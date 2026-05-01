import os
import json
import time
from decimal import Decimal

import pika

from app.config import logger
from app.exceptions import EventPublishingError
from app.request_context import ensure_request_id


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

            credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_pass)

            # Retry loop in case RabbitMQ is not ready yet
            for i in range(5):
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
                    logger.warning(
                        f"Attempt {i + 1}/5: Could not connect to RabbitMQ, retrying in 5 seconds..."
                    )
                    time.sleep(5)
            else:
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
