from decimal import Decimal
from pydantic import BaseModel, Field


class OrderItemDetail(BaseModel):
    product_id: int
    name: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal


class OrderItemRequest(BaseModel):
    product_id: int = Field(gt=0, description="Product ID to include in the order")
    quantity: int = Field(gt=0, description="Quantity of the product to order")
