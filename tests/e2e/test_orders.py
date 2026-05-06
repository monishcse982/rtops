from decimal import Decimal

import pytest
from sqlalchemy import func

from app.models.line_item_model import LineItem
from app.models.line_item_schemas import OrderItemRequest
from app.models.order_model import Order, OrderStatus
from app.models.order_schemas import OrderCreateRequest
from app.models.outbox_event_model import OutboxEvent
from app.models.product_model import Product
from constants import MONEY_PRECISION, TAX_RATE
from reporting import (
    api_request,
    assert_equal,
    assert_header,
    assert_status,
    assert_truthy,
    db_query_all,
    db_query_count,
    db_query_first,
    db_query_one,
)

ORDERS_PATH = "/api/orders/"


def _orders_url(test_config, suffix: str = "") -> str:
    return f"{test_config.api_url.rstrip('/')}{ORDERS_PATH}{suffix}"


def _get_created_order(db_session, order_id: int) -> Order:
    db_session.expire_all()
    return db_query_one(
        db_session.query(Order).filter(Order.id == order_id),
        f"fetch order row for order_id={order_id}",
    )


def _get_line_items(db_session, order_id: int) -> list[LineItem]:
    db_session.expire_all()
    return db_query_all(
        db_session.query(LineItem).filter(LineItem.order_id == order_id),
        f"fetch line items for order_id={order_id}",
    )


def _get_outbox_event(db_session, event_type: str, order_id: int) -> OutboxEvent:
    db_session.expire_all()
    return db_query_one(
        db_session.query(OutboxEvent)
        .filter(OutboxEvent.event_type == event_type)
        .filter(OutboxEvent.payload["order_id"].as_integer() == order_id),
        f"fetch outbox event {event_type} for order_id={order_id}",
    )


def _get_outbox_events_for_order(db_session, order_id: int) -> list[OutboxEvent]:
    db_session.expire_all()
    return db_query_all(
        db_session.query(OutboxEvent)
        .filter(OutboxEvent.payload["order_id"].as_integer() == order_id)
        .order_by(OutboxEvent.id.asc()),
        f"fetch outbox events for order_id={order_id}",
    )


def _create_order_via_api(test_config, items: list[dict], request_id: str | None = None):
    headers = {"X-Request-ID": request_id} if request_id else None
    return api_request(
        "post",
        _orders_url(test_config),
        json={"items": items},
        headers=headers,
    )


def test_order_creation(test_config, db_session):
    product = db_query_first(db_session.query(Product), "fetch seed product for order creation")
    assert product is not None

    order_request = OrderCreateRequest(items=[OrderItemRequest(product_id=product.id, quantity=1)])

    response = api_request(
        "post",
        _orders_url(test_config),
        json=order_request.model_dump(),
    )

    assert_status(response, 201)

    response_body = response.json()
    order_id = response_body["order_id"]

    assert_truthy(order_id, "created order id is returned")
    assert_equal(response_body["status"], "created", "created order status is returned")

    created_order = _get_created_order(db_session, order_id)
    assert_equal(created_order.id, order_id, "persisted order id matches API response")
    assert_equal(
        created_order.status.value
        if hasattr(created_order.status, "value")
        else created_order.status,
        "created",
        "persisted order status is created",
    )

    line_items = _get_line_items(db_session, order_id)
    assert_equal(len(line_items), 1, "one line item is persisted")
    assert_equal(line_items[0].product_id, product.id, "line item product id matches request")
    assert_equal(line_items[0].quantity, 1, "line item quantity matches request")

    outbound_event = _get_outbox_event(db_session, "order.created", order_id)
    assert_equal(outbound_event.event_type, "order.created", "outbox event type is order.created")
    assert_equal(outbound_event.payload["order_id"], order_id, "outbox payload order id matches")


