"""Pydantic v2 schemas for BankReconcile data validation."""

import re
import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TransactionItem(BaseModel):
    """Normalized banking transaction schema."""

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="Unique UUID transaction ID"
    )
    fecha: str = Field(..., description="ISO 8601 transaction date (YYYY-MM-DD)")
    descripcion_concepto: str = Field(
        ..., min_length=1, description="Transaction concept or description"
    )
    referencia: str = Field(
        default="No identificada", description="Transaction or operation reference"
    )
    tipo_movimiento: Literal["ingreso", "egreso"] = Field(
        ..., description="Direction: ingreso (credit) or egreso (debit)"
    )
    monto: float = Field(
        ..., ge=0.0, description="Absolute transaction amount (must be non-negative)"
    )
    saldo_resultante: float | None = Field(
        default=None, description="Resulting account balance after transaction"
    )
    moneda: str = Field(default="USD", description="Currency code (USD, EUR, MXN, etc.)")
    nombre_archivo_origen: str = Field(..., description="Source statement filename")
    estado: Literal["success", "warning", "error"] = Field(
        default="success", description="Extraction parsing status"
    )
    mensaje_error: str | None = Field(
        default=None, description="Diagnostic error or warning message"
    )

    @field_validator("fecha")
    @classmethod
    def validate_iso_date(cls, v: str) -> str:
        """Ensure date strictly follows YYYY-MM-DD format."""
        v = v.strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError(f"Fecha must be in ISO YYYY-MM-DD format, got: {v}")
        return v

    @field_validator("monto", "saldo_resultante", mode="before")
    @classmethod
    def round_numeric_values(cls, v: float | None) -> float | None:
        """Round floating point monetary values to two decimal places."""
        if v is None:
            return None
        return round(float(v), 2)

    @field_validator("moneda")
    @classmethod
    def normalize_currency(cls, v: str) -> str:
        """Normalize currency code to upper case."""
        return v.strip().upper() if v else "USD"


class BatchTransactionResponse(BaseModel):
    """Batch extraction response summarizing processed transactions and aggregate metrics."""

    total_archivos: int = Field(..., ge=0, description="Total number of uploaded files")
    total_transacciones: int = Field(..., ge=0, description="Total extracted transactions")
    total_ingresos: float = Field(
        default=0.0, ge=0.0, description="Total sum of credits (ingresos)"
    )
    total_egresos: float = Field(default=0.0, ge=0.0, description="Total sum of debits (egresos)")
    saldo_neto: float = Field(default=0.0, description="Net balance change (ingresos - egresos)")
    moneda_predominante: str = Field(default="USD", description="Primary currency detected")
    archivos_procesados: list[str] = Field(
        default_factory=list, description="Files successfully processed"
    )
    archivos_con_error: list[str] = Field(
        default_factory=list, description="Files that encountered errors"
    )
    transacciones: list[TransactionItem] = Field(
        default_factory=list, description="List of all extracted transactions"
    )


class ExportExcelRequest(BaseModel):
    """Payload to export an edited list of transactions to Excel."""

    transacciones: list[TransactionItem] = Field(
        ..., min_length=1, description="List of transactions to export"
    )
    nombre_reporte: str = Field(
        default="Conciliacion_Bancaria", description="Base title of the report"
    )
    incluir_resumen: bool = Field(default=True, description="Whether to include summary KPI sheet")


class HealthResponse(BaseModel):
    """Service health status model."""

    status: str = "healthy"
    app_name: str
    version: str
    environment: str
    timestamp: str


class MetricsResponse(BaseModel):
    """Application telemetry and business metrics model."""

    uptime_seconds: float
    total_requests: int
    total_extractions: int
    total_exports: int
    total_transactions_processed: int
    total_errors: int
