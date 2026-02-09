import logging
import structlog
from app.middleware import get_trace_id, get_request_id

class _ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = get_trace_id()
        record.request_id = get_request_id()
        record.service = "contoso-payments-api"
        return True

def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    root = logging.getLogger()
    root.addFilter(_ContextFilter())

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )
