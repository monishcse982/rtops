from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session, joinedload
from starlette import status

from app.config import logger
from app.events.outbox import enqueue_event, publish_pending_events
from app.models.database import get_db
from app.models.line_item_model import LineItem
from app.models.order_model import Order, OrderStatus
from app.models.order_schemas import (
    OrderCreate,
    OrderDetailResponse,
    OrderResponse,
    OrderStatusResponse,
    ShippingInfo,
)
from app.models.product_model import Product
from app.services.pricing import StandardPricing, TaxedPricing

router = APIRouter()
EVENT_ORDER_CREATED = "order.created"
EVENT_ORDER_PAID = "order.paid"
EVENT_ORDER_READY_TO_SHIP = "order.ready.to.ship"
EVENT_ORDER_SHIPPED = "order.shipped"
EVENT_ORDER_DELIVERED = "order.delivered"


def order_status_value(order: Order) -> str:
    return order.status.value if isinstance(order.status, OrderStatus) else str(order.status)


def get_order_or_404(db: Session, order_id: int) -> Order:
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


def require_order_status(order: Order, expected_status: str, action: str) -> None:
    current_status = order_status_value(order)
    if current_status != expected_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order cannot be {action} in its current state: {current_status}",
        )


def enqueue_order_event(db: Session, event_type: str, order_id: int, **extra_data):
    event_data = {
        "event": event_type,
        "order_id": order_id,
        "timestamp": datetime.now(UTC).isoformat(),
        **extra_data,
    }
    return enqueue_event(db, event_type, event_data)


def transition_order(
    *,
    db: Session,
    order_id: int,
    expected_status: str,
    next_status: OrderStatus,
    event_type: str,
    action: str,
    message: str,
) -> OrderStatusResponse:
    order = get_order_or_404(db, order_id)
    require_order_status(order, expected_status, action)

    order.status = next_status
    enqueue_order_event(db, event_type, order.id)
    db.commit()
    publish_pending_events(db, limit=20)
    logger.info(f"Order {order.id} {action} and event queued.")

    return OrderStatusResponse(
        message=message,
        order_id=order.id,
        status=order_status_value(order),
        tracking_info=(
            ShippingInfo(carrier=order.carrier, tracking_number=order.tracking_number)
            if order.carrier and order.tracking_number
            else None
        ),
    )


@router.post(
    "/orders/",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new order with multiple items",
    responses={
        400: {"description": "Invalid request data"},
        404: {"description": "One or more items not found"},
        500: {"description": "Server error"},
    },
)
async def create_order(order_data: OrderCreate, db: Session = Depends(get_db)):
    item_ids = [item.item_id for item in order_data.items]
    available_products = {
        product.id: product for product in db.query(Product).filter(Product.id.in_(item_ids)).all()
    }
    missing = [str(item_id) for item_id in item_ids if item_id not in available_products]

    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Items not found: {', '.join(missing)}",
        )

    new_order = Order()
    db.add(new_order)

    for item_data in order_data.items:
        product = available_products[item_data.item_id]
        new_order.line_items.append(LineItem(product=product, quantity=item_data.quantity))

    db.flush()
    total_price = new_order.calculate_total(TaxedPricing(tax_rate=0.2))

    enqueue_order_event(
        db,
        EVENT_ORDER_CREATED,
        new_order.id,
        total_price=total_price,
    )
    db.commit()
    db.refresh(new_order)
    publish_pending_events(db, limit=20)

    logger.info(f"Order {new_order.id} created with total price: ${total_price:.2f}")

    return OrderResponse(
        message="Order created successfully",
        order_id=new_order.id,
        total_price=total_price,
        status=order_status_value(new_order),
    )


