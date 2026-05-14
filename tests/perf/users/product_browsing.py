import random
from decimal import Decimal

from locust import task

from tests.perf.base_user import BaseApiUser
from tests.perf.commons import DEFAULT_WAIT


class ProductBrowsingUser(BaseApiUser):
    wait_time = DEFAULT_WAIT

    @staticmethod
    def _price(value) -> Decimal:
        return Decimal(str(value))

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

    @task
    def list_products_with_pagination(self):
        page = random.randint(1, 5)
        page_size = random.choice([10, 20, 50])
        get_products_payload = self.get_json_ok(
            f"/api/products/?page={page}&page_size={page_size}",
            name="GET /api/products/?page={page}&page_size={page_size}",
        )
        assert get_products_payload["page"] == page
        assert get_products_payload["page_size"] == page_size
        assert get_products_payload["total"] > 0

    @task
    def browse_random_page_then_random_product(self):
        page = random.randint(1, 5)
        get_products_payload = self.get_json_ok(
            f"/api/products/?page={page}",
            name="GET /api/products/?page={page}",
        )
        assert get_products_payload["page"] == page
        items = get_products_payload["items"]
        if not items:
            return
        product_id = random.choice(items)["id"]
        get_product_payload = self.get_json_ok(
            f"/api/products/{product_id}",
            name="GET /api/products/{id}",
        )
        assert product_id == get_product_payload["id"]

    @task
    def sort_products_by_price_asc(self):
        get_products_payload = self.get_json_ok(
            "/api/products/?sort_by=price&sort_order=asc",
            name="GET /api/products/?sort_by=price&sort_order=asc",
        )
        items = get_products_payload["items"]
        assert items
        prices = [self._price(item["price"]) for item in items]
        assert prices == sorted(prices)

    @task
    def sort_products_by_price_desc(self):
        get_products_payload = self.get_json_ok(
            "/api/products/?sort_by=price&sort_order=desc",
            name="GET /api/products/?sort_by=price&sort_order=desc",
        )
        items = get_products_payload["items"]
        assert items
        prices = [self._price(item["price"]) for item in items]
        assert prices == sorted(prices, reverse=True)

    @task
    def filter_products_by_stock(self):
        in_stock = random.choice([True, False])
        get_products_payload = self.get_json_ok(
            f"/api/products/?in_stock={in_stock}",
            name="GET /api/products/?in_stock={value}",
        )
        items = get_products_payload["items"]
        for item in items:
            if in_stock:
                assert item["stock"] > 0
            else:
                assert item["stock"] == 0

    @task
    def filter_products_by_price_range(self):
        min_price = Decimal(str(round(random.uniform(0, 100), 2)))
        max_price = Decimal(str(round(random.uniform(float(min_price), 200), 2)))
        get_products_payload = self.get_json_ok(
            f"/api/products/?min_price={min_price}&max_price={max_price}",
            name="GET /api/products/?min_price={min_price}&max_price={max_price}",
        )
        items = get_products_payload["items"]
        for item in items:
            price = self._price(item["price"])
            assert min_price <= price <= max_price

    @task
    def search_products_by_keyword(self):
        keyword = "shirt"
        get_products_payload = self.get_json_ok(
            f"/api/products/?search={keyword}",
            name="GET /api/products/?search={keyword}",
        )
        items = get_products_payload["items"]
        if not items:
            return

    @task
    def search_products_with_combined_filters(self) -> None:
        keyword = "lamp"
        min_price = Decimal(str(round(random.uniform(0, 100), 2)))
        max_price = Decimal(str(round(random.uniform(float(min_price), 200), 2)))
        in_stock = random.choice([True, False])
        get_products_payload = self.get_json_ok(
            f"/api/products/?search={keyword}&min_price={min_price}&max_price={max_price}&in_stock={in_stock}",
            name="GET /api/products/?search={keyword}&min_price={min_price}&max_price={max_price}&in_stock={value}",
        )
        items = get_products_payload["items"]
        if not items:
            return
        for item in items:
            assert keyword.lower() in item["name"].lower() or (
                item["description"] and keyword.lower() in item["description"].lower()
            )
            price = self._price(item["price"])
            assert min_price <= price <= max_price
            if in_stock:
                assert item["stock"] > 0
            else:
                assert item["stock"] == 0


__all__ = ["ProductBrowsingUser"]
