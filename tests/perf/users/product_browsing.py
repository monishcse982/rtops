import random

from locust import task

from tests.perf.base_user import BaseApiUser
from tests.perf.commons import DEFAULT_WAIT


class ProductBrowsingUser(BaseApiUser):
    wait_time = DEFAULT_WAIT

    @task
    def browse_product_by_id(self):
        get_products_payload = self.get_json_ok(
            "/api/products/",
            name="GET /api/products/",
        )
        items = get_products_payload["items"]
        assert items

        product_id = random.choice(items)["id"]
        get_product_payload = self.get_json_ok(
            f"/api/products/{product_id}",
            name="GET /api/products/{id}",
        )
        assert product_id == get_product_payload["id"]
