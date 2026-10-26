"""FastAPI main application for BankReconcile financial extraction engine."""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.excel.generator import excel_generator
from app.extractor.service import extraction_service
from app.observability import ObservabilityMiddleware, logger, metrics
from app.schemas import (
    BatchTransactionResponse,
    ExportExcelRequest,
    HealthResponse,
    MetricsResponse,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown event lifecycle."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} [{settings.APP_ENV}]")
    yield
    logger.info(f"Shutting down {settings.APP_NAME}")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Enterprise Bank Statement Extraction and Financial Reconciliation Engine",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# 1. Observability & Security Middleware
app.add_middleware(ObservabilityMiddleware)

# 2. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Mount Static Files
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def serve_index() -> FileResponse:
    """Serve the single-page frontend application."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Frontend interface file not found.",
        )
    return FileResponse(str(index_file))


@app.get("/health", response_model=HealthResponse, tags=["Observability"])
async def health_check() -> HealthResponse:
    """Health status and telemetry ping endpoint."""
    return HealthResponse(
        status="healthy",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/api/metrics", response_model=MetricsResponse, tags=["Observability"])
async def get_metrics() -> MetricsResponse:
    """Real-time business and system performance metrics."""
    return MetricsResponse(**metrics.get_snapshot())


@app.post("/api/extract", response_model=BatchTransactionResponse, tags=["Extraction"])
async def extract_statements(files: list[UploadFile]) -> BatchTransactionResponse:
    """Extract and normalize transactions from one or multiple PDF/CSV bank statements.

    - Validates file extensions (.pdf, .csv, .txt).
    - Processes files entirely in-memory.
    - Aggregates income, expense, and net balance KPIs.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se proporcionaron archivos para procesar.",
        )

    file_payloads = []
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    for file in files:
        filename = file.filename or "archivo_sin_nombre"
        content = await file.read()

        if len(content) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"El archivo '{filename}' supera el límite permitido de {settings.MAX_UPLOAD_SIZE_MB}MB.",
            )

        file_payloads.append((filename, content))

    batch_result = extraction_service.process_files(file_payloads)
    return batch_result


@app.post("/api/export", tags=["Export"])
async def export_transactions_excel(payload: ExportExcelRequest) -> StreamingResponse:
    """Export the list of edited transactions to a corporate Excel (.xlsx) file in-memory."""
    if not payload.transacciones:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe incluir al menos una transacción para exportar.",
        )

    excel_stream = excel_generator.generate_reconciliation_workbook(
        transactions=payload.transacciones,
        report_title=payload.nombre_reporte,
        include_summary=payload.incluir_resumen,
    )

    metrics.record_export()

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_title = "".join(
        c if c.isalnum() or c in ("-", "_") else "_" for c in payload.nombre_reporte
    )
    filename = f"{clean_title}_{timestamp_str}.xlsx"

    return StreamingResponse(
        excel_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all enterprise exception handler ensuring structured error responses."""
    logger.error(f"Global unhandled error on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Ha ocurrido un error interno en el servidor.",
            "error_type": exc.__class__.__name__,
        },
    )
