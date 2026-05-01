from decimal import Decimal
from uuid import UUID

from app.events import outbox as outbox_module
from app.models.order_model import Order, OrderStatus
from app.models.outbox_event_model import OutboxEvent
from app.models.product_model import Product


def test_create_order_writes_outbox_event_with_request_id(client, db_session, monkeypatch):
    published_events = []

    def fake_publish_event(event_type, payload):
        published_events.append((event_type, payload))

    monkeypatch.setattr(outbox_module.event_publisher, "publish_event", fake_publish_event)

    product = Product(name="Dock", description="USB-C dock", price=Decimal("100.00"), stock=10)
    db_session.add(product)
    db_session.commit()

    response = client.post(
        "/api/orders/",
        headers={"X-Request-ID": "req-create-001"},
        json={"items": [{"item_id": product.id, "quantity": 2}]},
    )

    assert response.status_code == 201
    assert response.headers["X-Request-ID"] == "req-create-001"

    outbox_events = db_session.query(OutboxEvent).all()
    assert len(outbox_events) == 1
    assert outbox_events[0].event_type == "order.created"
    assert outbox_events[0].request_id == "req-create-001"
    assert outbox_events[0].payload["request_id"] == "req-create-001"
    assert outbox_events[0].payload["total_price"] == 240.0
    assert outbox_events[0].published_at is not None

    assert len(published_events) == 1
    assert published_events[0][0] == "order.created"
    assert published_events[0][1]["request_id"] == "req-create-001"


def test_create_order_generates_request_id_when_missing(client, db_session, monkeypatch):
    monkeypatch.setattr(
        outbox_module.event_publisher, "publish_event", lambda *args, **kwargs: None
    )

    product = Product(name="Mouse", description="Wireless mouse", price=Decimal("50.00"), stock=5)
    db_session.add(product)
    db_session.commit()

    response = client.post(
        "/api/orders/",
        json={"items": [{"item_id": product.id, "quantity": 1}]},
    )

    assert response.status_code == 201
    generated_request_id = response.headers["X-Request-ID"]
    UUID(generated_request_id)

    outbox_event = db_session.query(OutboxEvent).one()
    assert outbox_event.request_id == generated_request_id
    assert outbox_event.payload["request_id"] == generated_request_id


def test_pay_order_creates_paid_outbox_event(client, db_session, monkeypatch):
    published_events = []

    def fake_publish_event(event_type, payload):
        published_events.append((event_type, payload))

    monkeypatch.setattr(outbox_module.event_publisher, "publish_event", fake_publish_event)

    order = Order(status=OrderStatus.PENDING_PAYMENT)
    db_session.add(order)
    db_session.commit()

    response = client.post(
        f"/api/orders/{order.id}/pay",
        headers={"X-Request-ID": "req-pay-001"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-pay-001"

    db_session.expire_all()
    refreshed = db_session.get(Order, order.id)
    assert refreshed.status == OrderStatus.IN_PREPARATION

    outbox_events = db_session.query(OutboxEvent).order_by(OutboxEvent.id.asc()).all()
    assert len(outbox_events) == 1
    assert outbox_events[0].event_type == "order.paid"
    assert outbox_events[0].request_id == "req-pay-001"
    assert outbox_events[0].payload["event"] == "order.paid"
    assert outbox_events[0].published_at is not None

    assert len(published_events) == 1
    assert published_events[0][0] == "order.paid"
