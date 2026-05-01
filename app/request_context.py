from contextvars import ContextVar
from typing import Optional
from uuid import uuid4


_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def generate_request_id() -> str:
    return str(uuid4())


def get_request_id() -> str:
    request_id = _request_id.get()
    return request_id or "-"


def ensure_request_id(request_id: Optional[str] = None) -> str:
    current = _request_id.get()
    if current:
        return current

    assigned = request_id or generate_request_id()
    _request_id.set(assigned)
    return assigned


def set_request_id(request_id: Optional[str] = None):
    assigned = request_id or generate_request_id()
    return _request_id.set(assigned)


def reset_request_id(token) -> None:
    _request_id.reset(token)
