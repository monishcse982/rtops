from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models.line_item_schemas import OrderItemDetail, OrderItemRequest


class OrderDetailsResponse(BaseModel):
    order_id: int
    status: str
    created_at: datetime
    items: list[OrderItemDetail]
    total_price: Decimal


class ShippingDetails(BaseModel):
    carrier: str = Field(description="Shipping carrier name")
    tracking_number: str = Field(description="Package tracking number")


class OrderStatusUpdateResponse(BaseModel):
    message: str
    order_id: int
    status: str
    tracking_info: Optional[ShippingDetails] = None


class OrderCreateRequest(BaseModel):
    items: list[OrderItemRequest] = Field(
        min_length=1, description="Products to include in the order"
    )

    @field_validator("items")
    @classmethod
    def ensure_unique_products(cls, items: list[OrderItemRequest]) -> list[OrderItemRequest]:
        product_ids = [item.product_id for item in items]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("duplicate product_id values are not allowed")
        return items


class OrderCreateResponse(BaseModel):
    message: str
    order_id: int
    total_price: Decimal
    status: str
