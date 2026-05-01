from app.models.database import SessionLocal
from app.models.order_model import Order, OrderStatus
from app.config import logger
from app.exceptions import EventConsumptionError

ORDER_STATUS_RANK = {
    OrderStatus.CREATED: 0,
    OrderStatus.PENDING_PAYMENT: 1,
    OrderStatus.IN_PREPARATION: 2,
    OrderStatus.READY_TO_SHIP: 3,
    OrderStatus.SHIPPED: 4,
    OrderStatus.DELIVERED: 5,
}


def _get_order_id(event: dict) -> int:
    order_id = event.get("order_id")
    if order_id is None:
        raise EventConsumptionError(
            "Event is missing order_id",
            event_data=event,
            retryable=False,
        )
    return order_id


def _update_order_status(
    event: dict,
    next_status: OrderStatus,
    *,
    success_log: str,
    notification_log: str,
    notification_kwargs: dict | None = None,
):
    order_id = _get_order_id(event)
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            logger.warning(f"Order {order_id} not found while processing event {event}")
            return

        current_status = order.status
        if current_status == next_status:
            logger.info(
                f"Order {order_id} already in state {next_status.value}; skipping duplicate event"
            )
            return
        if ORDER_STATUS_RANK[current_status] > ORDER_STATUS_RANK[next_status]:
            logger.info(
                f"Order {order_id} already advanced past {next_status.value}; ignoring stale event"
            )
            return

        order.status = next_status
        db.commit()
        logger.info(success_log.format(order_id=order_id))
        logger.info(notification_log.format(order_id=order_id, **(notification_kwargs or {})))
    except Exception as exc:
        db.rollback()
        raise EventConsumptionError(
            "Failed to process order event",
            event_data=event,
            error=exc,
            retryable=True,
        ) from exc
    finally:
        db.close()


def handle_order_created(event: dict):
    """When an order is created: update it to 'pending_payment' and notify the user."""
    total_price = event.get("total_price")
    _update_order_status(
        event,
        OrderStatus.PENDING_PAYMENT,
        success_log="Order {order_id} updated to pending_payment",
        notification_log="User notification: Please pay for order {order_id} with total amount ${total_price}",
        notification_kwargs={"total_price": total_price},
    )


def handle_order_payed(event: dict):
    """Simulate payment: update to 'in_preparation' and notify the supplier to prepare the package."""
    _update_order_status(
        event,
        OrderStatus.IN_PREPARATION,
        success_log="Order {order_id} updated to in_preparation",
        notification_log="Message to supplier: Prepare the package for order {order_id}",
    )


def handle_order_ready_to_ship(event: dict):
    """Triggered from an endpoint (not implemented here), this event notifies the carrier and updates to 'ready_to_ship'."""
    _update_order_status(
        event,
        OrderStatus.READY_TO_SHIP,
        success_log="Order {order_id} updated to ready_to_ship",
        notification_log="Message to carrier: Pick up the package for order {order_id}",
    )


def handle_shipped(event: dict):
    """When the carrier notifies that the package has been picked up, publish 'Shipped' to notify the user."""
    _update_order_status(
        event,
        OrderStatus.SHIPPED,
        success_log="Order {order_id} updated to shipped",
        notification_log="User notification: Your order {order_id} is on its way.",
    )


def handle_delivered(event: dict):
    """When the carrier marks the order as delivered, update the status to 'delivered' and notify the user."""
    _update_order_status(
        event,
        OrderStatus.DELIVERED,
        success_log="Order {order_id} updated to delivered",
        notification_log="User notification: Your order {order_id} has been delivered.",
    )
