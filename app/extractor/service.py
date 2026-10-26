"""Unified extraction service coordinating file parsing, aggregation, and business KPIs."""

from collections import Counter

from app.config import settings
from app.extractor.csv_extractor import CSVExtractor
from app.extractor.pdf_extractor import PDFExtractor
from app.observability import logger, metrics
from app.schemas import BatchTransactionResponse, TransactionItem


class ExtractionService:
    """Enterprise service orchestrating multi-format bank statement extraction."""

    def __init__(self) -> None:
        self.csv_extractor = CSVExtractor()
        self.pdf_extractor = PDFExtractor()

    def process_files(self, files: list[tuple[str, bytes]]) -> BatchTransactionResponse:
        """Process a batch of uploaded statement files in memory.

        :param files: List of tuples containing (filename, file_bytes).
        :return: BatchTransactionResponse with all normalized movements and KPI totals.
        """
        all_transactions: list[TransactionItem] = []
        processed_files: list[str] = []
        error_files: list[str] = []

        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

        for filename, file_bytes in files:
            # File size validation
            if len(file_bytes) > max_bytes:
                logger.warning(
                    f"File '{filename}' exceeds max size of {settings.MAX_UPLOAD_SIZE_MB}MB ({len(file_bytes)} bytes)"
                )
                error_files.append(f"{filename} (Excede límite de tamaño)")
                continue

            lower_name = filename.lower()
            try:
                if lower_name.endswith(".pdf"):
                    items = self.pdf_extractor.extract(file_bytes, filename)
                elif lower_name.endswith(".csv") or lower_name.endswith(".txt"):
                    items = self.csv_extractor.extract(file_bytes, filename)
                else:
                    logger.warning(f"Unsupported file format for '{filename}'")
                    error_files.append(f"{filename} (Formato no soportado)")
                    continue

                if items:
                    all_transactions.extend(items)
                    processed_files.append(filename)
                else:
                    logger.warning(f"No transactions could be extracted from '{filename}'")
                    error_files.append(f"{filename} (Sin transacciones detectadas)")

            except Exception as exc:
                logger.error(f"Failed processing file '{filename}': {exc}", exc_info=True)
                error_files.append(f"{filename} (Error: {str(exc)})")

        # Sort transactions chronologically
        all_transactions.sort(key=lambda t: t.fecha)

        # Calculate metrics
        total_ingresos = round(
            sum(t.monto for t in all_transactions if t.tipo_movimiento == "ingreso"), 2
        )
        total_egresos = round(
            sum(t.monto for t in all_transactions if t.tipo_movimiento == "egreso"), 2
        )
        saldo_neto = round(total_ingresos - total_egresos, 2)

        # Detect predominant currency
        currencies = [t.moneda for t in all_transactions if t.moneda]
        predominant_currency = Counter(currencies).most_common(1)[0][0] if currencies else "USD"

        # Record observability metrics
        metrics.record_extraction(len(all_transactions))

        return BatchTransactionResponse(
            total_archivos=len(files),
            total_transacciones=len(all_transactions),
            total_ingresos=total_ingresos,
            total_egresos=total_egresos,
            saldo_neto=saldo_neto,
            moneda_predominante=predominant_currency,
            archivos_procesados=processed_files,
            archivos_con_error=error_files,
            transacciones=all_transactions,
        )


extraction_service = ExtractionService()
