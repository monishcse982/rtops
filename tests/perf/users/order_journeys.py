import random

from locust import task

from app.models.line_item_schemas import OrderItemRequest
from app.models.order_schemas import OrderCreateRequest
from tests.perf.base_user import BaseApiUser
from tests.perf.commons import MEDIUM_WAIT


class OrderJourneysUser(BaseApiUser):
    wait_time = MEDIUM_WAIT

    def _load_products(self, *, path: str, name: str) -> list[dict]:
        get_products_payload = self.get_json_ok(path, name=name)
        products = get_products_payload["items"]
        assert products
        return products

    def _create_order(self, items: list[OrderItemRequest]) -> dict:
        create_order_payload = OrderCreateRequest(items=items)
        create_order_response_payload = self.post_json_ok(
            "/api/orders/",
            name="POST /api/orders/",
            json_body=create_order_payload.model_dump(),
        )
        assert create_order_response_payload["order_id"]
        assert create_order_response_payload["status"] == "created"
        assert create_order_response_payload["total_price"] is not None
        return create_order_response_payload

    @task(3)
    def browse_product_then_checkout(self):
        products = self._load_products(
            path="/api/products/",
            name="GET /api/products/",
        )
        selected_product = random.choice(products)
        product_id = selected_product["id"]

        get_product_response_payload = self.get_json_ok(
            f"/api/products/{product_id}",
            name="GET /api/products/{id}",
        )
        assert get_product_response_payload["id"] == product_id

        create_order_response_payload = self._create_order(
            [
                OrderItemRequest(
                    product_id=product_id,
                    quantity=random.randint(1, 5),
                )
            ]
        )
        order_id = create_order_response_payload["order_id"]

        get_order_response_payload = self.get_json_ok(
            f"/api/orders/{order_id}",
            name="GET /api/orders/{id}",
        )
        assert get_order_response_payload["order_id"] == order_id
        assert len(get_order_response_payload["items"]) == 1

    @task(2)
    def browse_filtered_products_then_checkout(self):
        page = random.randint(1, 3)
        page_size = random.choice([10, 20])
        products = self._load_products(
            path=f"/api/products/?page={page}&page_size={page_size}",
            name="GET /api/products/?page={page}&page_size={page_size}",
        )
        selected_product = random.choice(products)
        product_id = selected_product["id"]

        create_order_response_payload = self._create_order(
            [
                OrderItemRequest(
                    product_id=product_id,
                    quantity=random.randint(1, 3),
                )
            ]
        )
        order_id = create_order_response_payload["order_id"]
        get_order_response_payload = self.get_json_ok(
            f"/api/orders/{order_id}",
            name="GET /api/orders/{id}",
        )
        assert get_order_response_payload["order_id"] == order_id
        returned_product_ids = {item["product_id"] for item in get_order_response_payload["items"]}
        assert returned_product_ids == {product_id}

    @task(1)
    def multi_product_checkout_journey(self):
        products = self._load_products(
            path="/api/products/?sort_by=price&sort_order=asc",
            name="GET /api/products/?sort_by=price&sort_order=asc",
        )
        assert len(products) >= 2

        selected_products = random.sample(products, min(3, len(products)))
        requested_quantities = {
            product["id"]: random.randint(1, 4) for product in selected_products
        }
        create_order_response_payload = self._create_order(
            [
                OrderItemRequest(
                    product_id=product["id"],
                    quantity=requested_quantities[product["id"]],
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
        returned_quantities = {
            item["product_id"]: item["quantity"] for item in get_order_response_payload["items"]
        }
        assert returned_quantities == requested_quantities


__all__ = ["OrderJourneysUser"]
