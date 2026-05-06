from reporting import api_request, assert_equal, assert_header, assert_status, assert_truthy


HEALTH_PATH = "/health"


def _health_url(test_config) -> str:
    return f"{test_config.api_url.rstrip('/')}{HEALTH_PATH}"


def test_health_endpoint_returns_ok(test_config):
    response = api_request("get", _health_url(test_config))

    assert_status(response, 200)
    assert_equal(response.json(), {"status": "ok"}, "health response body is ok")


def test_health_endpoint_returns_request_tracing_headers(test_config):
    response = api_request(
        "get",
        _health_url(test_config),
        headers={"X-Request-ID": "req-health-001"},
    )

    assert_status(response, 200)
    assert_header(response, "X-Request-ID", "req-health-001")
    assert_header(response, "X-Trace-ID", "req-health-001")


def test_generated_request_id_is_returned_on_health_endpoint_when_omitted(test_config):
    response = api_request("get", _health_url(test_config))

    assert_status(response, 200)
    generated_request_id = response.headers["X-Request-ID"]
    assert_truthy(generated_request_id, "generated request id is returned")
    assert_header(response, "X-Trace-ID", generated_request_id)
