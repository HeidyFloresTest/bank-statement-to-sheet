"""CSV statement extractor supporting various bank exports (Chase, BBVA, Santander, etc.)."""

import csv
import io
import uuid
from typing import Any

import pandas as pd

from app.extractor.base import BaseExtractor
from app.extractor.normalizer import normalize_amount, normalize_date
from app.observability import logger
from app.schemas import TransactionItem

# Common column name heuristics across global banks
DATE_HEADERS = [
    "fecha",
    "date",
    "f. operacion",
    "f. valor",
    "fecha operacion",
    "fecha valor",
    "posting date",
    "transaction date",
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
REF_HEADERS = [
    "referencia",
    "reference",
    "ref",
    "documento",
    "no. operacion",
    "num operacion",
    "trans id",
    "folio",
    "cheque",
]
AMOUNT_HEADERS = ["monto", "importe", "amount", "valor", "trans amount"]
DEBIT_HEADERS = ["cargo", "debito", "debit", "egreso", "retiro", "withdrawal", "cargos"]
CREDIT_HEADERS = ["abono", "credito", "credit", "ingreso", "deposito", "deposit", "abonos"]
BALANCE_HEADERS = ["saldo", "balance", "saldo contable", "saldo disponible", "ending balance"]


class CSVExtractor(BaseExtractor):
    """Parses tabular bank statements exported in CSV/TSV format."""

    def extract(self, file_bytes: bytes, filename: str) -> list[TransactionItem]:
        df = self._read_csv_to_df(file_bytes)
        if df is None or df.empty:
            logger.warning(f"CSV file '{filename}' was empty or unparseable")
            return []

        col_map = self._map_columns(df.columns.tolist())
        items: list[TransactionItem] = []

        for idx, row in df.iterrows():
            item = self._parse_row(row, col_map, filename, idx)
            if item:
                items.append(item)

        return items

    def _read_csv_to_df(self, file_bytes: bytes) -> pd.DataFrame | None:
        """Try reading CSV with multiple encodings and auto-detected delimiters."""
        encodings = ["utf-8-sig", "utf-8", "latin-1", "cp1252"]
        sample_text = ""

        # Decode snippet to sniff delimiter
        for enc in encodings:
            try:
                sample_text = file_bytes[:4096].decode(enc)
                break
            except UnicodeDecodeError:
                continue

        delimiter = ","
        if sample_text:
            try:
                sniffer = csv.Sniffer()
                dialect = sniffer.sniff(sample_text, delimiters=",;\t|")
                delimiter = dialect.delimiter
            except Exception:
                # Count frequencies in first lines
                first_line = sample_text.splitlines()[0] if sample_text.splitlines() else ""
                counts = {d: first_line.count(d) for d in [",", ";", "\t", "|"]}
                delimiter = max(counts, key=lambda k: counts[k]) if any(counts.values()) else ","

        for enc in encodings:
            try:
                # Skip leading metadata rows if header is further down
                stream = io.BytesIO(file_bytes)
                df = pd.read_csv(
                    stream,
                    delimiter=delimiter,
                    encoding=enc,
                    dtype=str,
                    skipinitialspace=True,
                    on_bad_lines="skip",
                )
                if not df.empty:
                    # Check if first row is better header candidate
                    if not any(self._is_date_col(c) for c in df.columns):
                        for skip_idx in range(1, min(6, len(df))):
                            stream.seek(0)
                            sub_df = pd.read_csv(
                                stream,
                                delimiter=delimiter,
                                encoding=enc,
                                dtype=str,
                                skiprows=skip_idx,
                                skipinitialspace=True,
                                on_bad_lines="skip",
                            )
                            if any(self._is_date_col(c) for c in sub_df.columns):
                                return sub_df
                    return df
            except Exception:
                continue
        return None

    def _is_date_col(self, col_name: str) -> bool:
        clean = str(col_name).strip().lower()
        return any(dh in clean for dh in DATE_HEADERS)

    def _map_columns(self, columns: list[str]) -> dict[str, str | None]:
        """Map raw header names to canonical schema attributes."""
        col_map: dict[str, str | None] = {
            "date": None,
            "concept": None,
            "reference": None,
            "amount": None,
            "debit": None,
            "credit": None,
            "balance": None,
        }

        for col in columns:
            c = str(col).strip().lower()
            if not col_map["date"] and any(h in c for h in DATE_HEADERS):
                col_map["date"] = col
            elif not col_map["concept"] and any(h in c for h in CONCEPT_HEADERS):
                col_map["concept"] = col
            elif not col_map["reference"] and any(h in c for h in REF_HEADERS):
                col_map["reference"] = col
            elif not col_map["debit"] and any(h in c for h in DEBIT_HEADERS):
                col_map["debit"] = col
            elif not col_map["credit"] and any(h in c for h in CREDIT_HEADERS):
                col_map["credit"] = col
            elif not col_map["amount"] and any(h in c for h in AMOUNT_HEADERS):
                col_map["amount"] = col
            elif not col_map["balance"] and any(h in c for h in BALANCE_HEADERS):
                col_map["balance"] = col

        return col_map

    def _parse_row(
        self, row: pd.Series, col_map: dict[str, str | None], filename: str, row_idx: Any
    ) -> TransactionItem | None:
        date_col = col_map.get("date")
        if not date_col or pd.isna(row.get(date_col)):
            return None

        iso_date = normalize_date(row[date_col])
        if not iso_date:
            return None

        # Description
        concept_col = col_map.get("concept")
        concept = (
            str(row[concept_col]).strip()
            if concept_col and not pd.isna(row.get(concept_col))
            else f"Movimiento {row_idx + 1}"
        )

        # Reference
        ref_col = col_map.get("reference")
        reference = (
            str(row[ref_col]).strip()
            if ref_col and not pd.isna(row.get(ref_col)) and str(row[ref_col]).strip()
            else "No identificada"
        )

        # Amount and direction resolution
        monto: float = 0.0
        tipo: str = "egreso"
        currency = "USD"

        debit_col = col_map.get("debit")
        credit_col = col_map.get("credit")
        amount_col = col_map.get("amount")

        if debit_col and credit_col:
            raw_deb = row.get(debit_col)
            raw_cred = row.get(credit_col)
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
        elif amount_col:
            amt, is_neg, curr = normalize_amount(row.get(amount_col))
            if amt is None:
                return None
            monto = amt
            tipo = "egreso" if is_neg else "ingreso"
            currency = curr
        else:
            return None

        # Resulting Balance
        balance_col = col_map.get("balance")
        saldo_resultante = None
        if balance_col and not pd.isna(row.get(balance_col)):
            bal_amt, is_neg_bal, _ = normalize_amount(row.get(balance_col))
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
