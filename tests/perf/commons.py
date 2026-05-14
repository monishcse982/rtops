from locust import between

DEFAULT_WAIT = between(1, 3)
SHORT_WAIT = between(0.1, 0.3)
MEDIUM_WAIT = between(3, 5)
LONG_WAIT = between(5, 10)
