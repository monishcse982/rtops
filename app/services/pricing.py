from abc import ABC, abstractmethod
from decimal import Decimal

from app.exceptions import IncompleteOrderPricingError, InvalidPricingConfigurationError


ZERO = Decimal("0.00")


def _decimal(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _subtotal(order) -> Decimal:
    total = ZERO

    for line_item in order.line_items:
        if getattr(line_item, "product", None) is None:
            raise IncompleteOrderPricingError(
                f"Line item {getattr(line_item, 'id', 'unknown')} is missing product data"
            )

        if line_item.product.price is None:
            raise IncompleteOrderPricingError(
                f"Product {getattr(line_item.product, 'id', 'unknown')} is missing price data"
            )

        total += _decimal(line_item.product.price) * line_item.quantity

    return total


class PricingStrategy(ABC):
    """Abstract base class for pricing strategies"""

    @abstractmethod
    def calculate(self, order):
        pass


class StandardPricing(PricingStrategy):
    """Standard pricing strategy (no discount, no taxes)"""

    def calculate(self, order):
        return _subtotal(order)


class TaxedPricing(PricingStrategy):
    """Pricing strategy that applies a fixed tax percentage"""

    def __init__(self, tax_rate=0.1):
        self.tax_rate = _decimal(tax_rate)
        if self.tax_rate < ZERO:
            raise InvalidPricingConfigurationError("tax_rate cannot be negative")

    def calculate(self, order):
        subtotal = _subtotal(order)
        tax = subtotal * self.tax_rate
        return subtotal + tax


class DiscountPricing(PricingStrategy):
    """Pricing strategy that applies a discount if total exceeds a threshold"""

    def __init__(self, discount_threshold=100, discount_rate=0.1):
        self.discount_threshold = _decimal(discount_threshold)
        self.discount_rate = _decimal(discount_rate)

        if self.discount_threshold < ZERO:
            raise InvalidPricingConfigurationError("discount_threshold cannot be negative")
        if self.discount_rate < ZERO or self.discount_rate > Decimal("1"):
            raise InvalidPricingConfigurationError("discount_rate must be between 0 and 1")

    def calculate(self, order):
        subtotal = _subtotal(order)
        if subtotal > self.discount_threshold:
            discount = subtotal * self.discount_rate
            return subtotal - discount
        return subtotal
