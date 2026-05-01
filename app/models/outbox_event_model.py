from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, JSON, String, Text

from app.models.database import Base


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    request_id = Column(String, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=True)
    publish_attempts = Column(Integer, default=0, nullable=False)
    last_error = Column(Text, nullable=True)
