from app.events.handlers import handle_order_created, handle_order_payed
from app.exceptions import EventConsumptionError
from app.models.line_item_model import LineItem
from app.models.order_model import Order, OrderStatus
from app.models.product_model import Product


def test_handle_order_created_moves_order_to_pending_payment(db_session):
    product = Product(name="Keyboard", description="Test", price="25.00", stock=5)
    order = Order(status=OrderStatus.CREATED)
    db_session.add_all([product, order])
    db_session.flush()
    db_session.add(LineItem(order_id=order.id, product_id=product.id, quantity=2))
    db_session.commit()

    handle_order_created({"event": "order.created", "order_id": order.id, "total_price": 50.0})

    db_session.expire_all()
    refreshed = db_session.get(Order, order.id)
    assert refreshed.status == OrderStatus.PENDING_PAYMENT


def test_handle_order_payed_is_idempotent_for_duplicate_event(db_session):
    order = Order(status=OrderStatus.PENDING_PAYMENT)
    db_session.add(order)
    db_session.commit()

    handle_order_payed({"event": "order.paid", "order_id": order.id})
    handle_order_payed({"event": "order.paid", "order_id": order.id})

    db_session.expire_all()
    refreshed = db_session.get(Order, order.id)
    assert refreshed.status == OrderStatus.IN_PREPARATION


def test_handle_order_created_ignores_stale_event_when_order_already_advanced(db_session):
    order = Order(status=OrderStatus.SHIPPED)
    db_session.add(order)
    db_session.commit()

    handle_order_created({"event": "order.created", "order_id": order.id, "total_price": 10.0})

    db_session.expire_all()
    refreshed = db_session.get(Order, order.id)
    assert refreshed.status == OrderStatus.SHIPPED


def test_handler_requires_order_id():
    try:
        handle_order_created({"event": "order.created"})
    except EventConsumptionError as exc:
        assert exc.retryable is False
    else:
        raise AssertionError("Expected EventConsumptionError")


def test_handler_ignores_missing_order_without_raising(db_session):
    handle_order_created({"event": "order.created", "order_id": 99999, "total_price": 10.0})

    assert db_session.query(Order).count() == 0
