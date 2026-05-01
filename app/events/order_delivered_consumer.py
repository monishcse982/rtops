from app.events.base_consumer import BaseConsumer, consumer_callback
from app.config import logger

if __name__ == "__main__":
    consumer = None
    try:
        consumer = BaseConsumer(queue_name="order_delivered_queue", routing_key="order.delivered")
        consumer.start_consuming(consumer_callback)
    except KeyboardInterrupt:
        if consumer is not None:
            consumer.close()
        logger.info("Consumer for OrderDelivered interrupted and closed.")
