"""Pytest fixtures and mock resources for BankReconcile test suite."""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.observability import metrics
from app.schemas import TransactionItem


@pytest.fixture(autouse=True)
def reset_telemetry_metrics() -> Generator[None, None, None]:
    """Ensure telemetry counters are reset for isolated testing."""
    metrics.reset()
    yield
    metrics.reset()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """FastAPI TestClient fixture."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_transaction_item() -> TransactionItem:
    """Fixture providing a valid single TransactionItem."""
    return TransactionItem(
        id=str(uuid.uuid4()),
        fecha="2024-05-15",
        descripcion_concepto="Pago de Servicios Cloud AWS",
        referencia="AWS-88291",
        tipo_movimiento="egreso",
        monto=250.75,
        saldo_resultante=9749.25,
        moneda="USD",
        nombre_archivo_origen="extracto_mayo.csv",
        estado="success",
        mensaje_error=None,
    )


@pytest.fixture
def sample_transactions_list() -> list[TransactionItem]:
    """Fixture providing a realistic list of diverse transactions."""
    return [
        TransactionItem(
            id=str(uuid.uuid4()),
            fecha="2024-05-01",
            descripcion_concepto="Transferencia Recibida Cliente Alfa",
            referencia="TRF-00129",
            tipo_movimiento="ingreso",
            monto=3500.00,
            saldo_resultante=13500.00,
            moneda="USD",
            nombre_archivo_origen="chase_may_2024.csv",
            estado="success",
        ),
        TransactionItem(
            id=str(uuid.uuid4()),
            fecha="2024-05-05",
            descripcion_concepto="Pago Nomina Quincenal",
            referencia="NOM-5541",
            tipo_movimiento="egreso",
            monto=1850.50,
            saldo_resultante=11649.50,
            moneda="USD",
            nombre_archivo_origen="chase_may_2024.csv",
            estado="success",
        ),
        TransactionItem(
            id=str(uuid.uuid4()),
            fecha="2024-05-10",
            descripcion_concepto="Suscripción Software SaaS",
            referencia="SUB-9912",
            tipo_movimiento="egreso",
            monto=99.00,
            saldo_resultante=11550.50,
            moneda="USD",
            nombre_archivo_origen="chase_may_2024.csv",
            estado="success",
        ),
        TransactionItem(
            id=str(uuid.uuid4()),
            fecha="2024-05-18",
            descripcion_concepto="Reembolso de Gastos Operativos",
            referencia="RMB-3301",
            tipo_movimiento="ingreso",
            monto=245.80,
            saldo_resultante=11796.30,
            moneda="USD",
            nombre_archivo_origen="chase_may_2024.csv",
            estado="success",
        ),
    ]


@pytest.fixture
def sample_csv_standard() -> bytes:
    """Standard CSV statement with separate debit and credit columns."""
    content = (
        "Fecha,Concepto,Referencia,Cargo,Abono,Saldo\n"
        "2024-04-01,Deposito Inicial,REF-100,,5000.00,5000.00\n"
        "2024-04-05,Compra Insumos Oficina,FAC-881,320.50,,4679.50\n"
        "2024-04-12,Honorarios Consultoria,HON-002,,1200.00,5879.50\n"
        "2024-04-20,Pago Renta Local,REC-994,1500.00,,4379.50\n"
    )
    return content.encode("utf-8")


@pytest.fixture
def sample_csv_semicolon_european() -> bytes:
    """European format CSV statement with semicolons and comma decimals."""
    content = (
        "Fecha operacion;Descripcion;Documento;Importe;Saldo contable\n"
        "02/05/2024;Cobro Factura 102;DOC-102;+1.500,50;1.500,50\n"
        "10/05/2024;Recibo Luz Iberdrola;REC-55;-120,40;1.380,10\n"
        "15/05/2024;Servicio Internet Fibra;REC-98;-65,00;1.315,10\n"
    )
    return content.encode("latin-1")


@pytest.fixture
def sample_csv_single_amount() -> bytes:
    """CSV statement with a single Amount column and positive/negative values."""
    content = (
        "Date,Description,Reference,Amount,Balance\n"
        "2024-06-01,Stripe Payout,STR-001,2400.00,2400.00\n"
        "2024-06-04,Google Workspace,GSUITE-12,-36.00,2364.00\n"
        "2024-06-10,Client Wire Transfer,WIRE-99,850.50,3214.50\n"
    )
    return content.encode("utf-8")


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    """Valid minimal digital PDF bank statement containing structured transactions."""
    return b"""%PDF-1.4
1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj
2 0 obj <</Type /Pages /Kids [3 0 R] /Count 1>> endobj
3 0 obj <</Type /Page /Parent 2 0 R /Resources 4 0 R /MediaBox [0 0 612 792] /Contents 5 0 R>> endobj
4 0 obj <</Font <</F1 <</Type /Font /Subtype /Type1 /BaseFont /Helvetica>>>>>> endobj
5 0 obj <</Length 240>> stream
BT
/F1 10 Tf
50 720 Td
(2024-05-02 Pago Proveedor REF-8812 -450.00 9550.00) Tj
0 -20 Td
(2024-05-10 Deposito Cheque REF-3301 1200.00 10750.00) Tj
0 -20 Td
(2024-05-18 Comision Cuenta REF-0012 -15.50 10734.50) Tj
ET
endstream
endobj
xref
0 6
0000000000 65535 f 
0000000010 00000 n 
0000000060 00000 n 
0000000117 00000 n 
0000000216 00000 n 
0000000295 00000 n 
trailer <</Size 6 /Root 1 0 R>>
startxref
585
%%EOF"""
