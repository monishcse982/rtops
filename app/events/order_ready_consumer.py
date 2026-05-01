from app.events.base_consumer import BaseConsumer, consumer_callback
from app.config import logger

if __name__ == "__main__":
    consumer = None
    try:
        consumer = BaseConsumer(
            queue_name="order_ready_to_ship_queue", routing_key="order.ready.to.ship"
        )
        consumer.start_consuming(consumer_callback)
    except KeyboardInterrupt:
        if consumer is not None:
            consumer.close()
        logger.info("Consumer for OrderReadyToShip interrupted and closed.")
