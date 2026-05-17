import random

from locust import task

from app.models.line_item_schemas import OrderItemRequest
from app.models.order_schemas import OrderCreateRequest
from tests.perf.base_user import BaseApiUser
from tests.perf.commons import SHORT_WAIT


class OrdersActions(BaseApiUser):
    wait_time = SHORT_WAIT
    RECENT_ORDER_LIMIT = 50

    def on_start(self):
        self.recent_order_ids: list[int] = []

    def _load_products(self) -> list[dict]:
        get_products_payload = self.get_json_ok(
            "/api/products/",
            name="GET /api/products/",
        )
        products = get_products_payload["items"]
        assert products
        return products

    def _remember_order(self, order_id: int) -> None:
        self.recent_order_ids.append(order_id)
        if len(self.recent_order_ids) > self.RECENT_ORDER_LIMIT:
            self.recent_order_ids = self.recent_order_ids[-self.RECENT_ORDER_LIMIT :]

    def _create_order(self, line_items: list[OrderItemRequest]) -> dict:
        create_order_request_payload = OrderCreateRequest(items=line_items)
        create_order_response_payload = self.post_json_ok(
            "/api/orders/",
            name="POST /api/orders/",
            json_body=create_order_request_payload.model_dump(),
        )
        assert create_order_response_payload["order_id"]
        assert create_order_response_payload["status"] == "created"
        assert create_order_response_payload["total_price"] is not None
        self._remember_order(create_order_response_payload["order_id"])
        return create_order_response_payload

    @task(3)
    def create_single_item_order(self):
        products = self._load_products()
        product_id = random.choice(products)["id"]
        quantity = random.randint(1, 10)

        create_order_response_payload = self._create_order(
            [OrderItemRequest(product_id=product_id, quantity=quantity)]
        )
        order_id = create_order_response_payload["order_id"]
        get_order_response_payload = self.get_json_ok(
            f"/api/orders/{order_id}",
            name="GET /api/orders/{id}",
        )
        assert get_order_response_payload["order_id"] == order_id
        assert get_order_response_payload["status"] == "created"
        assert len(get_order_response_payload["items"]) == 1

    @task(2)
    def create_multiple_item_order(self):
        products = self._load_products()
        assert len(products) >= 2

        item_count = random.randint(2, min(3, len(products)))
        selected_products = random.sample(products, item_count)
        line_items = [
            OrderItemRequest(
                product_id=product["id"],
                quantity=random.randint(1, 10),
            )
            for product in selected_products
        ]
        create_order_response_payload = self._create_order(line_items)
        assert create_order_response_payload["status"] == "created"

    @task(2)
    def get_recent_order_details(self):
        if not self.recent_order_ids:
            self.create_single_item_order()
            return

        order_id = random.choice(self.recent_order_ids)
        get_order_response_payload = self.get_json_ok(
            f"/api/orders/{order_id}",
            name="GET /api/orders/{id}",
        )
        assert get_order_response_payload["order_id"] == order_id
        assert get_order_response_payload["items"]
        assert get_order_response_payload["total_price"] is not None

    @task(1)
    def create_order_and_validate_details(self):
        products = self._load_products()
        item_count = random.randint(1, min(3, len(products)))
        selected_products = random.sample(products, item_count)
        requested_quantities = {
            product["id"]: random.randint(1, 5) for product in selected_products
        }
        create_order_response_payload = self._create_order(
            [
                OrderItemRequest(
                    product_id=product["id"], quantity=requested_quantities[product["id"]]
                )
                for product in selected_products
            ]
        )
        order_id = create_order_response_payload["order_id"]
        get_order_response_payload = self.get_json_ok(
            f"/api/orders/{order_id}",
            name="GET /api/orders/{id}",
        )
        assert get_order_response_payload["order_id"] == order_id
        assert len(get_order_response_payload["items"]) == item_count
        returned_product_ids = {item["product_id"] for item in get_order_response_payload["items"]}
        assert returned_product_ids == set(requested_quantities)
        returned_quantities = {
            item["product_id"]: item["quantity"] for item in get_order_response_payload["items"]
        }
        assert returned_quantities == requested_quantities


__all__ = ["OrdersActions"]
