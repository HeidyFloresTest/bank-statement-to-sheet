"""Unit tests for structured JSON logging, metrics aggregator, and observability middleware."""

import json
import logging
import uuid

from fastapi.testclient import TestClient

from app.observability import JSONLogFormatter, correlation_id_ctx, metrics


def test_json_log_formatter() -> None:
    """Verify that JSONLogFormatter produces valid JSON with expected telemetry fields."""
    formatter = JSONLogFormatter()
    logger_name = "test_logger"
    record = logging.LogRecord(
        name=logger_name,
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Operacion de prueba completada exitosamente",
        args=(),
        exc_info=None,
    )

    token = correlation_id_ctx.set("custom-correlation-1234")
    try:
        output = formatter.format(record)
    finally:
        correlation_id_ctx.reset(token)

    data = json.loads(output)
    assert data["level"] == "INFO"
    assert data["message"] == "Operacion de prueba completada exitosamente"
    assert data["correlation_id"] == "custom-correlation-1234"
    assert "timestamp" in data
    assert data["logger"] == logger_name


def test_json_log_formatter_with_exception() -> None:
    """Ensure exception stacktraces are captured in formatted JSON output."""
    formatter = JSONLogFormatter()
    try:
        raise ValueError("Error simulado para logs")
    except ValueError:
        import sys

        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="test_exc",
        level=logging.ERROR,
        pathname=__file__,
        lineno=35,
        msg="Falla en procesamiento",
        args=(),
        exc_info=exc_info,
    )

    output = formatter.format(record)
    data = json.loads(output)
    assert "exception" in data
    assert "ValueError: Error simulado para logs" in data["exception"]


def test_metrics_tracker_accumulation() -> None:
    """Verify metrics counter increments and snapshot values."""
    metrics.reset()
    assert metrics.total_requests == 0

    metrics.record_request()
    metrics.record_request()
    metrics.record_extraction(15)
    metrics.record_export()
    metrics.record_error()

    snap = metrics.get_snapshot()
    assert snap["total_requests"] == 2
    assert snap["total_extractions"] == 1
    assert snap["total_transactions_processed"] == 15
    assert snap["total_exports"] == 1
    assert snap["total_errors"] == 1
    assert snap["uptime_seconds"] >= 0


def test_observability_middleware_headers(client: TestClient) -> None:
    """Verify that the middleware injects Request-ID, Latency, and OWASP headers."""
    custom_req_id = str(uuid.uuid4())
    res = client.get("/health", headers={"X-Request-ID": custom_req_id})

    assert res.status_code == 200
    assert res.headers.get("X-Request-ID") == custom_req_id
    assert "X-Response-Time-Ms" in res.headers

    # OWASP Security Headers
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert res.headers.get("X-XSS-Protection") == "1; mode=block"
    assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_observability_middleware_auto_generates_request_id(client: TestClient) -> None:
    """When X-Request-ID is not provided, the middleware must generate a valid UUID."""
    res = client.get("/health")
    assert res.status_code == 200
    req_id = res.headers.get("X-Request-ID")
    assert req_id is not None
    # Validate UUID format
    assert uuid.UUID(req_id)
