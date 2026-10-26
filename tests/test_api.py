"""HTTP integration tests for all BankReconcile REST API endpoints."""

import io

from fastapi.testclient import TestClient

from app.schemas import TransactionItem


def test_get_root_serves_html(client: TestClient) -> None:
    """Verify that GET / returns the single-page application HTML interface."""
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    assert "BankReconcile" in res.text


def test_get_health(client: TestClient) -> None:
    """Verify health endpoint returns healthy status and metadata."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["app_name"] == "BankReconcile"
    assert "version" in data
    assert "timestamp" in data


def test_get_metrics(client: TestClient) -> None:
    """Verify metrics endpoint reflects application telemetry."""
    res = client.get("/api/metrics")
    assert res.status_code == 200
    data = res.json()
    assert "total_requests" in data
    assert "uptime_seconds" in data
    assert data["total_requests"] >= 1


def test_post_extract_single_csv(client: TestClient, sample_csv_standard: bytes) -> None:
    """Verify extracting transactions from an uploaded CSV file."""
    files = [("files", ("extracto_chase.csv", io.BytesIO(sample_csv_standard), "text/csv"))]
    res = client.post("/api/extract", files=files)
    assert res.status_code == 200
    data = res.json()

    assert data["total_archivos"] == 1
    assert data["total_transacciones"] == 4
    assert data["total_ingresos"] == 6200.00
    assert data["total_egresos"] == 1820.50
    assert data["saldo_neto"] == 4379.50
    assert len(data["transacciones"]) == 4


def test_post_extract_single_pdf(client: TestClient, sample_pdf_bytes: bytes) -> None:
    """Verify extracting transactions from an uploaded PDF file."""
    files = [("files", ("extracto_bbva.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf"))]
    res = client.post("/api/extract", files=files)
    assert res.status_code == 200
    data = res.json()

    assert data["total_archivos"] == 1
    assert data["total_transacciones"] == 3
    assert len(data["transacciones"]) == 3


def test_post_extract_multiple_files(
    client: TestClient, sample_csv_standard: bytes, sample_pdf_bytes: bytes
) -> None:
    """Verify batch processing of heterogeneous statement uploads."""
    files = [
        ("files", ("banco1.csv", io.BytesIO(sample_csv_standard), "text/csv")),
        ("files", ("banco2.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")),
    ]
    res = client.post("/api/extract", files=files)
    assert res.status_code == 200
    data = res.json()

    assert data["total_archivos"] == 2
    assert data["total_transacciones"] == 7
    assert len(data["archivos_procesados"]) == 2


def test_post_extract_oversized_file(client: TestClient) -> None:
    """Verify that files exceeding the MAX_UPLOAD_SIZE limit return 413 Payload Too Large."""
    # 26 MB of dummy data
    large_payload = b"0" * (26 * 1024 * 1024)
    files = [("files", ("huge_statement.pdf", io.BytesIO(large_payload), "application/pdf"))]
    res = client.post("/api/extract", files=files)
    assert res.status_code == 413
    assert "supera el límite permitido" in res.json()["detail"]


def test_post_export_excel(
    client: TestClient, sample_transactions_list: list[TransactionItem]
) -> None:
    """Verify Excel export endpoint generates valid downloadable XLSX stream."""
    payload = {
        "transacciones": [t.model_dump() for t in sample_transactions_list],
        "nombre_reporte": "Conciliacion_Mayo_2024",
        "incluir_resumen": True,
    }
    res = client.post("/api/export", json=payload)
    assert res.status_code == 200
    assert (
        res.headers.get("content-type")
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "attachment; filename=" in res.headers.get("content-disposition", "")
    assert res.content.startswith(b"PK\x03\x04")


def test_post_export_excel_empty_rejected(client: TestClient) -> None:
    """Verify that export with empty transactions is rejected."""
    payload = {
        "transacciones": [],
        "nombre_reporte": "Vacio",
        "incluir_resumen": True,
    }
    res = client.post("/api/export", json=payload)
    assert res.status_code in [400, 422]
