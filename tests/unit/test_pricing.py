from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.exceptions import IncompleteOrderPricingError, InvalidPricingConfigurationError
from app.services.pricing import DiscountPricing, StandardPricing, TaxedPricing


def make_order(*line_items):
    return SimpleNamespace(line_items=list(line_items))


def make_line_item(price, quantity):
    product = None if price is None else SimpleNamespace(id=1, price=price)
    return SimpleNamespace(id=1, product=product, quantity=quantity)


def test_standard_pricing_calculates_decimal_total():
    order = make_order(
        make_line_item(Decimal("10.50"), 2),
        make_line_item(Decimal("3.25"), 1),
    )

    total = StandardPricing().calculate(order)

    assert total == Decimal("24.25")


def test_taxed_pricing_rejects_negative_tax_rate():
    with pytest.raises(InvalidPricingConfigurationError):
        TaxedPricing(tax_rate=-0.1)


def test_discount_pricing_rejects_discount_rate_above_one():
    with pytest.raises(InvalidPricingConfigurationError):
        DiscountPricing(discount_threshold=100, discount_rate=1.5)


def test_pricing_raises_when_line_item_product_is_missing():
    order = make_order(SimpleNamespace(id=99, product=None, quantity=1))

    with pytest.raises(IncompleteOrderPricingError):
        StandardPricing().calculate(order)


def test_pricing_raises_when_product_price_is_missing():
    line_item = SimpleNamespace(
        id=42,
        product=SimpleNamespace(id=7, price=None),
        quantity=1,
    )
    order = make_order(line_item)

    with pytest.raises(IncompleteOrderPricingError):
        StandardPricing().calculate(order)


def test_discount_pricing_applies_discount_above_threshold():
    order = make_order(
        make_line_item(Decimal("75.00"), 2),
        make_line_item(Decimal("10.00"), 1),
    )

    total = DiscountPricing(discount_threshold=100, discount_rate=Decimal("0.10")).calculate(order)

    assert total == Decimal("144.00")
