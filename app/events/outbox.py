from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.config import logger
from app.events.publisher import EventPublisher
from app.models.outbox_event_model import OutboxEvent
from app.request_context import ensure_request_id


event_publisher = EventPublisher()


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def enqueue_event(db: Session, event_type: str, payload: dict[str, Any]) -> OutboxEvent:
    request_id = payload.get("request_id") or ensure_request_id()
    normalized_payload = _json_safe({**payload, "request_id": request_id})
    outbox_event = OutboxEvent(
        event_type=event_type,
        payload=normalized_payload,
        request_id=request_id,
    )
    db.add(outbox_event)
    return outbox_event


def publish_pending_events(db: Session, limit: int = 20) -> int:
    pending_events = (
        db.query(OutboxEvent)
        .filter(OutboxEvent.published_at.is_(None))
        .order_by(OutboxEvent.created_at.asc())
        .limit(limit)
        .all()
    )

    published_count = 0
    for pending_event in pending_events:
        pending_event.publish_attempts += 1
        try:
            event_publisher.publish_event(pending_event.event_type, pending_event.payload)
            pending_event.published_at = datetime.now(UTC)
            pending_event.last_error = None
            published_count += 1
        except Exception as exc:
            pending_event.last_error = str(exc)
            logger.exception(
                f"Failed to publish outbox event {pending_event.id} ({pending_event.event_type})"
            )

    db.commit()
    return published_count
