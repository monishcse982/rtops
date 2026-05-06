from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.line_item_model import LineItem
from app.models.order_model import Order
from app.models.product_model import Product
from app.models.product_schemas import ProductCreateRequest
from reporting import (
    api_request,
    assert_equal,
    assert_header,
    assert_status,
    assert_truthy,
    db_query_first,
    db_query_one,
)

PRODUCTS_PATH = "/api/products/"


def _products_url(test_config, suffix: str = "") -> str:
    return f"{test_config.api_url.rstrip('/')}{PRODUCTS_PATH}{suffix}"


def _unique_product_name(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def _insert_product(
    db_session,
    *,
    name: str,
    price: Decimal,
    stock: int,
    description: str = "Inserted by E2E test",
) -> Product:
    product = Product(name=name, description=description, price=price, stock=stock)
    db_session.add(product)
    db_session.commit()
    return product


def test_create_product_persists_record(test_config, db_session):
    product_name = _unique_product_name("e2e-product")
    product_request = ProductCreateRequest(
        name=product_name,
        description="Created by E2E test",
        price=Decimal("19.99"),
        stock=7,
    )

    response = api_request(
        "post",
        _products_url(test_config),
        json=product_request.model_dump(mode="json"),
    )

    assert_status(response, 201)
    response_body = response.json()
    product_id = response_body["id"]

    db_session.expire_all()
    created_product = db_query_one(
        db_session.query(Product).filter(Product.id == product_id),
        f"fetch product row for product_id={product_id}",
    )
    assert_equal(created_product.name, product_name, "created product name matches request")
    assert_equal(
        created_product.description,
        "Created by E2E test",
        "created product description matches request",
    )
    assert_equal(created_product.price, Decimal("19.99"), "created product price matches request")
    assert_equal(created_product.stock, 7, "created product stock matches request")


def test_create_product_rejects_duplicate_name(test_config, db_session):
    existing_product = db_query_first(
        db_session.query(Product),
        "fetch existing product for duplicate-name check",
    )
    assert existing_product is not None

    response = api_request(
        "post",
        _products_url(test_config),
        json={
            "name": existing_product.name,
            "description": "Duplicate attempt",
            "price": "12.50",
            "stock": 3,
        },
    )

    assert_status(response, 409)


def test_get_nonexistent_product_returns_404(test_config):
    response = api_request("get", _products_url(test_config, "999999"))

    assert_status(response, 404)
    assert_equal(
        response.json()["detail"],
        "Product with ID 999999 not found",
        "missing product error message",
    )


def test_get_product_with_invalid_path_parameter_returns_422(test_config):
    response = api_request("get", _products_url(test_config, "0"))

    assert_status(response, 422)


def test_list_products_returns_paginated_payload(test_config):
    response = api_request("get", _products_url(test_config), params={"page": 1, "page_size": 5})

    assert_status(response, 200)
    response_body = response.json()
    assert_truthy("items" in response_body, "product list response contains items")
    assert_truthy("total" in response_body, "product list response contains total")
    assert_truthy("page" in response_body, "product list response contains page")
    assert_equal(response_body["page"], 1, "product list page matches request")
    assert_equal(response_body["page_size"], 5, "product list page size matches request")
    assert_truthy(len(response_body["items"]) <= 5, "product list is limited by page size")


def test_list_products_with_filters(test_config, db_session):
    product = db_query_first(
        db_session.query(Product), "fetch seed product for product filter check"
    )
    assert product is not None

    response = api_request(
        "get",
        _products_url(test_config),
        params={"search": product.name[:3], "min_price": 0, "max_price": 10_000},
    )

    assert_status(response, 200)
    response_body = response.json()
    assert response_body["total"] >= 1
    assert any(item["id"] == product.id for item in response_body["items"])


def test_list_products_with_ascending_sort(test_config, db_session):
    prefix = _unique_product_name("sort-asc")
    inserted_products = [
        _insert_product(db_session, name=f"{prefix}-a", price=Decimal("30.00"), stock=1),
        _insert_product(db_session, name=f"{prefix}-b", price=Decimal("10.00"), stock=1),
        _insert_product(db_session, name=f"{prefix}-c", price=Decimal("20.00"), stock=1),
    ]

    response = api_request(
        "get",
        _products_url(test_config),
        params={
            "search": prefix,
            "sort_by": "price",
            "sort_order": "asc",
            "page_size": 100,
        },
    )

    assert_status(response, 200)
    inserted_ids = {product.id for product in inserted_products}
    items = [item for item in response.json()["items"] if item["id"] in inserted_ids]
    prices = [Decimal(item["price"]) for item in items]
    assert prices == sorted(prices)


def test_list_products_with_descending_sort(test_config, db_session):
    prefix = _unique_product_name("sort-desc")
    inserted_products = [
        _insert_product(db_session, name=f"{prefix}-a", price=Decimal("30.00"), stock=1),
        _insert_product(db_session, name=f"{prefix}-b", price=Decimal("10.00"), stock=1),
        _insert_product(db_session, name=f"{prefix}-c", price=Decimal("20.00"), stock=1),
    ]

    response = api_request(
        "get",
        _products_url(test_config),
        params={
            "search": prefix,
            "sort_by": "price",
            "sort_order": "desc",
            "page_size": 100,
        },
    )

    assert_status(response, 200)
    inserted_ids = {product.id for product in inserted_products}
    items = [item for item in response.json()["items"] if item["id"] in inserted_ids]
    prices = [Decimal(item["price"]) for item in items]
    assert prices == sorted(prices, reverse=True)


def test_invalid_product_sort_field_falls_back_safely(test_config, db_session):
    prefix = _unique_product_name("sort-fallback")
    inserted_products = [
        _insert_product(db_session, name=f"{prefix}-b", price=Decimal("20.00"), stock=1),
        _insert_product(db_session, name=f"{prefix}-a", price=Decimal("10.00"), stock=1),
    ]
    expected_ids = sorted(product.id for product in inserted_products)

    response = api_request(
        "get",
        _products_url(test_config),
        params={"search": prefix, "sort_by": "not_a_real_field", "page_size": 100},
    )

    assert_status(response, 200)
    items = [item for item in response.json()["items"] if item["id"] in set(expected_ids)]
    assert [item["id"] for item in items] == expected_ids


def test_filter_products_with_in_stock_true(test_config, db_session):
    prefix = _unique_product_name("stock-true")
    product = _insert_product(db_session, name=prefix, price=Decimal("12.00"), stock=5)

    response = api_request(
        "get",
        _products_url(test_config),
        params={"search": prefix, "in_stock": "true", "page_size": 100},
    )

    assert_status(response, 200)
    items = response.json()["items"]
    assert any(item["id"] == product.id for item in items)
    assert all(item["stock"] > 0 for item in items)


def test_filter_products_with_in_stock_false(test_config, db_session):
    prefix = _unique_product_name("stock-false")
    product = _insert_product(db_session, name=prefix, price=Decimal("12.00"), stock=0)

    response = api_request(
        "get",
        _products_url(test_config),
        params={"search": prefix, "in_stock": "false", "page_size": 100},
    )

    assert_status(response, 200)
    items = response.json()["items"]
    assert any(item["id"] == product.id for item in items)
    assert all(item["stock"] == 0 for item in items)


def test_product_search_term_shorter_than_minimum_length_is_rejected(test_config):
    response = api_request("get", _products_url(test_config), params={"search": "a"})

    assert_status(response, 422)


def test_pagination_beyond_available_product_pages_returns_empty_page_safely(
    test_config, db_session
):
    prefix = _unique_product_name("page-beyond")
    _insert_product(db_session, name=f"{prefix}-1", price=Decimal("10.00"), stock=1)
    _insert_product(db_session, name=f"{prefix}-2", price=Decimal("11.00"), stock=1)

    first_page_response = api_request(
        "get",
        _products_url(test_config),
        params={"search": prefix, "page": 1, "page_size": 1},
    )

    assert_status(first_page_response, 200)
    pages = first_page_response.json()["pages"]

    beyond_response = api_request(
        "get",
        _products_url(test_config),
        params={"search": prefix, "page": pages + 1, "page_size": 1},
    )

    assert_status(beyond_response, 200)
    response_body = beyond_response.json()
    assert response_body["items"] == []
    assert response_body["page"] == pages + 1
    assert response_body["pages"] == pages


def test_reject_invalid_price_filter_range(test_config):
    response = api_request(
        "get",
        _products_url(test_config),
        params={"min_price": 10, "max_price": 5},
    )

    assert_status(response, 400)
    assert_equal(
        response.json()["detail"],
        "min_price cannot be greater than max_price",
        "invalid price range error message",
    )


def test_get_product_returns_expected_product(test_config, db_session):
    product = db_query_first(db_session.query(Product), "fetch seed product for get product check")
    assert product is not None

    response = api_request("get", _products_url(test_config, str(product.id)))

    assert_status(response, 200)
    response_body = response.json()
    assert response_body["id"] == product.id
    assert response_body["name"] == product.name
    assert Decimal(response_body["price"]) == product.price
    assert response_body["stock"] == product.stock


def test_update_product_updates_persisted_record(test_config, db_session):
    product = db_query_first(db_session.query(Product), "fetch seed product for update check")
    assert product is not None

    updated_name = _unique_product_name("updated-product")
    response = api_request(
        "put",
        _products_url(test_config, str(product.id)),
        json={
            "name": updated_name,
            "description": "Updated by E2E test",
            "price": "49.99",
            "stock": 11,
        },
    )

    assert_status(response, 200)

    db_session.expire_all()
    updated_product = db_query_one(
        db_session.query(Product).filter(Product.id == product.id),
        f"fetch updated product row for product_id={product.id}",
    )
    assert_equal(updated_product.name, updated_name, "updated product name matches request")
    assert_equal(
        updated_product.description,
        "Updated by E2E test",
        "updated product description matches request",
    )
    assert_equal(updated_product.price, Decimal("49.99"), "updated product price matches request")
    assert_equal(updated_product.stock, 11, "updated product stock matches request")


def test_products_endpoint_echoes_request_tracing_headers(test_config):
    response = api_request(
        "get",
        _products_url(test_config),
        headers={"X-Request-ID": "req-products-list-001"},
    )

    assert_status(response, 200)
    assert_header(response, "X-Request-ID", "req-products-list-001")
    assert_header(response, "X-Trace-ID", "req-products-list-001")


def test_generated_request_id_is_returned_on_products_endpoint_when_omitted(test_config):
    response = api_request("get", _products_url(test_config))

    assert_status(response, 200)
    generated_request_id = response.headers["X-Request-ID"]
    assert_truthy(generated_request_id, "generated request id is returned")
    assert_header(response, "X-Trace-ID", generated_request_id)


def test_update_product_rejects_name_conflict(test_config, db_session):
    product1 = db_query_first(
        db_session.query(Product), "fetch first seed product for name conflict"
    )
    product2 = db_query_first(
        db_session.query(Product).offset(1),
        "fetch second seed product for name conflict",
    )
    assert product1 is not None and product2 is not None

    original_name = product1.name
    response = api_request(
        "put",
        _products_url(test_config, str(product1.id)),
        json={
            "name": product2.name,
            "description": product1.description,
            "price": str(product1.price),
            "stock": product1.stock,
        },
    )

    assert_status(response, 409)

    db_session.expire_all()
    unchanged_product = db_query_one(
        db_session.query(Product).filter(Product.id == product1.id),
        f"fetch product row after conflict for product_id={product1.id}",
    )
    assert_equal(
        unchanged_product.name, original_name, "product name remains unchanged after conflict"
    )


def test_update_product_with_invalid_path_parameter_returns_422(test_config):
    response = api_request(
        "put",
        _products_url(test_config, "0"),
        json={
            "name": _unique_product_name("invalid-update"),
            "description": "Invalid path",
            "price": "10.00",
            "stock": 1,
        },
    )

    assert_status(response, 422)


@pytest.mark.parametrize("name", ["", "   "])
def test_create_product_rejects_blank_name(test_config, name):
    response = api_request(
        "post",
        _products_url(test_config),
        json={
            "name": name,
            "description": "Blank name attempt",
            "price": "10.00",
            "stock": 1,
        },
    )

    assert_status(response, 422)


@pytest.mark.parametrize("name", ["", "   "])
def test_update_product_rejects_blank_name(test_config, db_session, name):
    product = db_query_first(db_session.query(Product), "fetch seed product for blank-name update")
    assert product is not None

    original_name = product.name
    response = api_request(
        "put",
        _products_url(test_config, str(product.id)),
        json={
            "name": name,
            "description": product.description,
            "price": str(product.price),
            "stock": product.stock,
        },
    )

    assert_status(response, 422)

    db_session.expire_all()
    unchanged_product = db_query_one(
        db_session.query(Product).filter(Product.id == product.id),
        f"fetch product row after blank-name update for product_id={product.id}",
    )
    assert_equal(
        unchanged_product.name, original_name, "product name remains unchanged after blank update"
    )


def test_product_name_is_trimmed_before_persistence(test_config, db_session):
    raw_name = f"  {_unique_product_name('trimmed-product')}  "
    response = api_request(
        "post",
        _products_url(test_config),
        json={
            "name": raw_name,
            "description": "Whitespace trimmed",
            "price": "22.00",
            "stock": 4,
        },
    )

    assert_status(response, 201)
    response_body = response.json()
    assert_equal(response_body["name"], raw_name.strip(), "response product name is trimmed")

    db_session.expire_all()
    product = db_query_one(
        db_session.query(Product).filter(Product.id == response_body["id"]),
        f"fetch trimmed product row for product_id={response_body['id']}",
    )
    assert_equal(product.name, raw_name.strip(), "persisted product name is trimmed")


def test_delete_product_removes_unused_product(test_config, db_session):
    product = Product(
        name=_unique_product_name("delete-product"),
        description="To be deleted",
        price=Decimal("15.00"),
        stock=2,
    )

    db_session.add(product)
    db_session.commit()

    product_id = product.id
    response = api_request("delete", _products_url(test_config, str(product_id)))

    assert_status(response, 204)

    db_session.expire_all()
    deleted_product = db_query_first(
        db_session.query(Product).filter(Product.id == product_id),
        f"fetch deleted product row for product_id={product_id}",
    )
    assert_equal(deleted_product, None, "deleted product no longer exists")


def test_delete_product_with_invalid_path_parameter_returns_422(test_config):
    response = api_request("delete", _products_url(test_config, "0"))

    assert_status(response, 422)


def test_delete_product_rejects_product_referenced_by_order(test_config, db_session):
    product = Product(
        name=_unique_product_name("in-use-product"),
        description="Referenced product",
        price=Decimal("9.99"),
        stock=4,
    )
    db_session.add(product)
    db_session.flush()

    order = Order()
    db_session.add(order)
    db_session.flush()

    db_session.add(LineItem(order_id=order.id, product_id=product.id, quantity=1))
    db_session.commit()

    response = api_request("delete", _products_url(test_config, str(product.id)))

    assert_status(response, 400)
    assert_equal(
        response.json()["detail"],
        "Cannot delete product that is referenced in existing orders",
        "delete referenced product error message",
    )
