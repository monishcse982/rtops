from app.events.base_consumer import BaseConsumer, consumer_callback
from app.config import logger

if __name__ == "__main__":
    consumer = None
    try:
        consumer = BaseConsumer(queue_name="order_shipped_queue", routing_key="order.shipped")
        consumer.start_consuming(consumer_callback)
    except KeyboardInterrupt:
        if consumer is not None:
            consumer.close()
        logger.info("Consumer for OrderShipped interrupted and closed.")
