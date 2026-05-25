import json
import os
import shlex
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

import allure
import requests
from sqlalchemy.inspection import inspect as sqlalchemy_inspect
from sqlalchemy.orm import Query

DEFAULT_HTTP_TIMEOUT_SECONDS = float(os.getenv("E2E_HTTP_TIMEOUT_SECONDS", "10"))


def _serialize(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_serialize(item) for item in value]
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, str)):
        return [_serialize(item) for item in value]

    try:
        mapper = sqlalchemy_inspect(value).mapper
        return {
            column.key: _serialize(getattr(value, column.key)) for column in mapper.column_attrs
        }
    except Exception:
        return repr(value)


def attach_json(name: str, payload: Any) -> None:
    allure.attach(
        json.dumps(_serialize(payload), indent=2, sort_keys=True),
        name=name,
        attachment_type=allure.attachment_type.JSON,
    )


def attach_text(name: str, content: str) -> None:
    allure.attach(
        content,
        name=name,
        attachment_type=allure.attachment_type.TEXT,
    )


def api_request(method: str, url: str, **kwargs) -> requests.Response:
    kwargs.setdefault("timeout", DEFAULT_HTTP_TIMEOUT_SECONDS)
    request_payload = {
        "method": method.upper(),
        "url": url,
        "timeout": kwargs.get("timeout"),
        "params": kwargs.get("params"),
        "headers": kwargs.get("headers"),
        "json": kwargs.get("json"),
        "data": kwargs.get("data"),
    }

    with allure.step(f"API {method.upper()} {url}"):
        attach_json("api-request", request_payload)
        attach_text("api-request-curl", _curl_command(method, url, **kwargs))
        response = requests.request(method=method, url=url, **kwargs)
        response_payload = {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": _response_body(response),
        }
        attach_json("api-response", response_payload)
        return response


def _curl_command(method: str, url: str, **kwargs) -> str:
    parts = ["curl", "-X", method.upper()]

    headers = kwargs.get("headers") or {}
    for key, value in headers.items():
        parts.extend(["-H", f"{key}: {value}"])

    params = kwargs.get("params")
    if params:
        from requests import PreparedRequest

        prepared = PreparedRequest()
        prepared.prepare_url(url, params)
        url = prepared.url

    json_body = kwargs.get("json")
    if json_body is not None:
        if "Content-Type" not in headers:
            parts.extend(["-H", "Content-Type: application/json"])
        parts.extend(["--data", json.dumps(_serialize(json_body), separators=(",", ":"))])

    data = kwargs.get("data")
    if data is not None and json_body is None:
        parts.extend(["--data", str(data)])

    parts.append(url)
    return " ".join(shlex.quote(part) for part in parts)


def _response_body(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text


def _compiled_query(query: Query) -> str:
    try:
        return str(query.statement.compile(compile_kwargs={"literal_binds": True}))
    except Exception:
        return str(query.statement)


def db_query_first(query: Query, label: str):
    with allure.step(f"DB {label}"):
        attach_text("db-query", _compiled_query(query))
        result = query.first()
        attach_json("db-result", result)
        return result


def db_query_one(query: Query, label: str):
    with allure.step(f"DB {label}"):
        attach_text("db-query", _compiled_query(query))
        result = query.one()
        attach_json("db-result", result)
        return result


def db_query_all(query: Query, label: str):
    with allure.step(f"DB {label}"):
        attach_text("db-query", _compiled_query(query))
        result = query.all()
        attach_json("db-result", result)
        return result


def db_query_count(query: Query, label: str) -> int:
    with allure.step(f"DB {label}"):
        attach_text("db-query", _compiled_query(query))
        result = query.count()
        attach_json("db-result", {"count": result})
        return result


def assert_equal(actual: Any, expected: Any, description: str) -> None:
    with allure.step(f"Assert {description}"):
        attach_json(
            "assertion",
            {
                "description": description,
                "expected": expected,
                "actual": actual,
            },
        )
        assert actual == expected


def assert_truthy(value: Any, description: str) -> None:
    with allure.step(f"Assert {description}"):
        attach_json(
            "assertion",
            {
                "description": description,
                "actual": value,
            },
        )
        assert value


def assert_status(response: requests.Response, expected_status: int) -> None:
    actual_status = response.status_code
    with allure.step(f"Assert response status is {expected_status}"):
        attach_json(
            "assertion",
            {
                "expected_status": expected_status,
                "actual_status": actual_status,
            },
        )
        assert actual_status == expected_status


def assert_header(response: requests.Response, header_name: str, expected_value: str) -> None:
    actual_value = response.headers[header_name]
    with allure.step(f"Assert header {header_name} matches expected value"):
        attach_json(
            "assertion",
            {
                "header": header_name,
                "expected": expected_value,
                "actual": actual_value,
            },
        )
        assert actual_value == expected_value
