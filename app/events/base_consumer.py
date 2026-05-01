import json
import os
import time

import pika

from app.config import logger
from app.events.dispatcher import dispatch_event
from app.exceptions import EventConsumptionError, MalformedEventError
from app.request_context import generate_request_id, reset_request_id, set_request_id


class BaseConsumer:
    def __init__(self, queue_name, routing_key, exchange_name="order_exchange"):
        self.queue_name = queue_name
        self.routing_key = routing_key
        self.exchange_name = exchange_name

        # RabbitMQ configuration from environment variables
        rabbitmq_host = os.environ.get("RABBITMQ_HOST", "rabbitmq")
        rabbitmq_user = os.environ.get("RABBITMQ_USER", "user")
        rabbitmq_pass = os.environ.get("RABBITMQ_PASS", "password")
        credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_pass)
        last_error = None

        # Attempt to connect to RabbitMQ with retries
        for i in range(5):
            try:
                self.connection = pika.BlockingConnection(
                    pika.ConnectionParameters(host=rabbitmq_host, credentials=credentials)
                )
                break
            except pika.exceptions.AMQPConnectionError as exc:
                last_error = exc
                logger.warning(
                    f"Attempt {i + 1}/5: Unable to connect to RabbitMQ, retrying in 5 seconds..."
                )
                time.sleep(5)
        else:
            raise EventConsumptionError(
                "Could not connect to RabbitMQ after 5 attempts",
                error=last_error,
                retryable=True,
            )

        self.channel = self.connection.channel()
        # Declare exchange and queue as durable
        self.channel.exchange_declare(
            exchange=self.exchange_name, exchange_type="direct", durable=True
        )
        self.channel.queue_declare(queue=self.queue_name, durable=True)
        self.channel.queue_bind(
            exchange=self.exchange_name,
            queue=self.queue_name,
            routing_key=self.routing_key,
        )

    def start_consuming(self, callback):
        """Starts consuming messages using the provided callback."""
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(
            queue=self.queue_name, on_message_callback=callback, auto_ack=False
        )
        logger.info(f"Consumer listening on queue: {self.queue_name}")
        self.channel.start_consuming()

    def close(self):
        """Closes the connection to RabbitMQ."""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            logger.info("Connection to RabbitMQ closed.")


def consumer_callback(ch, method, properties, body):
    token = None
    try:
        event = json.loads(body)
        if not isinstance(event, dict):
            raise MalformedEventError(event_data=body.decode("utf-8", errors="replace"))

        request_id = event.get("request_id") or generate_request_id()
        token = set_request_id(request_id)
        logger.info(f"Event received: {event}")
        dispatch_event(event)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except json.JSONDecodeError as exc:
        token = set_request_id(generate_request_id())
        logger.error(
            f"Rejecting malformed JSON message: {body.decode('utf-8', errors='replace')}. error={exc}"
        )
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except MalformedEventError as exc:
        if token is None:
            token = set_request_id(generate_request_id())
        logger.error(str(exc))
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except EventConsumptionError as exc:
        if token is None:
            token = set_request_id(generate_request_id())
        logger.exception(str(exc))
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=exc.retryable)
    except Exception as exc:
        if token is None:
            token = set_request_id(generate_request_id())
        logger.exception(f"Unexpected error processing message: {exc}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    finally:
        if token is not None:
            reset_request_id(token)