def test_create_order_with_multiple_valid_products(test_config, db_session):
    product1 = db_query_first(db_session.query(Product), "fetch first seed product")
    product2 = db_query_first(db_session.query(Product).offset(1), "fetch second seed product")
    assert product1 is not None and product2 is not None

    order_request = OrderCreateRequest(
        items=[
            OrderItemRequest(product_id=product1.id, quantity=1),
            OrderItemRequest(product_id=product2.id, quantity=2),
        ]
    )

    response = api_request(
        "post",
        _orders_url(test_config),
        json=order_request.model_dump(),
    )

    assert_status(response, 201)

    response_body = response.json()
    order_id = response_body["order_id"]

    assert_truthy(order_id, "created order id is returned")
    assert_equal(response_body["status"], "created", "created order status is returned")

    created_order = _get_created_order(db_session, order_id)
    assert_equal(created_order.id, order_id, "persisted order id matches API response")
    assert_equal(
        created_order.status.value
        if hasattr(created_order.status, "value")
        else created_order.status,
        "created",
        "persisted order status is created",
    )

    line_items = _get_line_items(db_session, order_id)
    assert_equal(len(line_items), 2, "two line items are persisted")

    line_items_by_product_id = {item.product_id: item for item in line_items}

    assert_truthy(product1.id in line_items_by_product_id, "first product is present in line items")
    assert_truthy(
        product2.id in line_items_by_product_id, "second product is present in line items"
    )
    assert_equal(
        line_items_by_product_id[product1.id].quantity, 1, "first product quantity matches"
    )
    assert_equal(
        line_items_by_product_id[product2.id].quantity, 2, "second product quantity matches"
    )

    outbox_event = _get_outbox_event(db_session, "order.created", order_id)
    assert_equal(outbox_event.event_type, "order.created", "outbox event type is order.created")
    assert_equal(outbox_event.payload["order_id"], order_id, "outbox payload order id matches")


def test_create_order_calculates_total_price(test_config, db_session):
    quantity = 2
    product = db_query_first(
        db_session.query(Product).order_by(func.random()),
        "fetch random seed product for pricing check",
    )
    assert product is not None

    expected_total_price = (product.price * quantity) * (Decimal("1.0") + TAX_RATE)

    order_request = OrderCreateRequest(
        items=[OrderItemRequest(product_id=product.id, quantity=quantity)]
    )
    response = api_request(
        "post",
        _orders_url(test_config),
        json=order_request.model_dump(),
    )
    assert_status(response, 201)
    response_body = response.json()
    assert_equal(
        Decimal(response_body["total_price"]),
        expected_total_price.quantize(MONEY_PRECISION),
        "create order total price matches taxed pricing",
    )


def test_create_order_rejects_nonexistent_product(test_config, db_session):
    order_count_before = db_query_count(
        db_session.query(Order), "count orders before failed create"
    )
    line_item_count_before = db_query_count(
        db_session.query(LineItem), "count line items before failed create"
    )

    response = api_request(
        "post",
        _orders_url(test_config),
        json={"items": [{"product_id": 999999, "quantity": 1}]},
    )

    assert_status(response, 404)
    assert_equal(
        response.json()["detail"], "Items not found: 999999", "missing product error message"
    )

    db_session.expire_all()
    assert_equal(
        db_query_count(db_session.query(Order), "count orders after failed create"),
        order_count_before,
        "failed create does not change order count",
    )
    assert_equal(
        db_query_count(db_session.query(LineItem), "count line items after failed create"),
        line_item_count_before,
        "failed create does not change line item count",
    )
    assert_equal(
        db_query_count(db_session.query(OutboxEvent), "count outbox events after failed create"),
        0,
        "failed create does not write outbox events",
    )


def test_create_order_rejects_empty_items(test_config, db_session):
    response = api_request(
        "post",
        _orders_url(test_config),
        json={"items": []},
    )

    assert_status(response, 422)
    assert_equal(
        db_query_count(db_session.query(OutboxEvent), "count outbox events"),
        0,
        "no outbox row is written",
    )


def test_create_order_rejects_duplicate_product_ids(test_config, db_session):
    product = db_query_first(
        db_session.query(Product), "fetch seed product for duplicate item check"
    )
    assert product is not None

    response = api_request(
        "post",
        _orders_url(test_config),
        json={
            "items": [
                {"product_id": product.id, "quantity": 1},
                {"product_id": product.id, "quantity": 2},
            ]
        },
    )

    assert_status(response, 422)
    assert_equal(
        db_query_count(db_session.query(OutboxEvent), "count outbox events"),
        0,
        "no outbox row is written",
    )


def test_create_order_rejects_invalid_quantity(test_config, db_session):
    product = db_query_first(
        db_session.query(Product), "fetch seed product for invalid quantity check"
    )
    assert product is not None

    response = api_request(
        "post",
        _orders_url(test_config),
        json={"items": [{"product_id": product.id, "quantity": 0}]},
    )

    assert_status(response, 422)
    assert_equal(
        db_query_count(db_session.query(OutboxEvent), "count outbox events"),
        0,
        "no outbox row is written",
    )


