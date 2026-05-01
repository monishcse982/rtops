import logging

from app.request_context import get_request_id


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = get_request_id()
        return True


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(request_id)s] %(message)s",
    handlers=[logging.StreamHandler()],
)

request_id_filter = RequestIdFilter()
for handler in logging.getLogger().handlers:
    handler.addFilter(request_id_filter)

logger = logging.getLogger("rtops")
