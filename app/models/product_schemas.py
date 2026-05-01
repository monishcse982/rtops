from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field, condecimal, field_validator


class ProductCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Gaming Mouse",
                "description": "High-precision gaming mouse with adjustable DPI",
                "price": 49.99,
                "stock": 100,
            }
        }
    )

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Product name (1-100 characters)",
        json_schema_extra={"example": "Ergonomic Keyboard"},
    )
    description: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional product description (max 500 characters)",
        json_schema_extra={"example": "Mechanical keyboard with ergonomic design"},
    )
    price: condecimal(gt=0, decimal_places=2) = Field(
        ..., description="Product price (greater than 0)", json_schema_extra={"example": 99.99}
    )
    stock: int = Field(
        ...,
        ge=0,
        description="Available inventory quantity (0 or greater)",
        json_schema_extra={"example": 25},
    )

    @field_validator("name")
    @classmethod
    def name_must_be_valid(cls, v):
        if not v.strip():
            raise ValueError("Name cannot be empty or just whitespace")
        return v.strip()


class ProductResponse(ProductCreate):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "name": "Gaming Mouse",
                "description": "High-precision gaming mouse with adjustable DPI",
                "price": 49.99,
                "stock": 100,
                "created_at": "2025-03-20T18:30:45.123Z",
                "updated_at": None,
            }
        }
    )

    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None


class ProductList(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": 1,
                        "name": "Gaming Mouse",
                        "description": "High-precision gaming mouse with adjustable DPI",
                        "price": 49.99,
                        "stock": 100,
                        "created_at": "2025-03-20T18:30:45.123Z",
                        "updated_at": None,
                    }
                ],
                "total": 42,
                "page": 1,
                "page_size": 20,
                "pages": 3,
            }
        }
    )

    items: List[ProductResponse]
    total: int
    page: int
    page_size: int
    pages: int