def test_create_order_rejects_negative_quantity(test_config, db_session):
    product = db_query_first(
        db_session.query(Product), "fetch seed product for negative quantity check"
    )
    assert product is not None

    response = api_request(
        "post",
        _orders_url(test_config),
        json={"items": [{"product_id": product.id, "quantity": -1}]},
    )

    assert_status(response, 422)
    assert_equal(
        db_query_count(db_session.query(OutboxEvent), "count outbox events"),
        0,
        "no outbox row is written",
    )


def test_get_order_details_returns_created_order(test_config, db_session):
    product = db_query_first(
        db_session.query(Product), "fetch seed product for order details check"
    )
    assert product is not None

    create_response = api_request(
        "post",
        _orders_url(test_config),
        json={"items": [{"product_id": product.id, "quantity": 2}]},
    )
    assert_status(create_response, 201)
    order_id = create_response.json()["order_id"]

    response = api_request("get", _orders_url(test_config, str(order_id)))

    assert_status(response, 200)
    response_body = response.json()
    assert_equal(response_body["order_id"], order_id, "order details response order id matches")
    assert_equal(response_body["status"], "created", "order details status is created")
    assert_equal(len(response_body["items"]), 1, "order details has one item")
    assert_equal(
        response_body["items"][0]["product_id"], product.id, "order details product id matches"
    )
    assert_equal(response_body["items"][0]["quantity"], 2, "order details quantity matches")


def test_order_details_endpoint_echoes_request_tracing_headers(test_config, db_session):
    product = db_query_first(db_session.query(Product), "fetch seed product for order header check")
    assert product is not None

    create_response = api_request(
        "post",
        _orders_url(test_config),
        json={"items": [{"product_id": product.id, "quantity": 1}]},
    )
    assert_status(create_response, 201)
    order_id = create_response.json()["order_id"]

    response = api_request(
        "get",
        _orders_url(test_config, str(order_id)),
        headers={"X-Request-ID": "req-order-details-001"},
    )

    assert_status(response, 200)
    assert_header(response, "X-Request-ID", "req-order-details-001")
    assert_header(response, "X-Trace-ID", "req-order-details-001")


def test_get_nonexistent_order_returns_404(test_config):
    response = api_request("get", _orders_url(test_config, "999999"))

    assert_status(response, 404)
    assert_equal(response.json()["detail"], "Order not found", "missing order error message")


def test_get_order_with_invalid_path_parameter_returns_422(test_config):
    response = api_request("get", _orders_url(test_config, "0"))

    assert_status(response, 422)


def test_pay_order_successfully(test_config, db_session):
    order = Order(status=OrderStatus.PENDING_PAYMENT)
    db_session.add(order)
    db_session.commit()

    response = api_request("post", _orders_url(test_config, f"{order.id}/pay"))

    assert_status(response, 200)
    assert_equal(
        response.json()["status"], "in_preparation", "pay order response status is in_preparation"
    )

    created_order = _get_created_order(db_session, order.id)
    assert_equal(
        created_order.status, OrderStatus.IN_PREPARATION, "persisted order status is in_preparation"
    )

    outbox_event = _get_outbox_event(db_session, "order.paid", order.id)
    assert_equal(outbox_event.payload["event"], "order.paid", "outbox payload event is order.paid")


def test_pay_order_with_invalid_path_parameter_returns_422(test_config):
    response = api_request("post", _orders_url(test_config, "0/pay"))

    assert_status(response, 422)


def test_mark_order_ready_to_ship(test_config, db_session):
    order = Order(status=OrderStatus.IN_PREPARATION)
    db_session.add(order)
    db_session.commit()

    response = api_request("post", _orders_url(test_config, f"{order.id}/ready-to-ship"))

    assert_status(response, 200)
    assert_equal(
        response.json()["status"], "ready_to_ship", "ready-to-ship response status is ready_to_ship"
    )

    created_order = _get_created_order(db_session, order.id)
    assert_equal(
        created_order.status, OrderStatus.READY_TO_SHIP, "persisted order status is ready_to_ship"
    )

    outbox_event = _get_outbox_event(db_session, "order.ready.to.ship", order.id)
    assert_equal(
        outbox_event.payload["event"],
        "order.ready.to.ship",
        "outbox payload event is order.ready.to.ship",
    )


def test_ready_to_ship_with_invalid_path_parameter_returns_422(test_config):
    response = api_request("post", _orders_url(test_config, "0/ready-to-ship"))

    assert_status(response, 422)


