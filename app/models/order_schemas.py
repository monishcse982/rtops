from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.line_item_schemas import LineItemDetail, LineItemCreate


class OrderDetailResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "order_id": 123,
                "status": "created",
                "created_at": "2025-03-20T14:30:00",
                "items": [
                    {
                        "item_id": 1,
                        "name": "Product A",
                        "quantity": 2,
                        "unit_price": 24.99,
                        "subtotal": 49.98,
                    },
                    {
                        "item_id": 3,
                        "name": "Product C",
                        "quantity": 1,
                        "unit_price": 9.99,
                        "subtotal": 9.99,
                    },
                ],
                "total_price": 59.97,
            }
        }
    )

    order_id: int
    status: str
    created_at: datetime
    items: List[LineItemDetail]
    total_price: Decimal


class ShippingInfo(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"carrier": "FedEx", "tracking_number": "FX123456789US"}}
    )

    carrier: str = Field(..., description="Shipping carrier name")
    tracking_number: str = Field(..., description="Package tracking number")


class OrderStatusResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Order successfully marked as shipped",
                "order_id": 123,
                "status": "shipped",
                "tracking_info": {
                    "carrier": "FedEx",
                    "tracking_number": "FX123456789US",
                },
            }
        }
    )

    message: str
    order_id: int
    status: str
    tracking_info: Optional[ShippingInfo] = None


class OrderCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"items": [{"item_id": 1, "quantity": 2}, {"item_id": 3, "quantity": 1}]}
        }
    )
    items: List[LineItemCreate] = Field(
        ..., min_length=1, description="Items to include in the order"
    )


class OrderResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Order created successfully",
                "order_id": 123,
                "total_price": 59.99,
                "status": "created",
            }
        }
    )

    message: str
    order_id: int
    total_price: Decimal
    status: str
