import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import logger
from app.models.database import SessionLocal
from app.models.line_item_model import LineItem
from app.models.order_model import Order, OrderStatus
from app.models.product_model import Product


SEED_DATA_PATH = Path(__file__).with_name("seed_data.json")


def load_seed_data(path: Path = SEED_DATA_PATH) -> dict[str, list[dict[str, Any]]]:
    with path.open("r", encoding="utf-8") as seed_file:
        payload = json.load(seed_file)

    if not isinstance(payload, dict):
        raise ValueError("Seed data must be a JSON object")

    products = payload.get("products", [])
    orders = payload.get("orders", [])
    if not isinstance(products, list) or not isinstance(orders, list):
        raise ValueError("Seed data must include list fields: products and orders")

    return {"products": products, "orders": orders}


def seed_products(
    db: Session,
    count: int,
    product_specs: list[dict[str, Any]] | None = None,
) -> None:
    if count <= 0:
        logger.info("Product seeding skipped because count <= 0")
        return

    product_specs = product_specs or load_seed_data()["products"]
    logger.info(f"Seeding up to {count} products from JSON data...")

    existing_names = {name for (name,) in db.query(Product.name).all()}
    target_creations = max(count - len(existing_names), 0)
    created_count = 0
    try:
        for spec in product_specs:
            if created_count >= target_creations:
                break
            if spec["name"] in existing_names:
                continue

            db.add(
                Product(
                    name=spec["name"],
                    description=spec.get("description"),
                    price=Decimal(str(spec["price"])),
                    stock=spec["stock"],
                )
            )
            existing_names.add(spec["name"])
            created_count += 1

        db.commit()
    except Exception:
        db.rollback()
        raise

    logger.info(f"Products seeded. created={created_count}")


def seed_orders(
    db: Session,
    count: int,
    order_specs: list[dict[str, Any]] | None = None,
) -> None:
    if count <= 0:
        logger.info("Order seeding skipped because count <= 0")
        return

    order_specs = order_specs or load_seed_data()["orders"]
    products_by_name = {product.name: product for product in db.query(Product).all()}
    if not products_by_name:
        logger.warning("No products found. Seed products first.")
        return

    logger.info(f"Seeding up to {count} orders from JSON data...")

    existing_orders = db.query(Order.id).count()
    target_creations = max(count - existing_orders, 0)
    created_count = 0
    for spec in order_specs:
        if created_count >= target_creations:
            break

        try:
            missing_products = [
                item_spec["product_name"]
                for item_spec in spec["line_items"]
                if item_spec["product_name"] not in products_by_name
            ]
            if missing_products:
                logger.warning(
                    "Skipping seed order because referenced products are unavailable: "
                    + ", ".join(missing_products)
                )
                continue

            order = Order(
                status=OrderStatus(spec.get("status", OrderStatus.CREATED.value)),
                carrier=spec.get("carrier"),
                tracking_number=spec.get("tracking_number"),
            )
            db.add(order)
            db.flush()

            for item_spec in spec["line_items"]:
                product_name = item_spec["product_name"]
                product = products_by_name[product_name]

                db.add(
                    LineItem(
                        order_id=order.id,
                        product_id=product.id,
                        quantity=item_spec["quantity"],
                    )
                )

            db.commit()
            created_count += 1
        except Exception:
            db.rollback()
            raise

    logger.info(f"Orders seeded. created={created_count}")


if __name__ == "__main__":
    db: Session = SessionLocal()
    try:
        seed_payload = load_seed_data()
        seed_products(db, len(seed_payload["products"]), seed_payload["products"])
        seed_orders(db, len(seed_payload["orders"]), seed_payload["orders"])
    finally:
        db.close()
