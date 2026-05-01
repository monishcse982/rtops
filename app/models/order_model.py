from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.models.database import Base


class OrderStatus(Enum):
    CREATED = "created"
    PENDING_PAYMENT = "pending_payment"
    IN_PREPARATION = "in_preparation"
    READY_TO_SHIP = "ready_to_ship"
    SHIPPED = "shipped"
    DELIVERED = "delivered"


class Order(Base):
    """Customer Orders"""

    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(SQLEnum(OrderStatus), default=OrderStatus.CREATED, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    tracking_number = Column(String, nullable=True)
    carrier = Column(String, nullable=True)

    # Relationship with LineItem
    line_items = relationship("LineItem", back_populates="order")

    def calculate_total(self, pricing_strategy):
        """Calculates the total price using a pricing strategy"""
        return pricing_strategy.calculate(self)

    def mark_as_pending_payment(self):
        """Mark the order as awaiting payment"""
        self.status = OrderStatus.PENDING_PAYMENT

    def mark_as_paid(self):
        """Mark the order as paid and ready for preparation"""
        self.status = OrderStatus.IN_PREPARATION

    def mark_as_ready_to_ship(self):
        """Mark the order as ready to ship"""
        self.status = OrderStatus.READY_TO_SHIP

    def mark_as_shipped(self):
        """Mark the order as shipped"""
        self.status = OrderStatus.SHIPPED

    def mark_as_delivered(self):
        """Mark the order as delivered"""
        self.status = OrderStatus.DELIVERED
