"""Unit tests for Pydantic v2 schemas and validation constraints."""

import pytest
from pydantic import ValidationError

from app.schemas import (
    BatchTransactionResponse,
    ExportExcelRequest,
    HealthResponse,
    MetricsResponse,
    TransactionItem,
)


def test_transaction_item_valid(sample_transaction_item: TransactionItem) -> None:
    """Verify that a valid transaction item passes all schema validations."""
    assert sample_transaction_item.fecha == "2024-05-15"
    assert sample_transaction_item.monto == 250.75
    assert sample_transaction_item.tipo_movimiento == "egreso"
    assert sample_transaction_item.moneda == "USD"
    assert sample_transaction_item.referencia == "AWS-88291"


def test_transaction_item_date_validation() -> None:
    """Ensure non-ISO date formats are rejected by the validator."""
    with pytest.raises(ValidationError) as exc_info:
        TransactionItem(
            fecha="15/05/2024",  # Not ISO YYYY-MM-DD
            descripcion_concepto="Prueba de fecha invalida",
            tipo_movimiento="ingreso",
            monto=100.0,
            nombre_archivo_origen="test.csv",
        )
    assert "Fecha must be in ISO YYYY-MM-DD format" in str(exc_info.value)


def test_transaction_item_negative_amount_rejected() -> None:
    """Verify that negative amounts fail ge=0.0 validation."""
    with pytest.raises(ValidationError):
        TransactionItem(
            fecha="2024-05-15",
            descripcion_concepto="Monto negativo invalido",
            tipo_movimiento="egreso",
            monto=-50.0,  # Negative not allowed
            nombre_archivo_origen="test.csv",
        )


def test_transaction_item_decimal_rounding() -> None:
    """Ensure amounts and balances are rounded to two decimal places."""
    item = TransactionItem(
        fecha="2024-05-15",
        descripcion_concepto="Redondeo financiero",
        tipo_movimiento="ingreso",
        monto=123.4567,
        saldo_resultante=987.6543,
        nombre_archivo_origen="test.csv",
    )
    assert item.monto == 123.46
    assert item.saldo_resultante == 987.65


def test_transaction_item_currency_uppercase() -> None:
    """Currency codes should be automatically normalized to uppercase."""
    item = TransactionItem(
        fecha="2024-05-15",
        descripcion_concepto="Test moneda",
        tipo_movimiento="ingreso",
        monto=50.0,
        moneda="eur",
        nombre_archivo_origen="test.csv",
    )
    assert item.moneda == "EUR"


def test_transaction_item_invalid_type_movement() -> None:
    """Only 'ingreso' and 'egreso' should be accepted."""
    with pytest.raises(ValidationError):
        TransactionItem(
            fecha="2024-05-15",
            descripcion_concepto="Tipo invalido",
            tipo_movimiento="otro",  # type: ignore
            monto=10.0,
            nombre_archivo_origen="test.csv",
        )


def test_batch_transaction_response() -> None:
    """Ensure BatchTransactionResponse accepts valid statistics."""
    resp = BatchTransactionResponse(
        total_archivos=1,
        total_transacciones=2,
        total_ingresos=500.0,
        total_egresos=200.0,
        saldo_neto=300.0,
        moneda_predominante="EUR",
        archivos_procesados=["test.csv"],
        archivos_con_error=[],
        transacciones=[],
    )
    assert resp.total_transacciones == 2
    assert resp.saldo_neto == 300.0
    assert resp.moneda_predominante == "EUR"


def test_export_excel_request_validation(sample_transaction_item: TransactionItem) -> None:
    """Verify ExportExcelRequest requires at least one transaction."""
    valid_req = ExportExcelRequest(
        transacciones=[sample_transaction_item],
        nombre_reporte="Mi_Reporte",
    )
    assert len(valid_req.transacciones) == 1

    with pytest.raises(ValidationError):
        ExportExcelRequest(transacciones=[])  # min_length=1


def test_health_and_metrics_schemas() -> None:
    """Verify health and metrics models."""
    health = HealthResponse(
        app_name="BankReconcile",
        version="0.1.0",
        environment="test",
        timestamp="2026-10-26T12:00:00Z",
    )
    assert health.status == "healthy"

    metrics_resp = MetricsResponse(
        uptime_seconds=120.5,
        total_requests=15,
        total_extractions=3,
        total_exports=2,
        total_transactions_processed=45,
        total_errors=0,
    )
    assert metrics_resp.total_transactions_processed == 45
