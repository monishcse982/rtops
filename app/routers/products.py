from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette import status

from app.models.database import get_db
from app.models.line_item_model import LineItem
from app.models.product_model import Product
from app.models.product_schemas import (
    ProductCreateRequest,
    ProductDetailsResponse,
    ProductListResponse,
)

router = APIRouter()
VALID_PRODUCT_SORT_FIELDS = {"id", "name", "price", "stock", "created_at"}


def get_product_or_404(db: Session, product_id: int) -> Product:
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found",
        )
    return product


def apply_product_filters(
    query,
    *,
    search: Optional[str],
    min_price: Optional[float],
    max_price: Optional[float],
    in_stock: Optional[bool],
):
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            Product.name.ilike(search_term)
            | func.coalesce(Product.description, "").ilike(search_term)
        )

    if min_price is not None:
        query = query.filter(Product.price >= min_price)

    if max_price is not None:
        query = query.filter(Product.price <= max_price)

    if in_stock is not None:
        query = query.filter(Product.stock > 0 if in_stock else Product.stock == 0)

    return query


@router.get(
    "/products/",
    response_model=ProductListResponse,
    summary="List all products with pagination",
    responses={
        200: {"description": "List of products successfully retrieved"},
        400: {"description": "Invalid query parameters"},
    },
)
async def list_products(
    page: int = Query(1, ge=1, description="Page number, starting from 1"),
    page_size: int = Query(20, ge=1, le=100, description="Number of items per page (1-100)"),
    sort_by: str = Query("id", description="Field to sort by (id, name, price, stock)"),
    sort_order: str = Query("asc", description="Sort order (asc, desc)"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price filter"),
    max_price: Optional[float] = Query(None, gt=0, description="Maximum price filter"),
    in_stock: Optional[bool] = Query(None, description="Filter by stock availability"),
    search: Optional[str] = Query(None, min_length=2, description="Search in name and description"),
    db: Session = Depends(get_db),
):
    """
    Retrieve a paginated list of products with sorting and filtering options.

    ## Query Parameters
    - `page`: Page number (starts at 1)
    - `page_size`: Number of items per page (1-100)
    - `sort_by`: Field to sort by (id, name, price, stock)
    - `sort_order`: Sort direction (asc, desc)
    - `min_price`: Filter by minimum price
    - `max_price`: Filter by maximum price
    - `in_stock`: Filter by stock availability
    - `search`: Search term for name and description

    ## Returns
    A paginated list of products with total count information
    """
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="min_price cannot be greater than max_price",
        )

    query = apply_product_filters(
        db.query(Product),
        search=search,
        min_price=min_price,
        max_price=max_price,
        in_stock=in_stock,
    )

    # Get total count before pagination
    total_items = query.count()

    # Apply sorting
    if sort_by not in VALID_PRODUCT_SORT_FIELDS:
        sort_by = "id"

    sort_column = getattr(Product, sort_by)
    if sort_order.lower() == "desc":
        sort_column = sort_column.desc()
    else:
        sort_column = sort_column.asc()

    query = query.order_by(sort_column)

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Get results
    products = query.all()

    # Calculate total pages
    total_pages = (total_items + page_size - 1) // page_size

    return {
        "items": products,
        "total": total_items,
        "page": page,
        "page_size": page_size,
        "pages": total_pages,
    }


@router.get(
    "/products/{product_id}",
    response_model=ProductDetailsResponse,
    summary="Get detailed product information",
    responses={
        200: {"description": "Product details successfully retrieved"},
        404: {"description": "Product not found"},
    },
)
async def get_product(
    product_id: int = Path(..., gt=0, description="The ID of the product to retrieve"),
    db: Session = Depends(get_db),
):
    """
    Retrieve detailed information about a specific product.

    ## Path Parameter
    - **product_id**: The unique identifier of the product

    ## Returns
    Detailed product information including stock level and pricing

    ## Raises
    - **404 Not Found**: If the product with the specified ID doesn't exist
    """
    return get_product_or_404(db, product_id)


@router.post(
    "/products/",
    response_model=ProductDetailsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new product",
    responses={
        201: {"description": "Product successfully created"},
        400: {"description": "Invalid product data"},
        409: {"description": "Product with this name already exists"},
    },
)
async def add_product(product: ProductCreateRequest, db: Session = Depends(get_db)):
    """
    Create a new product in the inventory.

    ## Request Body
    - `name`: Product name (required)
    - `description`: Optional product description
    - `price`: Product price (required, > 0)
    - `stock`: Available inventory (required, >= 0)

    ## Returns
    The created product with its assigned ID

    ## Raises
    - `400 Bad Request`: If the product data is invalid
    - `409 Conflict`: If a product with the same name already exists
    """
    if db.query(Product.id).filter(Product.name == product.name).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Product with name '{product.name}' already exists",
        )

    new_product = Product(
        name=product.name,
        description=product.description,
        price=product.price,
        stock=product.stock,
        created_at=datetime.now(UTC),
    )
    db.add(new_product)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Product with name '{product.name}' already exists",
        )

    db.refresh(new_product)
    return new_product


@router.put(
    "/products/{product_id}",
    response_model=ProductDetailsResponse,
    summary="Update an existing product",
    responses={
        200: {"description": "Product successfully updated"},
        400: {"description": "Invalid product data"},
        404: {"description": "Product not found"},
        409: {"description": "Name conflict with existing product"},
    },
)
async def update_product(
    product_id: int = Path(..., gt=0, description="The ID of the product to update"),
    product_data: ProductCreateRequest = Body(...),
    db: Session = Depends(get_db),
):
    """
    Update an existing product's information.

    ## Path Parameter
    - `product_id`: The unique identifier of the product to update

    ## Request Body
    - `name`: Updated product name
    - `description`: Updated product description
    - `price`: Updated product price
    - `stock`: Updated inventory level

    ## Returns
    The updated product information

    ## Raises
    - `404 Not Found`: If the product doesn't exist
    - `409 Conflict`: If updating would create a name conflict
    """
    try:
        product = get_product_or_404(db, product_id)

        # Check for name conflict if name is being changed
        if product_data.name != product.name:
            existing = db.query(Product.id).filter(Product.name == product_data.name).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Product with name '{product_data.name}' already exists",
                )

        # Update fields
        for key, value in product_data.dict().items():
            setattr(product, key, value)

        # Update the updated_at timestamp
        product.updated_at = datetime.now(UTC)

        db.commit()
        db.refresh(product)
        return product
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not update product due to database constraint violation",
        )


@router.delete(
    "/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a product",
    responses={
        204: {"description": "Product successfully deleted"},
        404: {"description": "Product not found"},
        400: {"description": "Cannot delete product with active orders"},
    },
)
async def delete_product(
    product_id: int = Path(..., gt=0, description="The ID of the product to delete"),
    db: Session = Depends(get_db),
):
    """
    Delete a product from the inventory.

    ## Path Parameter
    - `product_id`: The unique identifier of the product to delete

    ## Returns
    No content on successful deletion

    ## Raises
    - `404 Not Found`: If the product doesn't exist
    - `400 Bad Request`: If the product cannot be deleted (e.g., referenced by orders)
    """
    product = get_product_or_404(db, product_id)

    if db.query(LineItem.id).filter(LineItem.product_id == product_id).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete product that is referenced in existing orders",
        )

    try:
        db.delete(product)
        db.commit()
        return None  # 204 No Content
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while deleting: {str(e)}",
        )
