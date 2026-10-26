"""Unit and parameterized tests for statement extractors and normalizers."""

from typing import Any

import pytest

from app.extractor.csv_extractor import CSVExtractor
from app.extractor.normalizer import detect_currency, normalize_amount, normalize_date
from app.extractor.pdf_extractor import PDFExtractor
from app.extractor.service import ExtractionService


@pytest.mark.parametrize(
    "raw_input,expected_amount,expected_negative,expected_currency",
    [
        ("$ 1,234.56", 1234.56, False, "USD"),
        ("-1.234,56 €", 1234.56, True, "EUR"),
        ("(500.00)", 500.00, True, "USD"),
        ("( 1,500.25 )", 1500.25, True, "USD"),
        ("+150.00 MXN", 150.00, False, "MXN"),
        ("250.00 DR", 250.00, True, "USD"),
        ("350.00 CR", 350.00, False, "USD"),
        ("1,000", 1000.00, False, "USD"),
        ("2.500", 2500.00, False, "USD"),
        ("120,50", 120.50, False, "USD"),
        ("£ 78.90", 78.90, False, "GBP"),
        (None, None, False, "USD"),
        ("", None, False, "USD"),
        ("-", None, False, "USD"),
        ("NaN", None, False, "USD"),
    ],
)
def test_normalize_amount_parameterized(
    raw_input: Any,
    expected_amount: float | None,
    expected_negative: bool,
    expected_currency: str,
) -> None:
    """Test monetary amount parsing across various international formats."""
    amount, is_neg, curr = normalize_amount(raw_input)
    assert amount == expected_amount
    assert is_neg == expected_negative
    assert curr == expected_currency


@pytest.mark.parametrize(
    "raw_date,expected_iso",
    [
        ("2024-05-15", "2024-05-15"),
        ("15/05/2024", "2024-05-15"),
        ("05-15-2024", "2024-05-15"),
        ("15.05.2024", "2024-05-15"),
        ("15-Ene-2024", "2024-01-15"),
        ("2024-05-12 18:45:00", "2024-05-12"),
        (None, None),
        ("", None),
        ("fecha_invalida", None),
    ],
)
def test_normalize_date_parameterized(raw_date: Any, expected_iso: str | None) -> None:
    """Test date parsing normalization to ISO 8601 (YYYY-MM-DD)."""
    assert normalize_date(raw_date) == expected_iso


def test_detect_currency() -> None:
    """Verify currency code detection from symbols and acronyms."""
    assert detect_currency("$ 50") == "USD"
    assert detect_currency("50 €") == "EUR"
    assert detect_currency("100 MXN") == "MXN"
    assert detect_currency("£ 20") == "GBP"
    assert detect_currency("desconocido") == "USD"


def test_csv_extractor_standard(sample_csv_standard: bytes) -> None:
    """Test extracting movements from standard CSV format."""
    extractor = CSVExtractor()
    items = extractor.extract(sample_csv_standard, "chase.csv")
    assert len(items) == 4

    ingresos = [i for i in items if i.tipo_movimiento == "ingreso"]
    egresos = [i for i in items if i.tipo_movimiento == "egreso"]

    assert len(ingresos) == 2
    assert len(egresos) == 2
    assert items[0].fecha == "2024-04-01"
    assert items[0].referencia == "REF-100"


def test_csv_extractor_european_semicolon(sample_csv_semicolon_european: bytes) -> None:
    """Test extracting movements from European semicolon format."""
    extractor = CSVExtractor()
    items = extractor.extract(sample_csv_semicolon_european, "santander_es.csv")
    assert len(items) == 3

    assert items[0].monto == 1500.50
    assert items[0].tipo_movimiento == "ingreso"
    assert items[1].monto == 120.40
    assert items[1].tipo_movimiento == "egreso"


def test_csv_extractor_single_amount(sample_csv_single_amount: bytes) -> None:
    """Test extracting movements with signed amount column."""
    extractor = CSVExtractor()
    items = extractor.extract(sample_csv_single_amount, "stripe_payouts.csv")
    assert len(items) == 3

    assert items[0].monto == 2400.00
    assert items[0].tipo_movimiento == "ingreso"
    assert items[1].monto == 36.00
    assert items[1].tipo_movimiento == "egreso"


def test_csv_extractor_empty_file() -> None:
    """Empty or unparseable CSV should return empty list gracefully."""
    extractor = CSVExtractor()
    assert extractor.extract(b"", "empty.csv") == []
    assert extractor.extract(b"solo,texto,sin,datos", "invalid.csv") == []


