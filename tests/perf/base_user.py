from locust import HttpUser


class BaseApiUser(HttpUser):
    abstract = True

    def get_json_ok(
        self,
        path: str,
        *,
        name: str,
        expected_status: int = 200,
    ) -> dict:
        with self.client.get(path, name=name, catch_response=True) as response:
            if response.status_code != expected_status:
                response.failure(f"expected status {expected_status}, got {response.status_code}")
                raise AssertionError(
                    f"{name} returned status {response.status_code}, expected {expected_status}"
                )

            try:
                payload = response.json()
            except ValueError as exc:
                response.failure("response body was not valid JSON")
                raise AssertionError(f"{name} returned invalid JSON") from exc

            response.success()
            return payload
