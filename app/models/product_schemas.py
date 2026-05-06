from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ProductCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100, description="Product name")
    description: Optional[str] = Field(
        None, max_length=500, description="Optional product description"
    )
    price: Decimal = Field(gt=0, description="Product price")
    stock: int = Field(ge=0, description="Available inventory quantity")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        stripped_value = value.strip()
        if not stripped_value:
            raise ValueError("Name cannot be empty or just whitespace")
        return stripped_value


class ProductDetailsResponse(ProductCreateRequest):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None


class ProductListResponse(BaseModel):
    items: list[ProductDetailsResponse]
    total: int
    page: int
    page_size: int
    pages: int