def test_mark_order_as_shipped(test_config, db_session):
    order = Order(status=OrderStatus.READY_TO_SHIP)
    db_session.add(order)
    db_session.commit()

    response = api_request("post", _orders_url(test_config, f"{order.id}/shipped"))

    assert_status(response, 200)
    assert_equal(response.json()["status"], "shipped", "ship response status is shipped")

    created_order = _get_created_order(db_session, order.id)
    assert_equal(created_order.status, OrderStatus.SHIPPED, "persisted order status is shipped")

    outbox_event = _get_outbox_event(db_session, "order.shipped", order.id)
    assert_equal(
        outbox_event.payload["event"], "order.shipped", "outbox payload event is order.shipped"
    )


def test_ship_order_with_invalid_path_parameter_returns_422(test_config):
    response = api_request("post", _orders_url(test_config, "0/shipped"))

    assert_status(response, 422)


def test_mark_order_as_delivered(test_config, db_session):
    order = Order(status=OrderStatus.SHIPPED)
    db_session.add(order)
    db_session.commit()

    response = api_request("post", _orders_url(test_config, f"{order.id}/delivered"))

    assert_status(response, 200)
    assert_equal(response.json()["status"], "delivered", "deliver response status is delivered")

    created_order = _get_created_order(db_session, order.id)
    assert_equal(created_order.status, OrderStatus.DELIVERED, "persisted order status is delivered")

    outbox_event = _get_outbox_event(db_session, "order.delivered", order.id)
    assert_equal(
        outbox_event.payload["event"], "order.delivered", "outbox payload event is order.delivered"
    )


def test_deliver_order_with_invalid_path_parameter_returns_422(test_config):
    response = api_request("post", _orders_url(test_config, "0/delivered"))

    assert_status(response, 422)


@pytest.mark.parametrize(
    ("initial_status", "action_path"),
    [
        (OrderStatus.CREATED, "shipped"),
        (OrderStatus.READY_TO_SHIP, "delivered"),
        (OrderStatus.CREATED, "ready-to-ship"),
    ],
)
def test_reject_invalid_order_status_transitions(
    test_config, db_session, initial_status, action_path
):
    order = Order(status=initial_status)
    db_session.add(order)
    db_session.commit()

    response = api_request("post", _orders_url(test_config, f"{order.id}/{action_path}"))

    assert_status(response, 400)

    refreshed_order = _get_created_order(db_session, order.id)
    assert_equal(
        refreshed_order.status, initial_status, "invalid transition leaves order status unchanged"
    )
    assert_equal(
        db_query_count(
            db_session.query(OutboxEvent), "count outbox events after invalid transition"
        ),
        0,
        "invalid transition does not write outbox rows",
    )


def test_invalid_order_transition_does_not_append_new_outbox_event(test_config, db_session):
    product = db_session.query(Product).first()
    assert product is not None

    create_response = api_request(
        "post",
        _orders_url(test_config),
        json={"items": [{"product_id": product.id, "quantity": 1}]},
    )
    assert_status(create_response, 201)
    order_id = create_response.json()["order_id"]

    outbox_count_before = len(_get_outbox_events_for_order(db_session, order_id))

    response = api_request("post", _orders_url(test_config, f"{order_id}/shipped"))

    assert_status(response, 400)
    assert_equal(
        len(_get_outbox_events_for_order(db_session, order_id)),
        outbox_count_before,
        "invalid transition does not append outbox events",
    )


def test_request_id_propagation_on_order_creation(test_config, db_session):
    product = db_query_first(
        db_session.query(Product), "fetch seed product for request id propagation"
    )
    assert product is not None

    response = _create_order_via_api(
        test_config,
        [{"product_id": product.id, "quantity": 1}],
        request_id="req-e2e-create-001",
    )

    assert_status(response, 201)
    assert_header(response, "X-Request-ID", "req-e2e-create-001")
    assert_header(response, "X-Trace-ID", "req-e2e-create-001")

    order_id = response.json()["order_id"]
    outbox_event = _get_outbox_event(db_session, "order.created", order_id)
    assert_equal(
        outbox_event.request_id, "req-e2e-create-001", "outbox request id matches custom request id"
    )
    assert_equal(
        outbox_event.payload["request_id"],
        "req-e2e-create-001",
        "outbox payload request id matches custom request id",
    )