def test_pdf_extractor(sample_pdf_bytes: bytes) -> None:
    """Test extracting transactions from in-memory PDF digital stream."""
    extractor = PDFExtractor()
    items = extractor.extract(sample_pdf_bytes, "bbva_extracto.pdf")
    assert len(items) == 3

    # Check extracted values
    assert items[0].monto == 450.00
    assert items[0].tipo_movimiento == "egreso"
    assert items[1].monto == 1200.00
    assert items[1].tipo_movimiento == "ingreso"
    assert items[2].monto == 15.50
    assert items[2].tipo_movimiento == "egreso"


def test_pdf_extractor_corrupt_bytes() -> None:
    """Corrupt PDF bytes should be handled without raising unhandled exception."""
    extractor = PDFExtractor()
    items = extractor.extract(b"ESTO NO ES UN PDF VALIDO", "corrupt.pdf")
    assert items == []


def test_pdf_extractor_table_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test extracting transactions when PDF pages contain structured table grids."""
    extractor = PDFExtractor()

    class MockPage:
        def extract_tables(self) -> list[list[list[str]]]:
            return [
                [
                    ["Fecha", "Concepto", "Referencia", "Cargo", "Abono", "Saldo"],
                    ["2024-05-01", "Compra Insumos", "REF-10", "150.00", "", "9850.00"],
                    ["2024-05-03", "Cobro de Factura", "FAC-99", "", "750.50", "10600.50"],
                ]
            ]

        def extract_text(self) -> str:
            return ""

    class MockPDF:
        def __init__(self) -> None:
            self.pages = [MockPage()]

        def __enter__(self) -> "MockPDF":
            return self

        def __exit__(self, *args: Any) -> None:
            pass

    import pdfplumber

    monkeypatch.setattr(pdfplumber, "open", lambda *args, **kwargs: MockPDF())

    items = extractor.extract(b"dummy pdf bytes", "statement_tables.pdf")
    assert len(items) == 2
    assert items[0].monto == 150.00
    assert items[0].tipo_movimiento == "egreso"
    assert items[1].monto == 750.50
    assert items[1].tipo_movimiento == "ingreso"
    assert items[1].saldo_resultante == 10600.50


def test_pdf_extractor_table_single_amount_col(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test PDF table extraction with single signed amount column."""
    extractor = PDFExtractor()

    class MockPage:
        def extract_tables(self) -> list[list[list[str]]]:
            return [
                [
                    ["Date", "Description", "Ref", "Amount", "Balance"],
                    ["2024-06-01", "Client Deposit", "DEP-1", "1200.00", "5000.00"],
                    ["2024-06-02", "Hosting Fee", "HOST-2", "-45.00", "4955.00"],
                ]
            ]

        def extract_text(self) -> str:
            return ""

    class MockPDF:
        def __init__(self) -> None:
            self.pages = [MockPage()]

        def __enter__(self) -> "MockPDF":
            return self

        def __exit__(self, *args: Any) -> None:
            pass

    import pdfplumber

    monkeypatch.setattr(pdfplumber, "open", lambda *args, **kwargs: MockPDF())

    items = extractor.extract(b"dummy pdf bytes", "single_amount.pdf")
    assert len(items) == 2
    assert items[0].tipo_movimiento == "ingreso"
    assert items[0].monto == 1200.00
    assert items[1].tipo_movimiento == "egreso"
    assert items[1].monto == 45.00


def test_extraction_service_batch(sample_csv_standard: bytes, sample_pdf_bytes: bytes) -> None:
    """Test unified multi-file batch processing and metric calculation."""
    service = ExtractionService()
    files = [
        ("banco1.csv", sample_csv_standard),
        ("banco2.pdf", sample_pdf_bytes),
    ]
    batch = service.process_files(files)

    assert batch.total_archivos == 2
    assert batch.total_transacciones == 7
    assert batch.total_ingresos > 0
    assert batch.total_egresos > 0
    assert batch.saldo_neto == round(batch.total_ingresos - batch.total_egresos, 2)
    assert len(batch.archivos_procesados) == 2
    assert len(batch.archivos_con_error) == 0


def test_extraction_service_unsupported_format() -> None:
    """Unsupported extensions should be reported in error files list."""
    service = ExtractionService()
    files = [("document.docx", b"some binary data")]
    batch = service.process_files(files)

    assert batch.total_archivos == 1
    assert batch.total_transacciones == 0
    assert len(batch.archivos_con_error) == 1
    assert "Formato no soportado" in batch.archivos_con_error[0]
