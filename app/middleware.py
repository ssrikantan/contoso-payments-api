import contextvars
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

trace_id_var = contextvars.ContextVar("trace_id", default="")
request_id_var = contextvars.ContextVar("request_id", default="")

def get_trace_id() -> str:
    return trace_id_var.get() or ""

def get_request_id() -> str:
    return request_id_var.get() or ""

def _extract_trace_id(traceparent: str) -> str:
    # W3C traceparent: 00-<trace_id>-<span_id>-<flags>
    try:
        parts = traceparent.split("-")
        if len(parts) >= 4 and len(parts[1]) == 32:
            return parts[1]
    except Exception:
        pass
    return ""

class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, service_name: str):
        super().__init__(app)
        self.service_name = service_name

    async def dispatch(self, request: Request, call_next):
        tp = request.headers.get("traceparent", "")
        trace_id = _extract_trace_id(tp) or uuid.uuid4().hex
        req_id = request.headers.get("x-request-id") or str(uuid.uuid4())

        trace_id_var.set(trace_id)
        request_id_var.set(req_id)

        response: Response = await call_next(request)
        response.headers["x-trace-id"] = trace_id
        response.headers["x-request-id"] = req_id
        return response