def test_auto_generated_request_id_on_order_creation(test_config, db_session):
    product = db_query_first(
        db_session.query(Product), "fetch seed product for generated request id"
    )
    assert product is not None

    response = _create_order_via_api(
        test_config,
        [{"product_id": product.id, "quantity": 1}],
    )

    assert_status(response, 201)
    generated_request_id = response.headers["X-Request-ID"]
    assert_truthy(generated_request_id, "generated request id is returned")
    assert_header(response, "X-Trace-ID", generated_request_id)

    order_id = response.json()["order_id"]
    outbox_event = _get_outbox_event(db_session, "order.created", order_id)
    assert_equal(
        outbox_event.request_id,
        generated_request_id,
        "outbox request id matches generated request id",
    )
    assert_equal(
        outbox_event.payload["request_id"],
        generated_request_id,
        "outbox payload request id matches generated request id",
    )


def test_failed_order_creation_leaves_no_partial_data(test_config, db_session):
    order_count_before = db_query_count(
        db_session.query(Order), "count orders before partial-data check"
    )
    line_item_count_before = db_query_count(
        db_session.query(LineItem), "count line items before partial-data check"
    )
    outbox_count_before = db_query_count(
        db_session.query(OutboxEvent), "count outbox events before partial-data check"
    )

    response = api_request(
        "post",
        _orders_url(test_config),
        json={"items": [{"product_id": 999999, "quantity": 1}]},
    )

    assert_status(response, 404)

    db_session.expire_all()
    assert_equal(
        db_query_count(db_session.query(Order), "count orders after partial-data check"),
        order_count_before,
        "failed create leaves order count unchanged",
    )
    assert_equal(
        db_query_count(db_session.query(LineItem), "count line items after partial-data check"),
        line_item_count_before,
        "failed create leaves line item count unchanged",
    )
    assert_equal(
        db_query_count(
            db_session.query(OutboxEvent), "count outbox events after partial-data check"
        ),
        outbox_count_before,
        "failed create leaves outbox count unchanged",
    )


def test_create_order_response_uses_taxed_pricing_while_order_details_uses_standard_pricing(
    test_config, db_session
):
    quantity = 2
    product = db_query_first(
        db_session.query(Product).order_by(func.random()),
        "fetch random seed product for pricing contract check",
    )
    assert product is not None

    create_response = api_request(
        "post",
        _orders_url(test_config),
        json={"items": [{"product_id": product.id, "quantity": quantity}]},
    )

    assert_status(create_response, 201)
    order_id = create_response.json()["order_id"]
    create_total = Decimal(create_response.json()["total_price"])
    expected_taxed_total = (product.price * quantity) * (Decimal("1.0") + TAX_RATE)
    assert_equal(
        create_total,
        expected_taxed_total.quantize(MONEY_PRECISION),
        "create order total uses taxed pricing",
    )

    details_response = api_request("get", _orders_url(test_config, str(order_id)))

    assert_status(details_response, 200)
    details_total = Decimal(details_response.json()["total_price"])
    expected_standard_total = product.price * quantity
    assert_equal(
        details_total,
        expected_standard_total.quantize(MONEY_PRECISION),
        "order details total uses standard pricing",
    )
    assert_truthy(
        create_total > details_total, "create order total is greater than standard pricing total"
    )


def test_full_order_lifecycle_writes_complete_outbox_event_sequence(test_config, db_session):
    product = db_query_first(
        db_session.query(Product), "fetch seed product for lifecycle outbox sequence"
    )
    assert product is not None

    create_response = api_request(
        "post",
        _orders_url(test_config),
        json={"items": [{"product_id": product.id, "quantity": 1}]},
    )
    assert_status(create_response, 201)
    order_id = create_response.json()["order_id"]

    order = _get_created_order(db_session, order_id)
    order.status = OrderStatus.PENDING_PAYMENT
    db_session.commit()

    assert_status(api_request("post", _orders_url(test_config, f"{order_id}/pay")), 200)
    assert_status(api_request("post", _orders_url(test_config, f"{order_id}/ready-to-ship")), 200)
    assert_status(api_request("post", _orders_url(test_config, f"{order_id}/shipped")), 200)
    assert_status(api_request("post", _orders_url(test_config, f"{order_id}/delivered")), 200)

    outbox_events = _get_outbox_events_for_order(db_session, order_id)
    assert_equal(
        [event.event_type for event in outbox_events],
        [
            "order.created",
            "order.paid",
            "order.ready.to.ship",
            "order.shipped",
            "order.delivered",
        ],
        "full lifecycle writes the expected outbox event sequence",
    )
