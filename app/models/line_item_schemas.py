from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class LineItemDetail(BaseModel):
    item_id: int
    name: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal


class LineItemCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"item_id": 1, "quantity": 2}})

    item_id: int = Field(..., gt=0, description="ID of the item to order")
    quantity: int = Field(..., gt=0, description="Quantity of items to order")
