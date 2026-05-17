from locust import HttpUser


class BaseApiUser(HttpUser):
    abstract = True

    @staticmethod
    def _raise_for_status(response, name: str, expected_status: int) -> None:
        if response.status_code == expected_status:
            return
        if response.status_code == 0:
            error = getattr(response, "error", None)
            response.failure(f"request failed before HTTP response: {error}")
            raise AssertionError(
                f"{name} did not receive an HTTP response. underlying error: {error}"
            )
        response.failure(f"expected status {expected_status}, got {response.status_code}")
        raise AssertionError(
            f"{name} returned status {response.status_code}, expected {expected_status}"
        )

    @staticmethod
    def _response_json(response, name: str) -> dict:
        try:
            payload = response.json()
        except ValueError as exc:
            response.failure("response body was not valid JSON")
            raise AssertionError(f"{name} returned invalid JSON") from exc
        response.success()
        return payload

    def get_json_ok(
        self,
        path: str,
        *,
        name: str,
        expected_status: int = 200,
    ) -> dict:
        with self.client.get(path, name=name, catch_response=True) as response:
            self._raise_for_status(response, name, expected_status)
            return self._response_json(response, name)

    def post_json_ok(
        self,
        path: str,
        *,
        name: str,
        json_body: dict,
        expected_status: int = 201,
    ) -> dict:
        with self.client.post(path, name=name, json=json_body, catch_response=True) as response:
            self._raise_for_status(response, name, expected_status)
            return self._response_json(response, name)
