from app.models.order_model import Order, OrderStatus
from app.models.product_model import Product
from app.utils.seed_data import load_seed_data, seed_orders, seed_products


def test_load_seed_data_includes_products_and_orders():
    payload = load_seed_data()

    assert len(payload["products"]) >= 20
    assert len(payload["orders"]) >= 10


def test_seed_products_is_repeatable_without_duplicate_names(db_session):
    payload = load_seed_data()

    seed_products(db_session, 5, payload["products"])
    seed_products(db_session, 5, payload["products"])

    assert db_session.query(Product).count() == 5


def test_seed_orders_loads_multiple_business_states(db_session):
    payload = load_seed_data()
    seed_products(db_session, len(payload["products"]), payload["products"])
    seed_orders(db_session, len(payload["orders"]), payload["orders"])

    orders = db_session.query(Order).all()
    expected_statuses = {OrderStatus(order_spec["status"]) for order_spec in payload["orders"]}

    assert len(orders) == len(payload["orders"])
    assert {order.status for order in orders} == expected_statuses


def test_seed_orders_skips_entries_with_unknown_products(db_session):
    payload = load_seed_data()
    seed_products(db_session, 1, payload["products"][:1])
    order_specs = [
        {
            "status": "created",
            "line_items": [{"product_name": payload["products"][0]["name"], "quantity": 1}],
        },
        {
            "status": "pending_payment",
            "line_items": [{"product_name": "Does Not Exist", "quantity": 1}],
        },
    ]

    seed_orders(db_session, len(order_specs), order_specs)

    orders = db_session.query(Order).all()
    assert len(orders) == 1
    assert orders[0].status == OrderStatus.CREATED
