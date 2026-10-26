"""PDF statement extractor using in-memory pdfplumber table and text parsing."""

import io
import re
import uuid
from typing import Any

import pdfplumber

from app.extractor.base import BaseExtractor
from app.extractor.normalizer import normalize_amount, normalize_date
from app.observability import logger
from app.schemas import TransactionItem

DATE_HEADERS = [
    "fecha",
    "date",
    "f. operacion",
    "f. valor",
    "fecha operacion",
    "fecha valor",
    "posting date",
    "trans date",
]
CONCEPT_HEADERS = [
    "concepto",
    "descripcion",
    "description",
    "detalle",
    "movimiento",
    "memo",
    "details",
    "narrativa",
    "observaciones",
    "glosa",
]
REF_HEADERS = ["referencia", "reference", "ref", "documento", "no. operacion", "folio"]
AMOUNT_HEADERS = ["monto", "importe", "amount", "valor"]
DEBIT_HEADERS = ["cargo", "debito", "debit", "egreso", "retiro", "withdrawal", "cargos"]
CREDIT_HEADERS = ["abono", "credito", "credit", "ingreso", "deposito", "deposit", "abonos"]
BALANCE_HEADERS = ["saldo", "balance", "saldo contable", "saldo disponible"]


class PDFExtractor(BaseExtractor):
    """Parses PDF bank statements extracting tabular data and text stream movements."""

    def extract(self, file_bytes: bytes, filename: str) -> list[TransactionItem]:
        items: list[TransactionItem] = []

        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page_idx, page in enumerate(pdf.pages):
                    page_items = self._extract_from_page_tables(page, filename, page_idx)

                    # If table extraction yielded nothing, fallback to text regex parsing
                    if not page_items:
                        text = page.extract_text() or ""
                        page_items = self._extract_from_page_text(text, filename, page_idx)

                    items.extend(page_items)

        except Exception as exc:
            logger.error(f"Error reading PDF '{filename}': {exc}", exc_info=True)
            # Return any successfully extracted items or empty
            return items

        return items

    def _extract_from_page_tables(
        self, page: pdfplumber.page.Page, filename: str, page_idx: int
    ) -> list[TransactionItem]:
        items: list[TransactionItem] = []
        tables = page.extract_tables() or []

        for table in tables:
            if not table or len(table) < 2:
                continue

            # Detect header row
            header_idx = -1
            col_map: dict[str, int | None] = {}

            for r_idx, row in enumerate(table[:5]):
                c_map = self._map_columns(row)
                if c_map.get("date") is not None and (
                    c_map.get("amount") is not None
                    or (c_map.get("debit") is not None and c_map.get("credit") is not None)
                ):
                    header_idx = r_idx
                    col_map = c_map
                    break

            if header_idx == -1:
                # If no explicit header recognized, try assuming first row or searching for date column
                for r_idx, row in enumerate(table[:3]):
                    c_map = self._map_columns(row)
                    if c_map.get("date") is not None:
                        header_idx = r_idx
                        col_map = c_map
                        break

            if header_idx == -1:
                continue

            # Process data rows
            for row in table[header_idx + 1 :]:
                if not row or not any(row):
                    continue
                item = self._parse_table_row(row, col_map, filename)
                if item:
                    items.append(item)

        return items

    def _map_columns(self, row: list[Any]) -> dict[str, int | None]:
        col_map: dict[str, int | None] = {
            "date": None,
            "concept": None,
            "reference": None,
            "amount": None,
            "debit": None,
            "credit": None,
            "balance": None,
        }

        for idx, cell in enumerate(row):
            if not cell:
                continue
            text = str(cell).strip().lower()
            if col_map["date"] is None and any(h in text for h in DATE_HEADERS):
                col_map["date"] = idx
            elif col_map["concept"] is None and any(h in text for h in CONCEPT_HEADERS):
                col_map["concept"] = idx
            elif col_map["reference"] is None and any(h in text for h in REF_HEADERS):
                col_map["reference"] = idx
            elif col_map["debit"] is None and any(h in text for h in DEBIT_HEADERS):
                col_map["debit"] = idx
            elif col_map["credit"] is None and any(h in text for h in CREDIT_HEADERS):
                col_map["credit"] = idx
            elif col_map["amount"] is None and any(h in text for h in AMOUNT_HEADERS):
                col_map["amount"] = idx
            elif col_map["balance"] is None and any(h in text for h in BALANCE_HEADERS):
                col_map["balance"] = idx

        return col_map

    def _parse_table_row(
        self, row: list[Any], col_map: dict[str, int | None], filename: str
    ) -> TransactionItem | None:
        date_idx = col_map.get("date")
        if date_idx is None or date_idx >= len(row) or not row[date_idx]:
            return None

        iso_date = normalize_date(row[date_idx])
        if not iso_date:
            return None

        # Concept
        concept_idx = col_map.get("concept")
        concept = (
            str(row[concept_idx]).strip()
            if concept_idx is not None and concept_idx < len(row) and row[concept_idx]
            else "Movimiento bancario"
        )
        # Clean up line breaks in table cell text
        concept = " ".join(concept.split())

        # Reference
        ref_idx = col_map.get("reference")
        reference = (
            str(row[ref_idx]).strip()
            if ref_idx is not None and ref_idx < len(row) and row[ref_idx]
            else "No identificada"
        )

        monto: float = 0.0
        tipo: str = "egreso"
        currency = "USD"

        debit_idx = col_map.get("debit")
        credit_idx = col_map.get("credit")
        amount_idx = col_map.get("amount")

        if debit_idx is not None and credit_idx is not None:
            raw_deb = row[debit_idx] if debit_idx < len(row) else None
            raw_cred = row[credit_idx] if credit_idx < len(row) else None

            deb_amt, _, deb_curr = normalize_amount(raw_deb)
            cred_amt, _, cred_curr = normalize_amount(raw_cred)

            if cred_amt and cred_amt > 0:
                monto = cred_amt
                tipo = "ingreso"
                currency = cred_curr
            elif deb_amt and deb_amt > 0:
                monto = deb_amt
                tipo = "egreso"
                currency = deb_curr
            else:
                return None
        elif amount_idx is not None and amount_idx < len(row):
            amt, is_neg, curr = normalize_amount(row[amount_idx])
            if amt is None:
                return None
            monto = amt
            tipo = "egreso" if is_neg else "ingreso"
            currency = curr
        else:
            return None

        # Resulting Balance
        balance_idx = col_map.get("balance")
        saldo_resultante = None
        if balance_idx is not None and balance_idx < len(row) and row[balance_idx]:
            bal_amt, is_neg_bal, _ = normalize_amount(row[balance_idx])
            if bal_amt is not None:
                saldo_resultante = -bal_amt if is_neg_bal else bal_amt

        return TransactionItem(
            id=str(uuid.uuid4()),
            fecha=iso_date,
            descripcion_concepto=concept,
            referencia=reference,
            tipo_movimiento="ingreso" if tipo == "ingreso" else "egreso",
            monto=monto,
            saldo_resultante=saldo_resultante,
            moneda=currency,
            nombre_archivo_origen=filename,
            estado="success",
        )

    def _extract_from_page_text(
        self, text: str, filename: str, page_idx: int
    ) -> list[TransactionItem]:
        """Line-by-line fallback extractor for digital bank statement PDFs without formal table grid."""
        items: list[TransactionItem] = []
        if not text:
            return items

        # Regex for lines starting with a date: e.g. "12/05/2024 Transferencia Spei 12345 1,500.00 15,400.00"
        line_pattern = re.compile(
            r"^(\d{1,4}[-/\.]\d{1,2}[-/\.]\d{2,4})\s+(.+?)\s+([+-]?\$?\s*\(?[\d\.,]+\)?)\s*([+-]?\$?\s*\(?[\d\.,]+\)?)?$"
        )

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue

            match = line_pattern.match(line)
            if not match:
                continue

            raw_date, raw_concept, raw_amt, raw_balance = match.groups()
            iso_date = normalize_date(raw_date)
            if not iso_date:
                continue

            amt, is_neg, curr = normalize_amount(raw_amt)
            if amt is None:
                continue

            saldo_resultante = None
            if raw_balance:
                bal_amt, is_neg_bal, _ = normalize_amount(raw_balance)
                if bal_amt is not None:
                    saldo_resultante = -bal_amt if is_neg_bal else bal_amt

            # Check if reference is in concept
            ref_match = re.search(
                r"\b(REF|FOLIO|DOC|OP)[\s#:]*([A-Za-z0-9_-]+)", raw_concept, re.IGNORECASE
            )
            ref_val = ref_match.group(2) if ref_match else "No identificada"

            items.append(
                TransactionItem(
                    id=str(uuid.uuid4()),
                    fecha=iso_date,
                    descripcion_concepto=raw_concept.strip(),
                    referencia=ref_val,
                    tipo_movimiento="egreso" if is_neg else "ingreso",
                    monto=amt,
                    saldo_resultante=saldo_resultante,
                    moneda=curr,
                    nombre_archivo_origen=filename,
                    estado="success",
                )
            )

        return items
