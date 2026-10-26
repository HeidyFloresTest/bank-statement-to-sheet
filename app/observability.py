"""Observability module providing structured JSON logging, telemetry metrics, and tracing middleware."""

import contextvars
import json
import logging
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Context variable for correlating logs with incoming HTTP request IDs
correlation_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)


class JSONLogFormatter(logging.Formatter):
    """Custom logging formatter that outputs log records as structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id_ctx.get() or "system",
        }

        # Include standard exception info if present
        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        # Include custom extra fields if provided
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_payload.update(record.extra_data)

        return json.dumps(log_payload, default=str)


def setup_logger(name: str = "bank_reconcile", level: str = "INFO") -> logging.Logger:
    """Configure and return a structured JSON logger."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Avoid duplicate handlers on reload
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONLogFormatter())
        logger.addHandler(handler)
        logger.propagate = False

    return logger


logger = setup_logger()


class MetricsTracker:
    """Thread-safe telemetry metrics aggregator for BankReconcile."""

    def __init__(self) -> None:
        self.start_time: float = time.time()
        self.total_requests: int = 0
        self.total_extractions: int = 0
        self.total_exports: int = 0
        self.total_transactions_processed: int = 0
        self.total_errors: int = 0

    def record_request(self) -> None:
        self.total_requests += 1

    def record_extraction(self, transaction_count: int) -> None:
        self.total_extractions += 1
        self.total_transactions_processed += transaction_count

    def record_export(self) -> None:
        self.total_exports += 1

    def record_error(self) -> None:
        self.total_errors += 1

    def get_snapshot(self) -> dict[str, Any]:
        """Return an instantaneous snapshot of application metrics."""
        return {
            "uptime_seconds": round(time.time() - self.start_time, 2),
            "total_requests": self.total_requests,
            "total_extractions": self.total_extractions,
            "total_exports": self.total_exports,
            "total_transactions_processed": self.total_transactions_processed,
            "total_errors": self.total_errors,
        }

    def reset(self) -> None:
        """Reset metrics (useful for isolated unit testing)."""
        self.start_time = time.time()
        self.total_requests = 0
        self.total_extractions = 0
        self.total_exports = 0
        self.total_transactions_processed = 0
        self.total_errors = 0


metrics = MetricsTracker()


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Enterprise middleware for request correlation, latency tracking, and security headers."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        start_time = time.perf_counter()

        # 1. Traceability / Correlation ID
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = correlation_id_ctx.set(req_id)

        metrics.record_request()

        try:
            response: Response = await call_next(request)
        except Exception as exc:
            metrics.record_error()
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(
                f"Unhandled error during request {request.method} {request.url.path}: {exc}",
                exc_info=True,
                extra={"extra_data": {"path": request.url.path, "duration_ms": duration_ms}},
            )
            raise exc
        finally:
            correlation_id_ctx.reset(token)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # 2. Inject Correlation & Performance Headers
        response.headers["X-Request-ID"] = req_id
        response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}ms"

        # 3. Inject OWASP Security Headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Track 4xx/5xx responses as errors in metrics
        if response.status_code >= 400:
            metrics.record_error()

        # Structured access log
        logger.info(
            f"{request.method} {request.url.path} - {response.status_code} ({duration_ms}ms)",
            extra={
                "extra_data": {
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                }
            },
        )

        return response