@router.get(
    "/orders/{order_id}",
    response_model=OrderDetailResponse,
    summary="Get order details by ID",
    responses={
        200: {"description": "Order details retrieved successfully"},
        404: {"description": "Order not found"},
    },
)
async def get_order(
    order_id: int = Path(..., gt=0, description="The ID of the order to retrieve"),
    db: Session = Depends(get_db),
):
    order = (
        db.query(Order)
        .filter(Order.id == order_id)
        .options(joinedload(Order.line_items).joinedload(LineItem.product))
        .first()
    )
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    items_detail = [
        {
            "item_id": line.product_id,
            "name": line.product.name,
            "quantity": line.quantity,
            "unit_price": line.product.price,
            "subtotal": line.product.price * line.quantity,
        }
        for line in order.line_items
    ]
    total_price = order.calculate_total(StandardPricing())
    return OrderDetailResponse(
        order_id=order.id,
        status=order_status_value(order),
        created_at=order.created_at,
        items=items_detail,
        total_price=total_price,
    )


@router.post(
    "/orders/{order_id}/pay",
    response_model=OrderStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Simulate payment and mark order as paid",
    responses={
        200: {
            "description": "Order status updated to in_preparation and order.paid event published"
        },
        400: {"description": "Invalid state for payment"},
        404: {"description": "Order not found"},
    },
)
async def pay_order(
    order_id: int = Path(..., gt=0, description="ID of the order to pay"),
    db: Session = Depends(get_db),
):
    return transition_order(
        db=db,
        order_id=order_id,
        expected_status=OrderStatus.PENDING_PAYMENT.value,
        next_status=OrderStatus.IN_PREPARATION,
        event_type=EVENT_ORDER_PAID,
        action="marked as paid",
        message="Order marked as paid",
    )


@router.post(
    "/orders/{order_id}/ready-to-ship",
    response_model=OrderStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark order as ready to ship",
    responses={
        200: {
            "description": "Order status updated to ready_to_ship and order.ready.to.ship event published"
        },
        400: {"description": "Invalid state for marking as ready to ship"},
        404: {"description": "Order not found"},
    },
)
async def mark_order_ready_to_ship(
    order_id: int = Path(..., gt=0, description="ID of the order to mark as ready to ship"),
    db: Session = Depends(get_db),
):
    return transition_order(
        db=db,
        order_id=order_id,
        expected_status=OrderStatus.IN_PREPARATION.value,
        next_status=OrderStatus.READY_TO_SHIP,
        event_type=EVENT_ORDER_READY_TO_SHIP,
        action="marked as ready to ship",
        message="Order marked as ready to ship",
    )


@router.post(
    "/orders/{order_id}/shipped",
    response_model=OrderStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark order as shipped",
    responses={
        200: {"description": "Order status updated to shipped and order.shipped event published"},
        400: {"description": "Invalid state for shipping"},
        404: {"description": "Order not found"},
    },
)
async def mark_order_shipped(
    order_id: int = Path(..., gt=0, description="ID of the order to mark as shipped"),
    db: Session = Depends(get_db),
):
    return transition_order(
        db=db,
        order_id=order_id,
        expected_status=OrderStatus.READY_TO_SHIP.value,
        next_status=OrderStatus.SHIPPED,
        event_type=EVENT_ORDER_SHIPPED,
        action="marked as shipped",
        message="Order marked as shipped",
    )


@router.post(
    "/orders/{order_id}/delivered",
    response_model=OrderStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark order as delivered",
    responses={
        200: {
            "description": "Order status updated to delivered and order.delivered event published"
        },
        400: {"description": "Invalid state for delivery"},
        404: {"description": "Order not found"},
    },
)
async def mark_order_delivered(
    order_id: int = Path(..., gt=0, description="ID of the order to mark as delivered"),
    db: Session = Depends(get_db),
):
    return transition_order(
        db=db,
        order_id=order_id,
        expected_status=OrderStatus.SHIPPED.value,
        next_status=OrderStatus.DELIVERED,
        event_type=EVENT_ORDER_DELIVERED,
        action="marked as delivered",
        message="Order marked as delivered",
    )
